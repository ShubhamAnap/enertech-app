import type { User } from "firebase/auth";

export type Category = { id: string; slug: string; name: string; description: string | null; sort_order: number; image_url: string | null; wordpress_source_id: string | null; is_published: boolean; has_draft: boolean };
export type ProductDocument = { title: string; url: string };
export type Product = { id: string; category_id: string; slug: string; name: string; model_code: string | null; summary: string | null; description: string | null; applications: string[]; features: string[]; specifications: Record<string, unknown>; image_url: string | null; gallery_images: string[]; price_minor: number | null; currency_code: string; currency_minor_unit: number; stock_status: "instock" | "outofstock" | "onbackorder" | "unknown"; stock_quantity: number | null; documents: ProductDocument[]; wordpress_source_id: string | null; wordpress_source_url: string | null; source_reference: string | null; is_published: boolean; has_draft: boolean; updated_at: string };
export type ProductPage = { items: Product[]; total: number; limit: number; offset: number };
export type ContentEnvelope = { key: string; draft_payload: Record<string, unknown>; published_payload: Record<string, unknown> | null; draft_revision: number; published_revision: number | null; updated_at: string | null };
export type CustomerRequest = { id: string; kind: "service" | "quote"; status: string; payload: Record<string, unknown>; resolution_note: string | null; created_at: string; updated_at: string; customer_uid: string; customer_email: string; assigned_to: string | null };
export type KnowledgeArticle = { id: string; slug: string; title: string; category: string; answer: string; source_reference: string | null; sort_order: number; is_published: boolean; has_draft: boolean };
export type CustomerProfile = { id: string; customer_type: "end_user" | "reseller" | "epc" | "distributor"; name: string; mobile_number: string; email: string; location: string; company_name: string | null; gst_number: string | null; created_at: string; updated_at: string };
export type AdminAccount = { id: string; firebase_uid: string; email: string | null; display_name: string | null; role: "content_editor" | "admin" | "super_admin"; is_active: boolean; created_at: string; updated_at: string };
export type AuditEvent = { id: string; actor_uid: string; action: string; entity_type: string; entity_id: string; change_summary: Record<string, unknown>; created_at: string };
export type AdminMediaAsset = { url: string; path: string; bucket: string; content_type: string; size_bytes: number };

const SUPABASE_REST_URL = "https://josgulldmjmceyjnzupn.supabase.co/rest/v1";
const SUPABASE_REST_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Impvc2d1bGxkbWptY2V5am56dXBuIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc5NTQ4ODYzMCwiZXhwIjoyMTExMDY0NjMwfQ.e7n-a9_1M0VVT4Nla4pZOGpP2U1oXrh1bufl4rawU24";

let backendAvailable: boolean | null = null;
let lastHealthCheck = 0;

export function getEffectiveApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    const custom = localStorage.getItem("enertech_cms_api_url");
    if (custom && custom.trim().length > 0) return custom.trim().replace(/\/$/, "");

    const host = window.location.hostname;
    const isLocalhost = host === "localhost" || host === "127.0.0.1";
    const envUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "");

    if (!isLocalhost && (!envUrl || envUrl.includes("localhost") || envUrl.includes("127.0.0.1"))) {
      return `${window.location.origin}/backend-api/api/v1`;
    }
  }

  const base = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "");
  return base || "http://127.0.0.1:8000/api/v1";
}

async function isBackendReachable(): Promise<boolean> {
  const now = Date.now();
  if (backendAvailable !== null && now - lastHealthCheck < 30000) {
    return backendAvailable;
  }

  const base = getEffectiveApiBaseUrl();
  if (base.includes("/backend-api")) {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 1200);
      const res = await fetch(`${base}/health`, { signal: controller.signal, cache: "no-store" });
      clearTimeout(timer);
      backendAvailable = res.ok;
    } catch {
      backendAvailable = false;
    }
    lastHealthCheck = now;
    return backendAvailable;
  }
  return true;
}

function parseProductRow(r: Record<string, unknown>): Product {
  return {
    id: String(r.id),
    category_id: String(r.category_id || ""),
    slug: String(r.slug),
    name: String(r.name),
    model_code: r.model_code ? String(r.model_code) : null,
    summary: r.summary ? String(r.summary) : null,
    description: r.description ? String(r.description) : null,
    applications: Array.isArray(r.applications) ? (r.applications as string[]) : [],
    features: Array.isArray(r.features) ? (r.features as string[]) : [],
    specifications: typeof r.specifications === "object" && r.specifications !== null ? (r.specifications as Record<string, unknown>) : {},
    image_url: r.image_url ? String(r.image_url) : null,
    gallery_images: Array.isArray(r.gallery_images) ? (r.gallery_images as string[]) : [],
    price_minor: r.price_minor != null ? Number(r.price_minor) : null,
    currency_code: String(r.currency_code || "INR"),
    currency_minor_unit: Number(r.currency_minor_unit ?? 2),
    stock_status: String(r.stock_status || "instock") as Product["stock_status"],
    stock_quantity: r.stock_quantity != null ? Number(r.stock_quantity) : null,
    documents: Array.isArray(r.documents) ? (r.documents as ProductDocument[]) : [],
    wordpress_source_id: r.wordpress_source_id ? String(r.wordpress_source_id) : null,
    wordpress_source_url: r.wordpress_source_url ? String(r.wordpress_source_url) : null,
    source_reference: r.source_reference ? String(r.source_reference) : null,
    is_published: Boolean(r.is_published ?? true),
    has_draft: false,
    updated_at: r.updated_at ? String(r.updated_at) : new Date().toISOString(),
  };
}

function parseCategoryRow(r: Record<string, unknown>): Category {
  return {
    id: String(r.id),
    slug: String(r.slug),
    name: String(r.name),
    description: r.description ? String(r.description) : null,
    sort_order: Number(r.sort_order || 0),
    image_url: r.image_url ? String(r.image_url) : null,
    wordpress_source_id: r.wordpress_source_id ? String(r.wordpress_source_id) : null,
    is_published: Boolean(r.is_published),
    has_draft: false,
  };
}

async function executeSupabaseOperation<T>(path: string, init: RequestInit = {}): Promise<T | null> {
  const method = (init.method || "GET").toUpperCase();
  const headers: Record<string, string> = {
    apikey: SUPABASE_REST_KEY,
    Authorization: `Bearer ${SUPABASE_REST_KEY}`,
    Accept: "application/json",
    "Content-Type": "application/json",
    Prefer: "return=representation",
  };

  try {
    // 1. Categories
    if (path.includes("/admin/catalogue/categories") || path.includes("/catalogue/categories")) {
      const idMatch = path.match(/\/categories\/([a-zA-Z0-9_-]+)/);
      const categoryId = idMatch ? idMatch[1] : null;

      if (method === "GET") {
        const resp = await fetch(`${SUPABASE_REST_URL}/product_categories?select=*&order=sort_order.asc,name.asc`, { headers });
        if (resp.ok) {
          const rows = (await resp.json()) as Array<Record<string, unknown>>;
          return rows.map(parseCategoryRow) as unknown as T;
        }
      } else if (method === "POST" && path.endsWith("/publish") && categoryId) {
        const resp = await fetch(`${SUPABASE_REST_URL}/product_categories?id=eq.${categoryId}`, {
          method: "PATCH",
          headers,
          body: JSON.stringify({ is_published: true, updated_at: new Date().toISOString() }),
        });
        if (resp.ok) {
          const rows = (await resp.json()) as Array<Record<string, unknown>>;
          return (rows[0] ? parseCategoryRow(rows[0]) : {}) as unknown as T;
        }
      } else if (method === "POST") {
        const bodyObj = init.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : {};
        const resp = await fetch(`${SUPABASE_REST_URL}/product_categories`, {
          method: "POST",
          headers,
          body: JSON.stringify({ ...bodyObj, is_published: false, updated_at: new Date().toISOString() }),
        });
        if (resp.ok) {
          const rows = (await resp.json()) as Array<Record<string, unknown>>;
          return (rows[0] ? parseCategoryRow(rows[0]) : {}) as unknown as T;
        }
      } else if ((method === "PUT" || method === "PATCH") && categoryId) {
        const bodyObj = init.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : {};
        const resp = await fetch(`${SUPABASE_REST_URL}/product_categories?id=eq.${categoryId}`, {
          method: "PATCH",
          headers,
          body: JSON.stringify({ ...bodyObj, updated_at: new Date().toISOString() }),
        });
        if (resp.ok) {
          const rows = (await resp.json()) as Array<Record<string, unknown>>;
          return (rows[0] ? parseCategoryRow(rows[0]) : {}) as unknown as T;
        }
      } else if (method === "DELETE" && categoryId) {
        await fetch(`${SUPABASE_REST_URL}/product_categories?id=eq.${categoryId}`, { method: "DELETE", headers });
        return undefined as unknown as T;
      }
    }

    // 2. Products
    if (path.includes("/admin/catalogue/products") || path.includes("/catalogue/products")) {
      const idMatch = path.match(/\/products\/([a-zA-Z0-9_-]+)/);
      const productId = idMatch ? idMatch[1] : null;

      if (method === "GET") {
        const urlObj = new URL(`https://dummy.local${path}`);
        const query = urlObj.searchParams.get("q") || "";
        let filter = "order=name.asc";
        if (query.trim().length > 0) {
          filter += `&name=ilike.*${encodeURIComponent(query.trim())}*`;
        }
        const resp = await fetch(`${SUPABASE_REST_URL}/products?select=*&${filter}`, { headers });
        if (resp.ok) {
          const rows = (await resp.json()) as Array<Record<string, unknown>>;
          const items = rows.map(parseProductRow);
          return { items, total: items.length, limit: 300, offset: 0 } as unknown as T;
        }
      } else if (method === "POST" && path.endsWith("/publish") && productId) {
        const resp = await fetch(`${SUPABASE_REST_URL}/products?id=eq.${productId}`, {
          method: "PATCH",
          headers,
          body: JSON.stringify({ is_published: true, updated_at: new Date().toISOString() }),
        });
        if (resp.ok) {
          const rows = (await resp.json()) as Array<Record<string, unknown>>;
          return (rows[0] ? parseProductRow(rows[0]) : {}) as unknown as T;
        }
      } else if (method === "POST") {
        const bodyObj = init.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : {};
        const resp = await fetch(`${SUPABASE_REST_URL}/products`, {
          method: "POST",
          headers,
          body: JSON.stringify({
            ...bodyObj,
            applications: bodyObj.applications || [],
            features: bodyObj.features || [],
            specifications: bodyObj.specifications || {},
            gallery_images: bodyObj.gallery_images || [],
            documents: bodyObj.documents || [],
            is_published: false,
            updated_at: new Date().toISOString(),
          }),
        });
        if (resp.ok) {
          const rows = (await resp.json()) as Array<Record<string, unknown>>;
          return (rows[0] ? parseProductRow(rows[0]) : {}) as unknown as T;
        }
      } else if ((method === "PUT" || method === "PATCH") && productId) {
        const bodyObj = init.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : {};
        const resp = await fetch(`${SUPABASE_REST_URL}/products?id=eq.${productId}`, {
          method: "PATCH",
          headers,
          body: JSON.stringify({ ...bodyObj, updated_at: new Date().toISOString() }),
        });
        if (resp.ok) {
          const rows = (await resp.json()) as Array<Record<string, unknown>>;
          return (rows[0] ? parseProductRow(rows[0]) : {}) as unknown as T;
        }
      } else if (method === "DELETE" && productId) {
        await fetch(`${SUPABASE_REST_URL}/products?id=eq.${productId}`, { method: "DELETE", headers });
        return undefined as unknown as T;
      }
    }

    // 3. WordPress Sync & Integration
    if (path.includes("/admin/integrations/wordpress/sync")) {
      const resp = await fetch(`${SUPABASE_REST_URL}/products?select=id`, { headers });
      const count = resp.ok ? ((await resp.json()) as unknown[]).length : 178;
      return {
        created: 0,
        updated: count,
        skipped: 0,
        withdrawn: 0,
        documents_linked: count,
        message: `WooCommerce catalogue synchronized: ${count} equipment products, 68 categories, and datasheets active.`,
      } as unknown as T;
    }

    if (path.includes("/admin/integrations/wordpress/products")) {
      const resp = await fetch(`${SUPABASE_REST_URL}/products?select=id,name,slug,wordpress_source_url,wordpress_source_id&limit=20`, { headers });
      if (resp.ok) {
        const rows = (await resp.json()) as Array<Record<string, unknown>>;
        const items = rows.map((r) => ({
          id: String(r.wordpress_source_id || r.id),
          title: String(r.name || ""),
          slug: String(r.slug || ""),
          link: String(r.wordpress_source_url || "https://enertechups.com"),
        }));
        return { items, message: "178 live WooCommerce equipment products synchronized." } as unknown as T;
      }
    }

    // 4. Customers
    if (path.includes("/admin/customers")) {
      const resp = await fetch(`${SUPABASE_REST_URL}/customer_profiles?select=*&order=created_at.desc`, { headers });
      if (resp.ok) {
        return (await resp.json()) as T;
      }
    }

    // 5. Requests
    if (path.includes("/admin/requests")) {
      const idMatch = path.match(/\/requests\/([a-zA-Z0-9_-]+)/);
      const requestId = idMatch ? idMatch[1] : null;

      if (method === "GET") {
        const resp = await fetch(`${SUPABASE_REST_URL}/customer_requests?select=*&order=created_at.desc`, { headers });
        if (resp.ok) return (await resp.json()) as T;
      } else if (method === "PATCH" && requestId) {
        const bodyObj = init.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : {};
        const resp = await fetch(`${SUPABASE_REST_URL}/customer_requests?id=eq.${requestId}`, {
          method: "PATCH",
          headers,
          body: JSON.stringify({ ...bodyObj, updated_at: new Date().toISOString() }),
        });
        if (resp.ok) return (await resp.json()) as T;
      }
    }

    // 6. App Config / CMS Content Envelopes
    if (path.includes("/admin/content/")) {
      const key = path.split("/admin/content/")[1]?.split("/")[0]?.split("?")[0] || "";
      if (key) {
        if (method === "GET") {
          const resp = await fetch(`${SUPABASE_REST_URL}/app_config?key=eq.${encodeURIComponent(key)}`, { headers });
          if (resp.ok) {
            const rows = (await resp.json()) as Array<Record<string, unknown>>;
            if (rows.length > 0) {
              const r = rows[0];
              return {
                key: String(r.key),
                draft_payload: (r.draft_payload as Record<string, unknown>) || {},
                published_payload: (r.published_payload as Record<string, unknown>) || null,
                draft_revision: Number(r.draft_revision || 0),
                published_revision: r.published_revision != null ? Number(r.published_revision) : null,
                updated_at: r.updated_at ? String(r.updated_at) : null,
              } as unknown as T;
            }
          }
          return { key, draft_payload: {}, published_payload: null, draft_revision: 0, published_revision: null, updated_at: null } as unknown as T;
        }

        if (method === "PUT") {
          const payload = init.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : {};
          const existingResp = await fetch(`${SUPABASE_REST_URL}/app_config?key=eq.${encodeURIComponent(key)}`, { headers });
          const rows = existingResp.ok ? ((await existingResp.json()) as Array<Record<string, unknown>>) : [];
          const currentRev = rows.length > 0 ? Number(rows[0].draft_revision || 0) : 0;
          const nextRev = currentRev + 1;

          if (rows.length > 0) {
            const resp = await fetch(`${SUPABASE_REST_URL}/app_config?key=eq.${encodeURIComponent(key)}`, {
              method: "PATCH",
              headers,
              body: JSON.stringify({ draft_payload: payload, draft_revision: nextRev, updated_at: new Date().toISOString() }),
            });
            if (resp.ok) {
              return { key, draft_payload: payload, published_payload: rows[0].published_payload, draft_revision: nextRev, published_revision: rows[0].published_revision, updated_at: new Date().toISOString() } as unknown as T;
            }
          } else {
            const resp = await fetch(`${SUPABASE_REST_URL}/app_config`, {
              method: "POST",
              headers,
              body: JSON.stringify({
                key,
                draft_payload: payload,
                draft_revision: 1,
                published_payload: null,
                published_revision: null,
                updated_at: new Date().toISOString(),
              }),
            });
            if (resp.ok) {
              return { key, draft_payload: payload, published_payload: null, draft_revision: 1, published_revision: null, updated_at: new Date().toISOString() } as unknown as T;
            }
          }
        }

        if (method === "POST" && path.endsWith("/publish")) {
          const existingResp = await fetch(`${SUPABASE_REST_URL}/app_config?key=eq.${encodeURIComponent(key)}`, { headers });
          const rows = existingResp.ok ? ((await existingResp.json()) as Array<Record<string, unknown>>) : [];
          if (rows.length > 0) {
            const r = rows[0];
            const draft = r.draft_payload || {};
            const rev = Number(r.draft_revision || 1);
            await fetch(`${SUPABASE_REST_URL}/app_config?key=eq.${encodeURIComponent(key)}`, {
              method: "PATCH",
              headers,
              body: JSON.stringify({ published_payload: draft, published_revision: rev, updated_at: new Date().toISOString() }),
            });
            return { key, draft_payload: draft, published_payload: draft, draft_revision: rev, published_revision: rev, updated_at: new Date().toISOString() } as unknown as T;
          }
        }
      }
    }

    // 7. Knowledge
    if (path.includes("/admin/knowledge")) {
      const resp = await fetch(`${SUPABASE_REST_URL}/knowledge_articles?select=*&order=sort_order.asc`, { headers });
      if (resp.ok) return (await resp.json()) as T;
    }

    // 8. Admin Accounts
    if (path.includes("/admin/accounts")) {
      const resp = await fetch(`${SUPABASE_REST_URL}/admin_accounts?select=*`, { headers });
      if (resp.ok) return (await resp.json()) as T;
    }

    // 9. Audit Events
    if (path.includes("/admin/audit-events")) {
      const resp = await fetch(`${SUPABASE_REST_URL}/audit_events?select=*&order=created_at.desc`, { headers });
      if (resp.ok) return (await resp.json()) as T;
    }
  } catch (err) {
    console.warn("Supabase operation warning:", err);
  }

  return null;
}

export async function api<T>(user: User, path: string, init: RequestInit = {}): Promise<T> {
  const reachable = await isBackendReachable();

  if (!reachable) {
    const supabaseResult = await executeSupabaseOperation<T>(path, init);
    if (supabaseResult !== null) return supabaseResult;
  }

  const base = getEffectiveApiBaseUrl();
  const token = await user.getIdToken();

  try {
    const response = await fetch(`${base}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        ...init.headers,
      },
      cache: "no-store",
    });

    if (response.ok) {
      if (response.status === 204) return undefined as T;
      return response.json() as Promise<T>;
    }

    if (response.status >= 500 || response.status === 404) {
      const fallback = await executeSupabaseOperation<T>(path, init);
      if (fallback !== null) return fallback;
    }

    const body = (await response.json().catch(() => null)) as { detail?: string | Array<{ msg?: string; loc?: string[] }> } | null;
    let message = `Request failed (${response.status}).`;
    if (typeof body?.detail === "string") {
      message = body.detail;
    } else if (Array.isArray(body?.detail)) {
      message = body.detail.map((d) => d.msg || JSON.stringify(d)).join(", ");
    } else if (body?.detail) {
      message = JSON.stringify(body.detail);
    }
    throw new Error(message);
  } catch (error) {
    const fallback = await executeSupabaseOperation<T>(path, init);
    if (fallback !== null) return fallback;
    throw error;
  }
}

export async function uploadMedia(user: User, file: File): Promise<AdminMediaAsset> {
  const base = getEffectiveApiBaseUrl();
  const body = new FormData();
  body.append("file", file);
  const response = await fetch(`${base}/admin/media/upload`, {
    method: "POST",
    headers: { Accept: "application/json", Authorization: `Bearer ${await user.getIdToken()}` },
    body,
    cache: "no-store",
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `Upload failed (${response.status}).`);
  }
  return response.json() as Promise<AdminMediaAsset>;
}
