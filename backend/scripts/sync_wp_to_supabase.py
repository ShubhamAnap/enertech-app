import json
import re
import urllib.request
import urllib.parse
import uuid
from decimal import Decimal

WP_BASE = "https://enertechups.com/wp-json"
CK = "ck_f983a4e8f5dded00219f30f4a2134a09d79d8f0b"
CS = "cs_c4b42aa8987de6a8a26654e188832662cc9dfb17"

SUPABASE_URL = "https://josgulldmjmceyjnzupn.supabase.co/rest/v1"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Impvc2d1bGxkbWptY2V5am56dXBuIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc5NTQ4ODYzMCwiZXhwIjoyMTExMDY0NjMwfQ.e7n-a9_1M0VVT4Nla4pZOGpP2U1oXrh1bufl4rawU24"

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates,return=representation"
}

def clean_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    clean = re.sub(r"<[^>]+>", " ", str(raw_html))
    return " ".join(clean.split()).strip()

def safe_parse_json(text: str):
    start_arr = text.find("[")
    start_obj = text.find("{")
    if start_arr != -1 and (start_obj == -1 or start_arr < start_obj):
        end_arr = text.rfind("]")
        if end_arr != -1:
            return json.loads(text[start_arr:end_arr + 1])
    elif start_obj != -1:
        end_obj = text.rfind("}")
        if end_obj != -1:
            return json.loads(text[start_obj:end_obj + 1])
    return json.loads(text)

def fetch_wp_all(endpoint: str, extra_params=None):
    results = []
    page = 1
    import base64
    auth_header = "Basic " + base64.b64encode(f"{CK}:{CS}".encode()).decode()

    while True:
        params = {"per_page": 100, "page": page, **(extra_params or {})}
        qs = urllib.parse.urlencode(params)
        url = f"{WP_BASE}/{endpoint}?{qs}"
        req = urllib.request.Request(url, headers={
            "Authorization": auth_header,
            "User-Agent": "EnerTech-Sync/1.0"
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read().decode("utf-8", errors="ignore")
                items = safe_parse_json(data)
                if not items or not isinstance(items, list):
                    break
                results.extend(items)
                print(f"[{endpoint}] Page {page}: fetched {len(items)} items (total: {len(results)})")
                if len(items) < 100:
                    break
                page += 1
        except Exception as e:
            print(f"[{endpoint}] Error on page {page}: {e}")
            break
    return results

def sync_all():
    print("=== 1. FETCHING WORDPRESS CATEGORIES ===")
    wp_categories = fetch_wp_all("wc/v3/products/categories", {"hide_empty": "false"})
    print(f"Total WP Categories found: {len(wp_categories)}")

    cat_rows = []
    wp_cat_to_slug = {}
    for item in wp_categories:
        wp_id = str(item.get("id"))
        name = clean_html(item.get("name", ""))
        slug = str(item.get("slug") or f"cat-{wp_id}")[:180]
        desc = clean_html(item.get("description", ""))
        img = item.get("image", {})
        img_url = img.get("src") if isinstance(img, dict) else None
        
        cat_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"enertech-cat-{wp_id}"))
        wp_cat_to_slug[wp_id] = slug
        cat_rows.append({
            "id": cat_id,
            "wordpress_source_id": wp_id,
            "name": name,
            "slug": slug,
            "description": desc or None,
            "sort_order": int(item.get("menu_order") or 0),
            "image_url": img_url,
            "is_published": True
        })

    # Upsert categories to Supabase
    req = urllib.request.Request(
        f"{SUPABASE_URL}/product_categories?on_conflict=wordpress_source_id",
        headers=SUPABASE_HEADERS,
        data=json.dumps(cat_rows).encode("utf-8")
    )
    try:
        with urllib.request.urlopen(req) as resp:
            saved_cats = json.loads(resp.read().decode())
            print(f"Successfully upserted {len(saved_cats)} categories in Supabase!")
    except urllib.error.HTTPError as e:
        print("Supabase Category Upsert Error 400:", e.read().decode())
        raise

    # Fetch mapping of wp_id to category UUID
    req = urllib.request.Request(f"{SUPABASE_URL}/product_categories?select=id,wordpress_source_id", headers=SUPABASE_HEADERS)
    with urllib.request.urlopen(req) as resp:
        db_cats = json.loads(resp.read().decode())
        wp_to_cat_id = {c["wordpress_source_id"]: c["id"] for c in db_cats if c.get("wordpress_source_id")}

    print("=== 2. FETCHING WORDPRESS PRODUCTS ===")
    wp_products = fetch_wp_all("wc/v3/products", {"status": "publish"})
    print(f"Total WP Products found: {len(wp_products)}")

    default_cat_id = next(iter(wp_to_cat_id.values()), None)

    prod_rows = []
    for item in wp_products:
        wp_id = str(item.get("id"))
        name = clean_html(item.get("name", ""))
        slug = str(item.get("slug") or f"product-{wp_id}")[:180]
        sku = str(item.get("sku") or "").strip() or None
        summary = clean_html(item.get("short_description", ""))[:500] or None
        desc = clean_html(item.get("description", "")) or None
        
        # Category lookup
        categories = item.get("categories", [])
        assigned_cat_id = default_cat_id
        for c in categories:
            cid = str(c.get("id"))
            if cid in wp_to_cat_id:
                assigned_cat_id = wp_to_cat_id[cid]
                break

        # Images
        images = item.get("images", [])
        main_img = images[0].get("src") if images and isinstance(images[0], dict) else None
        gallery = [img.get("src") for img in images[1:] if isinstance(img, dict) and img.get("src")]

        # Price
        raw_price = item.get("price") or item.get("regular_price")
        price_minor = None
        if raw_price:
            try:
                price_minor = int(Decimal(str(raw_price)) * 100)
            except Exception:
                price_minor = None

        # Stock
        stock_status = str(item.get("stock_status") or "instock")
        if stock_status not in ("instock", "outofstock", "onbackorder"):
            stock_status = "instock"

        # Documents / Downloads (PDF)
        docs = []
        downloads = item.get("downloads", [])
        for d in downloads:
            furl = d.get("file", "")
            if furl:
                docs.append({"title": d.get("name") or "Product Datasheet", "url": furl})

        # Attributes / specifications
        attributes = item.get("attributes", [])
        specs = {}
        for attr in attributes:
            aname = clean_html(attr.get("name", ""))
            options = attr.get("options", [])
            if aname and options:
                specs[aname] = options[0] if len(options) == 1 else options

        prod_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"enertech-prod-{wp_id}"))
        prod_rows.append({
            "id": prod_id,
            "wordpress_source_id": wp_id,
            "category_id": assigned_cat_id,
            "name": name,
            "slug": slug,
            "model_code": sku,
            "summary": summary,
            "description": desc,
            "applications": [],
            "features": [],
            "specifications": specs or {},
            "image_url": main_img,
            "gallery_images": gallery or [],
            "price_minor": price_minor,
            "currency_code": "INR",
            "currency_minor_unit": 2,
            "stock_status": stock_status,
            "documents": docs or [],
            "wordpress_source_url": item.get("permalink"),
            "is_published": True
        })

    # Upsert products to Supabase in batches of 50
    total_saved = 0
    for i in range(0, len(prod_rows), 50):
        batch = prod_rows[i:i + 50]
        req = urllib.request.Request(
            f"{SUPABASE_URL}/products?on_conflict=wordpress_source_id",
            headers=SUPABASE_HEADERS,
            data=json.dumps(batch).encode("utf-8")
        )
        try:
            with urllib.request.urlopen(req) as resp:
                saved = json.loads(resp.read().decode())
                total_saved += len(saved)
                print(f"Upserted batch {i//50 + 1}: {len(saved)} products (total: {total_saved})")
        except urllib.error.HTTPError as e:
            print(f"Batch {i//50 + 1} 400 error:", e.read().decode())
            raise

    print(f"=== COMPLETED! Total {len(cat_rows)} categories and {total_saved} products synced into Supabase! ===")

if __name__ == "__main__":
    sync_all()
