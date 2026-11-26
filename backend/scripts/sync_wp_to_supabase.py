"""Standalone WooCommerce -> Supabase REST sync script using hardened parser, auth fallback, and PDF preservation."""

import base64
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

WP_BASE = os.getenv("WORDPRESS_API_BASE_URL", "https://enertechups.com/wp-json").strip().rstrip("/")
CK = os.getenv("WORDPRESS_CONSUMER_KEY", "").strip()
CS = os.getenv("WORDPRESS_CONSUMER_SECRET", "").strip()

SUPABASE_URL = f"{os.getenv('SUPABASE_URL', '').strip().rstrip('/')}/rest/v1"
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates,return=representation",
}


_ORIGIN = "/".join(WP_BASE.split("/")[:3])
_REQUEST_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (compatible; EnerTechSync/1.0)",
}
_HTML_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
}
_PDF_URL_RE = re.compile(r"https?://[^\s\"'<>]+?\.pdf(?:\?[^\s\"'<>]*)?", re.I)
_REL_PDF_RE = re.compile(r"(?:/?wp-content/uploads/[^\s\"'<>]+?\.pdf(?:\?[^\s\"'<>]*)?)", re.I)


def to_https_url(raw: str | None) -> str | None:
    text = str(raw or "").strip().replace("\\/", "/")
    if not text:
        return None
    if text.startswith("//"):
        text = f"https:{text}"
    elif text.startswith("/") and _ORIGIN:
        text = f"{_ORIGIN}{text}"
    elif text.startswith("wp-content/") and _ORIGIN:
        text = f"{_ORIGIN}/{text}"
    if text.startswith("http://"):
        text = "https://" + text[len("http://"):]
    return text if text.startswith("https://") else None


def clean_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    clean = re.sub(r"<[^>]+>", " ", str(raw_html))
    return " ".join(clean.split()).strip()


def safe_parse_json(text: str):
    cleaned = text.lstrip("\ufeff \t\r\n")
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    decoder = json.JSONDecoder()
    for idx, ch in enumerate(cleaned):
        if ch in ("[", "{"):
            try:
                obj, _ = decoder.raw_decode(cleaned, idx)
                if isinstance(obj, list):
                    return obj
            except json.JSONDecodeError:
                continue
    return json.loads(cleaned)


def fetch_wp_all(endpoint: str, extra_params=None, authenticated=True, page_size: int = 20):
    results = []
    page = 1
    current_page_size = page_size
    can_auth = bool(CK and CS)
    auth_active = authenticated
    auth_mode = "basic_header" if (auth_active and can_auth) else "public"
    auth_header = "Basic " + base64.b64encode(f"{CK}:{CS}".encode()).decode() if can_auth else None

    while page <= 500:
        params = {"per_page": current_page_size, "page": page, **(extra_params or {})}
        if auth_active and auth_mode == "query_params" and can_auth:
            params["consumer_key"] = CK
            params["consumer_secret"] = CS
        qs = urllib.parse.urlencode(params)
        url = f"{WP_BASE}/{endpoint.strip('/')}?{qs}"
        headers = dict(_REQUEST_HEADERS)
        if auth_active and auth_mode == "basic_header" and auth_header:
            headers["Authorization"] = auth_header

        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = resp.read().decode("utf-8", errors="replace")
                items = safe_parse_json(data)
                if not items or not isinstance(items, list):
                    break
                results.extend(items)
                print(f"[{endpoint}] Page {page}: fetched {len(items)} items (total: {len(results)})")
                if len(items) < current_page_size:
                    break
                page += 1
        except urllib.error.HTTPError as e:
            body_preview = e.read().decode("utf-8", errors="replace")[:200]
            if e.code in (401, 403) and not auth_active and can_auth:
                print(f"[{endpoint}] HTTP {e.code} unauthenticated; retrying with Basic auth")
                auth_active = True
                auth_mode = "basic_header"
                continue
            if e.code in (401, 403) and auth_active and auth_mode == "basic_header":
                print(f"[{endpoint}] HTTP {e.code} with Basic auth; switching to query-string auth")
                auth_mode = "query_params"
                continue
            if e.code == 400 and page == 1 and current_page_size > 25:
                current_page_size = 25
                continue
            print(f"[{endpoint}] HTTP {e.code} on page {page}: {body_preview!r}")
            break
        except Exception as e:
            print(f"[{endpoint}] Error on page {page}: {type(e).__name__}: {e}")
            break
    return results


def _collect_pdf_urls(value, title: str, found: dict[str, str], media_by_id: dict, allow_non_pdf: bool = False):
    if value is None:
        return
    if isinstance(value, str):
        unescaped = value.replace("\\/", "/")
        if allow_non_pdf and (unescaped.startswith(("http://", "https://", "/")) or ".pdf" in unescaped.lower()):
            u = to_https_url(unescaped)
            if u:
                found.setdefault(u[:1000], (title or "Product brochure")[:180])
                return
        for raw in _PDF_URL_RE.findall(unescaped) + _REL_PDF_RE.findall(unescaped):
            u = to_https_url(raw)
            if u:
                found.setdefault(u[:1000], (title or "Product datasheet")[:180])
    elif isinstance(value, int) and not isinstance(value, bool):
        m = media_by_id.get(str(value))
        if m and m.get("source_url"):
            u = to_https_url(m["source_url"])
            if u:
                t = clean_html((m.get("title") or {}).get("rendered", "")) or title
                found.setdefault(u[:1000], (t or "Product datasheet")[:180])
    elif isinstance(value, dict):
        url_candidate = value.get("url") or value.get("src") or value.get("href") or value.get("file") or value.get("source_url")
        if url_candidate:
            _collect_pdf_urls(url_candidate, str(value.get("title") or value.get("name") or title), found, media_by_id, allow_non_pdf=allow_non_pdf)
        for v in value.values():
            _collect_pdf_urls(v, title, found, media_by_id, allow_non_pdf=allow_non_pdf)
    elif isinstance(value, list):
        for entry in value:
            _collect_pdf_urls(entry, title, found, media_by_id, allow_non_pdf=allow_non_pdf)


def extract_html_pdf_documents(page_url: str | None, default_title: str) -> list[dict]:
    safe_url = to_https_url(page_url)
    if not safe_url:
        return []
    try:
        req = urllib.request.Request(safe_url, headers=_HTML_HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            if "html" not in (resp.headers.get("Content-Type") or "").lower():
                return []
            html = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return []
    scoped = re.sub(r"<(header|nav|footer)\b[^>]*>.*?</\1>", " ", html, flags=re.I | re.S)
    main_match = re.search(r"<main\b[^>]*>(.*?)</main>", scoped, flags=re.I | re.S)
    if main_match:
        scoped = main_match.group(1)
    found: dict[str, str] = {}
    for m in re.finditer(r"<a\b[^>]*href=[\"']([^\"']+\.pdf(?:\?[^\"']*)?)[\"'][^>]*>(.*?)</a>", scoped, flags=re.I | re.S):
        u = to_https_url(m.group(1))
        if u:
            label = clean_html(m.group(2)) or default_title
            found.setdefault(u[:1000], label[:180])
    for raw in _PDF_URL_RE.findall(scoped.replace("\\/", "/")) + _REL_PDF_RE.findall(scoped.replace("\\/", "/")):
        u = to_https_url(raw)
        if u:
            found.setdefault(u[:1000], default_title[:180])
    return [{"title": t, "url": u} for u, t in list(found.items())[:12]]


def extract_pdf_documents(item: dict, media_by_id: dict, media_by_parent: dict) -> list[dict]:
    found: dict[str, str] = {}

    for d in item.get("downloads") or []:
        if isinstance(d, dict) and d.get("file"):
            _collect_pdf_urls(d["file"], d.get("name") or "Product brochure", found, media_by_id, allow_non_pdf=True)

    for field in item.get("meta_data") or []:
        if not isinstance(field, dict):
            continue
        key = str(field.get("key") or "")
        val = field.get("value")
        key_match = re.search(r"catalog(?:ue)?|pdf|datasheet|brochure|download", key, re.I)
        if key_match or (key.lower() == "_elementor_data" and isinstance(val, str) and ".pdf" in val.lower()):
            title = clean_html(key.replace("_", " ")) if key_match else "Product brochure"
            _collect_pdf_urls(val, title or "Product datasheet", found, media_by_id)

    for text_field in (item.get("description") or "", item.get("short_description") or ""):
        _collect_pdf_urls(str(text_field), "Product datasheet", found, media_by_id)

    for m in media_by_parent.get(str(item.get("id")), []):
        if m.get("source_url"):
            t = clean_html((m.get("title") or {}).get("rendered", "")) or "Product document"
            _collect_pdf_urls(m["source_url"], t, found, media_by_id, allow_non_pdf=True)

    if not found and item.get("permalink"):
        for doc in extract_html_pdf_documents(item.get("permalink"), f"{clean_html(item.get('name', '')) or 'Product'} Brochure"):
            found.setdefault(doc["url"][:1000], doc["title"][:180])

    return [{"title": t, "url": u} for u, t in list(found.items())[:24]]


def sync_all():
    if not CK or not CS or not SUPABASE_KEY:
        raise RuntimeError("Configure WORDPRESS_CONSUMER_KEY, WORDPRESS_CONSUMER_SECRET, and SUPABASE_SERVICE_ROLE_KEY in backend/.env")

    print("=== 1. FETCHING WORDPRESS CATEGORIES & PDF MEDIA ===")
    wp_categories = fetch_wp_all("wc/v3/products/categories", {"hide_empty": "false"})
    wp_media = fetch_wp_all("wp/v2/media", {"mime_type": "application/pdf"}, authenticated=False, page_size=100)
    media_by_id = {str(m.get("id")): m for m in wp_media if m.get("id") is not None}
    media_by_parent: dict[str, list] = {}
    for m in wp_media:
        parent = str(m.get("post") if m.get("post") is not None else m.get("parent") or "")
        if parent:
            media_by_parent.setdefault(parent, []).append(m)

    cat_rows = []
    cat_catalogues = []
    for item in wp_categories:
        wp_id = str(item.get("id"))
        name = clean_html(item.get("name", ""))
        slug = str(item.get("slug") or f"cat-{wp_id}")[:180]
        desc = clean_html(item.get("description", ""))
        img = item.get("image", {})
        img_url = to_https_url(img.get("src")) if isinstance(img, dict) else None
        cat_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"enertech-cat-{wp_id}"))
        cat_rows.append({
            "id": cat_id,
            "wordpress_source_id": wp_id,
            "name": name,
            "slug": slug,
            "description": desc or None,
            "sort_order": int(item.get("menu_order") or 0),
            "image_url": img_url,
            "is_published": True,
        })
        cat_found: dict[str, str] = {}
        _collect_pdf_urls(item.get("description") or "", f"{name} Catalogue PDF", cat_found, media_by_id)
        for mf in item.get("meta_data") or []:
            if isinstance(mf, dict):
                _collect_pdf_urls(mf.get("value"), f"{name} Catalogue PDF", cat_found, media_by_id)
        if not cat_found and _ORIGIN and slug:
            for doc in extract_html_pdf_documents(f"{_ORIGIN}/product-category/{slug}/", f"{name} Catalogue PDF"):
                cat_found[doc["url"][:1000]] = doc["title"][:180]
        if cat_found:
            first_url, first_title = next(iter(cat_found.items()))
            cat_catalogues.append({
                "category_key": slug,
                "category_id": cat_id,
                "wordpress_category_id": wp_id,
                "title": first_title,
                "catalog_pdf_url": first_url,
            })

    req = urllib.request.Request(
        f"{SUPABASE_URL}/product_categories?on_conflict=wordpress_source_id",
        headers=SUPABASE_HEADERS,
        data=json.dumps(cat_rows).encode("utf-8"),
    )
    with urllib.request.urlopen(req) as resp:
        saved_cats = json.loads(resp.read().decode())
        print(f"Upserted {len(saved_cats)} categories in Supabase!")

    with urllib.request.urlopen(urllib.request.Request(f"{SUPABASE_URL}/product_categories?select=id,wordpress_source_id", headers=SUPABASE_HEADERS)) as resp:
        db_cats = json.loads(resp.read().decode())
        wp_to_cat_id = {c["wordpress_source_id"]: c["id"] for c in db_cats if c.get("wordpress_source_id")}

    if cat_catalogues:
        mapped_cat_catalogues = [
            {**entry, "category_id": wp_to_cat_id.get(entry["wordpress_category_id"], entry["category_id"])}
            for entry in cat_catalogues
        ]
        cat_req = urllib.request.Request(
            f"{SUPABASE_URL}/product_category_catalogues?on_conflict=category_key",
            headers=SUPABASE_HEADERS,
            data=json.dumps(mapped_cat_catalogues).encode("utf-8"),
        )
        with urllib.request.urlopen(cat_req) as resp:
            saved_cat_pdfs = json.loads(resp.read().decode())
            print(f"Upserted {len(saved_cat_pdfs)} category catalogues in Supabase!")

    # Load existing product documents so we NEVER wipe previously mapped PDFs on future syncs
    with urllib.request.urlopen(urllib.request.Request(f"{SUPABASE_URL}/products?select=wordpress_source_id,documents&limit=500", headers=SUPABASE_HEADERS)) as resp:
        existing_docs_by_wp_id = {
            p["wordpress_source_id"]: p["documents"]
            for p in json.loads(resp.read().decode())
            if p.get("wordpress_source_id") and p.get("documents")
        }

    print("=== 2. FETCHING WORDPRESS PRODUCTS ===")
    wp_products = fetch_wp_all("wc/v3/products", {"status": "publish"})
    default_cat_id = next(iter(wp_to_cat_id.values()), None)
    prod_rows = []
    for item in wp_products:
        wp_id = str(item.get("id"))
        name = clean_html(item.get("name", ""))
        slug = str(item.get("slug") or f"product-{wp_id}")[:180]
        sku = str(item.get("sku") or "").strip() or None
        summary = clean_html(item.get("short_description", ""))[:500] or None
        desc = clean_html(item.get("description", "")) or None

        assigned_cat_id = default_cat_id
        for c in item.get("categories", []):
            cid = str(c.get("id"))
            if cid in wp_to_cat_id:
                assigned_cat_id = wp_to_cat_id[cid]
                break

        images = item.get("images", [])
        main_img = to_https_url(images[0].get("src")) if images and isinstance(images[0], dict) else None
        gallery = [u for img in images[1:] if isinstance(img, dict) and (u := to_https_url(img.get("src")))]

        raw_price = item.get("price") or item.get("regular_price")
        price_minor = None
        if raw_price:
            try:
                price_minor = int(Decimal(str(raw_price)) * 100)
            except Exception:
                price_minor = None

        stock_status = str(item.get("stock_status") or "instock")
        if stock_status not in ("instock", "outofstock", "onbackorder"):
            stock_status = "instock"

        incoming_docs = extract_pdf_documents(item, media_by_id, media_by_parent)
        docs = incoming_docs or existing_docs_by_wp_id.get(wp_id, [])

        specs = {}
        for attr in item.get("attributes", []):
            aname = clean_html(attr.get("name", ""))
            options = attr.get("options", [])
            if aname and options:
                specs[aname] = options[0] if len(options) == 1 else options

        prod_rows.append({
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"enertech-prod-{wp_id}")),
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
            "wordpress_source_url": to_https_url(item.get("permalink")) or item.get("permalink"),
            "is_published": True,
        })

    total_saved = 0
    for i in range(0, len(prod_rows), 50):
        batch = prod_rows[i:i + 50]
        req = urllib.request.Request(
            f"{SUPABASE_URL}/products?on_conflict=wordpress_source_id",
            headers=SUPABASE_HEADERS,
            data=json.dumps(batch).encode("utf-8"),
        )
        with urllib.request.urlopen(req) as resp:
            saved = json.loads(resp.read().decode())
            total_saved += len(saved)
            print(f"Upserted batch {i // 50 + 1}: {len(saved)} products (total: {total_saved})")

    print(f"=== COMPLETED! {len(cat_rows)} categories and {total_saved} products synced into Supabase! ===")


if __name__ == "__main__":
    sync_all()
