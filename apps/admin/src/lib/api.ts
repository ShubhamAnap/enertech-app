import type { User } from "firebase/auth";

export type Category = {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  sort_order: number;
  image_url: string | null;
  wordpress_source_id: string | null;
  cms_locked?: boolean;
  product_count?: number;
  is_published: boolean;
  has_draft: boolean;
  catalog_pdf_url?: string | null;
  catalog_pdf_title?: string | null;
  published_payload?: Record<string, unknown> | null;
};

export type ProductDocument = { title: string; url: string };

export type Product = {
  id: string;
  category_id: string;
  category_ids: string[];
  app_collection_ids: string[];
  wordpress_tag_ids: string[];
  slug: string;
  name: string;
  model_code: string | null;
  summary: string | null;
  description: string | null;
  applications: string[];
  features: string[];
  specifications: Record<string, unknown>;
  image_url: string | null;
  gallery_images: string[];
  price_minor: number | null;
  currency_code: string;
  currency_minor_unit: number;
  stock_status: "instock" | "outofstock" | "onbackorder" | "unknown";
  stock_quantity: number | null;
  documents: ProductDocument[];
  own_documents: ProductDocument[];
  catalog_pdf_url?: string | null;
  catalog_pdf_source?: "product" | "category" | "none";
  wordpress_source_id: string | null;
  wordpress_source_url: string | null;
  category_override?: boolean;
  documents_override?: boolean;
  source_reference: string | null;
  is_published: boolean;
  has_draft: boolean;
  updated_at: string;
  published_payload?: Record<string, unknown> | null;
};

export type CatalogueSummary = {
  products_total: number;
  products_unassigned: number;
  products_published: number;
  products_missing_pdf: number;
  products_category_overridden: number;
  products_pdf_overridden: number;
  categories_total: number;
  categories_published: number;
  categories_hidden: number;
  categories_empty: number;
  categories_missing_pdf: number;
  open_service_requests: number;
  open_quote_requests: number;
  open_contact_inquiries: number;
  customers_total: number;
};

export type CategoryCatalogue = {
  id: string;
  category_key: string;
  category_id: string | null;
  wordpress_category_id: string | null;
  title: string;
  catalog_pdf_url: string;
  source: string;
  updated_at: string;
};

export type ProductPage = { items: Product[]; total: number; limit: number; offset: number };
export type ContentEnvelope = { key: string; draft_payload: Record<string, unknown>; published_payload: Record<string, unknown> | null; draft_revision: number; published_revision: number | null; updated_at: string | null };
export type CustomerRequest = { id: string; kind: "service" | "quote" | "warranty" | "amc"; status: string; payload: Record<string, unknown>; resolution_note: string | null; created_at: string; updated_at: string; customer_uid: string; customer_email: string; assigned_to: string | null; customer_name?: string | null; customer_phone?: string | null; customer_company?: string | null; customer_location?: string | null };
export type ContactInquiry = { id: string; name: string; email: string; phone: string; company_name: string | null; subject: string | null; message: string; inquiry_type: string; status: "new" | "in_progress" | "waiting_for_customer" | "resolved" | "closed"; notes: string | null; created_at: string; updated_at: string };
export type KnowledgeArticle = { id: string; slug: string; title: string; category: string; answer: string; image_urls: string[]; video_urls: string[]; source_reference: string | null; sort_order: number; is_published: boolean; has_draft: boolean };
export type CustomerProfile = { id: string; customer_type: "end_user" | "reseller" | "epc" | "distributor"; name: string; mobile_number: string; email: string; location: string; company_name: string | null; gst_number: string | null; created_at: string; updated_at: string };
export type AdminAccount = { id: string; firebase_uid: string; email: string | null; display_name: string | null; role: "content_editor" | "admin" | "super_admin"; is_active: boolean; created_at: string; updated_at: string };
export type AuditEvent = { id: string; actor_uid: string; action: string; entity_type: string; entity_id: string; change_summary: Record<string, unknown>; created_at: string };
export type AdminMediaAsset = { url: string; path: string; bucket: string; content_type: string; size_bytes: number };

export function getEffectiveApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    const host = window.location.hostname;
    const isLocalhost = host === "localhost" || host === "127.0.0.1";
    // In production, send browser requests through the same-origin Next.js
    // rewrite. This avoids CORS and API-certificate mismatches in browsers;
    // the CMS server forwards the request over Coolify's private network.
    if (!isLocalhost) return `${window.location.origin}/backend-api/api/v1`;

    const envUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "");
    if (envUrl) return envUrl;
  }
  return process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000/api/v1";
}

async function responseError(response: Response): Promise<Error> {
  const body = (await response.json().catch(() => null)) as { detail?: string | Array<{ msg?: string }> } | null;
  if (typeof body?.detail === "string") return new Error(body.detail);
  if (Array.isArray(body?.detail)) return new Error(body.detail.map((item) => item.msg || "Invalid value").join(", "));
  return new Error(`Request failed (${response.status}).`);
}

export async function api<T>(user: User, path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${getEffectiveApiBaseUrl()}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      Authorization: `Bearer ${await user.getIdToken()}`,
      ...init.headers,
    },
    cache: "no-store",
  });
  if (!response.ok) throw await responseError(response);
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function uploadMedia(user: User, file: File): Promise<AdminMediaAsset> {
  const body = new FormData();
  body.append("file", file);
  const path = file.type.startsWith("video/") ? "upload-video" : "upload";
  const response = await fetch(`${getEffectiveApiBaseUrl()}/admin/media/${path}`, {
    method: "POST",
    headers: { Accept: "application/json", Authorization: `Bearer ${await user.getIdToken()}` },
    body,
    cache: "no-store",
  });
  if (!response.ok) throw await responseError(response);
  return response.json() as Promise<AdminMediaAsset>;
}
