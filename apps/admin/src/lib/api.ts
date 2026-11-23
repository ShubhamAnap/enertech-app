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

export async function api<T>(user: User, path: string, init: RequestInit = {}): Promise<T> {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "");
  if (!base) throw new Error("Set NEXT_PUBLIC_API_BASE_URL to connect the CMS API.");
  const token = await user.getIdToken();
  const response = await fetch(`${base}${path}`, {
    ...init,
    headers: { Accept: "application/json", "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...init.headers },
    cache: "no-store",
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Request failed (${response.status}).`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function uploadMedia(user: User, file: File): Promise<AdminMediaAsset> {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "");
  if (!base) throw new Error("Set NEXT_PUBLIC_API_BASE_URL to connect the CMS API.");
  const body = new FormData();
  body.append("file", file);
  const response = await fetch(`${base}/admin/media/upload`, {
    method: "POST",
    headers: { Accept: "application/json", Authorization: `Bearer ${await user.getIdToken()}` },
    body,
    cache: "no-store",
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `Upload failed (${response.status}).`);
  }
  return response.json() as Promise<AdminMediaAsset>;
}
