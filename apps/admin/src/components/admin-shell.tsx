"use client";

import { signOut, type User } from "firebase/auth";
import Image from "next/image";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { api, uploadMedia, type AdminAccount, type AuditEvent, type CatalogueSummary, type Category, type CategoryCatalogue, type ContactInquiry, type ContentEnvelope, type CustomerProfile, type CustomerRequest, type KnowledgeArticle, type Product } from "@/lib/api";
import { getFirebaseAuth } from "@/lib/firebase";
import { AssignProductsModal, CollectionCataloguePdfModal, CreateCollectionModal, ProductCategoryOverrideModal, ProductPdfOverrideModal } from "./catalogue-modals";

type Section = "overview" | "products" | "categories" | "app_content" | "wordpress" | "service" | "quotes" | "warranty" | "amc" | "contact_inquiries" | "knowledge" | "customers" | "admins" | "audit";
type AppContentTab = "home" | "contacts" | "solution_finder" | "chat" | "brand";
type WordPressStatus = { configured: boolean; authenticated: boolean; documents_configured: boolean; site: string | null; products_path: string | null; categories_path: string | null; store_api_path: string | null; message: string };
type WordPressSyncSummary = {
  source?: string;
  source_mode?: string;
  fallback_used?: string | null;
  media_fetch_status?: string;
  media_pdf_count?: number;
  matched_by_rest_fields?: number;
  matched_by_wp_media?: number;
  matched_by_html?: number;
  created?: number;
  updated?: number;
  skipped?: number;
  withdrawn?: number;
  categories?: number;
  cms_preserved_category_products?: number;
  cms_preserved_pdf_products?: number;
  documents_linked?: number;
  message?: string;
};
const sectionNames: Record<Section, string> = { overview: "Overview", products: "Products", categories: "Collections", app_content: "App Content", wordpress: "WordPress Sync", service: "Service requests", quotes: "Quote enquiries", warranty: "Warranty registrations", amc: "AMC requests", contact_inquiries: "Contact enquiries", knowledge: "FAQs & knowledge", customers: "Customers", admins: "Admin access", audit: "Audit history" };
const appContentTabs: { key: AppContentTab; title: string }[] = [
  { key: "home", title: "Home screen" },
  { key: "contacts", title: "Contacts & support" },
  { key: "solution_finder", title: "Solution Finder" },
  { key: "chat", title: "Live chat" },
  { key: "brand", title: "Brand identity" },
];
const emptyProduct = { category_id: "", category_ids: [] as string[], slug: "", name: "", model_code: "", summary: "", description: "", applications: [] as string[], features: [] as string[], specifications: {} as Record<string, unknown>, image_url: null as string | null, gallery_images: [] as string[], price_minor: null as number | null, currency_code: "INR", currency_minor_unit: 2, stock_status: "unknown" as Product["stock_status"], stock_quantity: null as number | null, documents: [] as Product["documents"], source_reference: "", wordpress_source_id: null as string | null, wordpress_source_url: null as string | null };
const emptyKnowledge = { slug: "", title: "", category: "General", answer: "", image_urls: [] as string[], video_urls: [] as string[], source_reference: "", sort_order: 0 };

function textValue(value: unknown): string { return value == null ? "" : typeof value === "string" ? value : JSON.stringify(value, null, 2); }
function humanize(key: string): string { return key.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()); }
function catalogPrice(product: Product): string { if (product.price_minor == null) return "—"; const digits = productPriceDigits(product); return new Intl.NumberFormat("en-IN", { style: "currency", currency: product.currency_code, minimumFractionDigits: 0, maximumFractionDigits: digits }).format(product.price_minor / (10 ** digits)); }
function productPriceDigits(product: Pick<Product, "currency_minor_unit">): number { return Math.max(0, Math.min(product.currency_minor_unit, 4)); }
function productDatasheet(product: Pick<Product, "documents" | "catalog_pdf_url" | "catalog_pdf_source" | "wordpress_source_url">): { title: string; url: string; inherited: boolean } | null {
  const inherited = product.catalog_pdf_source === "category";
  const documents = product.documents ?? [];
  const match = documents.find((document) => {
    const url = document.url?.toLowerCase().split(/[?#]/, 1)[0] ?? "";
    const title = document.title?.toLowerCase() ?? "";
    return url.endsWith(".pdf") || /pdf|datasheet|catalogue|brochure/.test(title);
  });
  if (match?.url) return { title: match.title || "Product catalogue PDF", url: match.url, inherited };
  if (product.catalog_pdf_url) return { title: "Collection catalogue PDF", url: product.catalog_pdf_url, inherited: true };
  const sourceUrl = product.wordpress_source_url ?? "";
  return sourceUrl.toLowerCase().split(/[?#]/, 1)[0].endsWith(".pdf")
    ? { title: "Product catalogue PDF", url: sourceUrl, inherited: false }
    : null;
}
function BoltMark({ className = "h-4 w-4" }: { className?: string }) { return <svg aria-hidden="true" focusable="false" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className={className}><path d="M13 2 4 14h7l-1 8 10-12h-7l1-8Z" /></svg>; }
type AdminIconName = "overview" | "product" | "collection" | "import" | "quote" | "service" | "inquiry" | "home" | "contact" | "solution" | "chat" | "brand" | "customer" | "admin" | "audit" | "settings" | "menu" | "table" | "grid" | "document" | "edit" | "delete";
const adminIconPaths: Record<AdminIconName, string[]> = {
  overview: ["M3.5 3.5h7v7h-7z", "M13.5 3.5h7v7h-7z", "M3.5 13.5h7v7h-7z", "M13.5 13.5h7v7h-7z"],
  product: ["m3 7 9-4 9 4-9 4-9-4Z", "M3 7v10l9 4 9-4V7", "M12 11v10", "m7 5 9 4"],
  collection: ["M3.5 3.5h7v7h-7z", "M13.5 3.5h7v7h-7z", "M3.5 13.5h7v7h-7z", "M13.5 13.5h7v7h-7z"],
  import: ["M13 2 4 14h7l-1 8 10-12h-7l1-8Z"],
  quote: ["M6 3.5h9l4 4V20H6z", "M15 3.5V8h4", "M9 12h7", "M9 16h7"],
  service: ["M14.5 6a5 5 0 0 0-6.3 6.3L3 17.5 6.5 21l5.2-5.2A5 5 0 0 0 18 9.5l-3 3-3.5-3.5 3-3Z"],
  inquiry: ["M3 5h18v14H3z", "m3 7 9 6 9-6", "M7 3v2", "M17 3v2"],
  home: ["m3 10 9-7 9 7", "M5 9v11h14V9", "M9 20v-6h6v6"],
  contact: ["M16 20v-1.5a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4V20", "M10 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z", "M17 8h4", "M19 6v4"],
  solution: ["M9 18h6", "M10 22h4", "M8.5 14.5a7 7 0 1 1 7 0c-.9.7-1.5 1.6-1.5 2.5h-4c0-.9-.6-1.8-1.5-2.5Z", "M12 3v1"],
  chat: ["M4 5h16v11H8l-4 4z", "M8 9h8", "M8 12h5"],
  brand: ["M4 4h16v16H4z", "M8 8h8", "M8 12h5", "M8 16h8"],
  customer: ["M16 20v-1.5a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4V20", "M10 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z", "M16 4.2a3.5 3.5 0 0 1 0 6.6", "M20 20v-1.5a4 4 0 0 0-3-3.9"],
  admin: ["M12 3 20 6v5c0 5-3.4 8.3-8 10-4.6-1.7-8-5-8-10V6z", "m9 12 2 2 4-4"],
  audit: ["M7 4h10v17H5V6h2", "M9 4V2h6v2", "M9 10h6", "M9 14h6", "M9 18h4"],
  settings: ["M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Z", "m19.4 15 .1.1 1.4 1.1-1.4 2.4-1.8-.6a7.8 7.8 0 0 1-1.5.9l-.4 1.9h-2.8l-.4-1.9a7.8 7.8 0 0 1-1.5-.9l-1.8.6-1.4-2.4 1.4-1.1a7 7 0 0 1 0-1.8l-1.4-1.1 1.4-2.4 1.8.6a7.8 7.8 0 0 1 1.5-.9l.4-1.9h2.8l.4 1.9a7.8 7.8 0 0 1 1.5.9l1.8-.6 1.4 2.4-1.4 1.1a7 7 0 0 1 0 1.8Z"],
  menu: ["M4 6h16", "M4 12h16", "M4 18h16"],
  table: ["M3 4h18v16H3z", "M3 10h18", "M10 4v16"],
  grid: ["M3.5 3.5h7v7h-7z", "M13.5 3.5h7v7h-7z", "M3.5 13.5h7v7h-7z", "M13.5 13.5h7v7h-7z"],
  document: ["M6 3h9l4 4v14H6z", "M15 3v5h4", "M9 13h7", "M9 17h7"],
  edit: ["m4 16.5-.8 4.3 4.3-.8L19 8.5 15.5 5z", "m13.5 7 3.5 3.5"],
  delete: ["M4 7h16", "M10 11v6", "M14 11v6", "m5 7 1 14h12l1-14", "M9 7V4h6v3"],
};
function AdminIcon({ name, className = "h-4 w-4" }: { name: AdminIconName; className?: string }) { return <svg aria-hidden="true" focusable="false" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className={className}>{adminIconPaths[name].map((path) => <path key={path} d={path} />)}</svg>; }
function stockLabel(status: Product["stock_status"]): string { return ({ instock: "In stock", outofstock: "Out of stock", onbackorder: "On backorder", unknown: "Not provided" })[status]; }
function stockBadgeClass(status: Product["stock_status"]): string { return ({ instock: "badge-success", outofstock: "badge-error", onbackorder: "badge-warning", unknown: "badge-ghost" })[status]; }
const requestTransitions: Record<string, Record<string, string[]>> = {
  service: { submitted: ["in_review", "assigned", "waiting_for_customer", "closed"], in_review: ["assigned", "waiting_for_customer", "resolved", "closed"], assigned: ["in_review", "waiting_for_customer", "resolved", "closed"], waiting_for_customer: ["in_review", "assigned", "resolved", "closed"], resolved: ["closed"], closed: [] },
  quote: { submitted: ["in_review", "assigned", "waiting_for_customer", "quote_preparing", "closed"], in_review: ["assigned", "waiting_for_customer", "quote_preparing", "quote_sent", "closed"], assigned: ["in_review", "waiting_for_customer", "quote_preparing", "quote_sent", "closed"], waiting_for_customer: ["in_review", "assigned", "quote_preparing", "quote_sent", "closed"], quote_preparing: ["waiting_for_customer", "quote_sent", "closed"], quote_sent: ["waiting_for_customer", "closed"], closed: [] },
};
requestTransitions.warranty = requestTransitions.service; requestTransitions.amc = requestTransitions.service;
const requestStatuses: Record<string, string[]> = {
  service: ["submitted", "in_review", "assigned", "waiting_for_customer", "resolved", "closed"],
  quote: ["submitted", "in_review", "assigned", "waiting_for_customer", "quote_preparing", "quote_sent", "closed"],
};

requestStatuses.warranty = requestStatuses.service; requestStatuses.amc = requestStatuses.service;
const requestKindForSection = (section: Section): CustomerRequest["kind"] => section === "service" || section === "warranty" || section === "amc" ? section : "quote";

export default function AdminShell({ user, role }: { user: User; role: string }) {
  const [section, setSection] = useState<Section>("overview");
  const [appContentTab, setAppContentTab] = useState<AppContentTab>("home");
  const [menuOpen, setMenuOpen] = useState(false);
  const [summary, setSummary] = useState<CatalogueSummary | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [categoryCatalogues, setCategoryCatalogues] = useState<CategoryCatalogue[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [productTotal, setProductTotal] = useState(0);
  const [productHasMore, setProductHasMore] = useState(false);
  const [categoryHasMore, setCategoryHasMore] = useState(false);
  const [content, setContent] = useState<ContentEnvelope | null>(null);
  const [contentDraft, setContentDraft] = useState<Record<string, unknown>>({});
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState("");
  const [productViewMode, setProductViewMode] = useState<"table" | "grid">("table");
  const [selectedProductCategory, setSelectedProductCategory] = useState<string>("all");
  const [productStatusFilter, setProductStatusFilter] = useState<"all" | "published" | "draft">("all");
  const [productPdfFilter, setProductPdfFilter] = useState<"all" | "has_pdf" | "missing_pdf">("all");
  const [productSourceFilter, setProductSourceFilter] = useState<"all" | "wp" | "cms" | "overridden">("all");
  const [categoryFilter, setCategoryFilter] = useState<"all" | "visible" | "hidden" | "empty" | "missing_pdf">("all");
  const [customerRoleFilter, setCustomerRoleFilter] = useState<"all" | "end_user" | "reseller" | "epc" | "distributor">("all");
  const [selectedProductIds, setSelectedProductIds] = useState<Set<string>>(new Set());
  const [selectedCategoryIds, setSelectedCategoryIds] = useState<Set<string>>(new Set());
  const [bulkTargetCategoryId, setBulkTargetCategoryId] = useState("");
  const [productForm, setProductForm] = useState<typeof emptyProduct | Product>(emptyProduct);
  const [specificationsText, setSpecificationsText] = useState("{}");
  const [specificationsError, setSpecificationsError] = useState("");
  const [editingProduct, setEditingProduct] = useState<string | null>(null);
  const [collectionEditorTarget, setCollectionEditorTarget] = useState<Category | null>(null);
  const [showCreateCollection, setShowCreateCollection] = useState(false);
  const [showProductForm, setShowProductForm] = useState(false);
  const [docUploadingIndex, setDocUploadingIndex] = useState<number | null>(null);
  const [assignTarget, setAssignTarget] = useState<Category | null>(null);
  const [cataloguePdfTarget, setCataloguePdfTarget] = useState<Category | null>(null);
  const [productPdfTarget, setProductPdfTarget] = useState<Product | null>(null);
  const [productCategoryTarget, setProductCategoryTarget] = useState<Product | null>(null);
  const [knowledgeArticles, setKnowledgeArticles] = useState<KnowledgeArticle[]>([]);
  const [customerProfiles, setCustomerProfiles] = useState<CustomerProfile[]>([]);
  const [adminAccounts, setAdminAccounts] = useState<AdminAccount[]>([]);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [auditQuery, setAuditQuery] = useState("");
  const [auditEntityFilter, setAuditEntityFilter] = useState("all");
  const [adminForm, setAdminForm] = useState({ firebase_uid: "", email: "", display_name: "", role: "content_editor" as AdminAccount["role"], is_active: true });
  const [editingAdminUid, setEditingAdminUid] = useState<string | null>(null);
  const [knowledgeForm, setKnowledgeForm] = useState<typeof emptyKnowledge | KnowledgeArticle>(emptyKnowledge);
  const [knowledgeVideoInput, setKnowledgeVideoInput] = useState("");
  const [knowledgePreview, setKnowledgePreview] = useState(false);
  const [knowledgeSlugTouched, setKnowledgeSlugTouched] = useState(false);
  const [editingKnowledge, setEditingKnowledge] = useState<string | null>(null);
  const [showKnowledgeForm, setShowKnowledgeForm] = useState(false);
  const [knowledgeMediaUploading, setKnowledgeMediaUploading] = useState(false);
  const knowledgeAnswerRef = useRef<HTMLTextAreaElement | null>(null);
  const [wpPreview, setWpPreview] = useState<Array<Record<string, unknown>>>([]);
  const [wpStatus, setWpStatus] = useState<string>("");
  const [lastWpSync, setLastWpSync] = useState<WordPressSyncSummary | null>(null);
  const [wpConnection, setWpConnection] = useState<WordPressStatus | null>(null);
  const [wpConnectionLoading, setWpConnectionLoading] = useState(false);
  const [customerRequests, setCustomerRequests] = useState<CustomerRequest[]>([]);
  const [assignableStaff, setAssignableStaff] = useState<AdminAccount[]>([]);
  const [requestsHasMore, setRequestsHasMore] = useState(false);
  const [requestNotes, setRequestNotes] = useState<Record<string, string>>({});
  const [requestAssignees, setRequestAssignees] = useState<Record<string, string>>({});
  const [requestStatusFilter, setRequestStatusFilter] = useState("all");
  const [requestQuery, setRequestQuery] = useState("");
  const [knowledgeHasMore, setKnowledgeHasMore] = useState(false);
  const [customersHasMore, setCustomersHasMore] = useState(false);
  const [auditHasMore, setAuditHasMore] = useState(false);
  const [contactInquiries, setContactInquiries] = useState<ContactInquiry[]>([]);
  const [inquiryNotes, setInquiryNotes] = useState<Record<string, string>>({});
  const [inquiryStatuses, setInquiryStatuses] = useState<Record<string, ContactInquiry["status"]>>({});
  const [inquiryStatusFilter, setInquiryStatusFilter] = useState("all");
  const [inquiryQuery, setInquiryQuery] = useState("");
  const [inquiryHasMore, setInquiryHasMore] = useState(false);
  const catalogueRequestId = useRef(0);
  const title = sectionNames[section];
  const wpSyncReady = Boolean(wpConnection?.configured && (wpConnection.authenticated || wpConnection.store_api_path));

  const loadWordPressStatus = useCallback(async () => {
    setWpConnectionLoading(true);
    try {
      const status = await api<WordPressStatus>(user, "/admin/integrations/wordpress/status");
      setWpConnection(status);
    } catch {
      setWpConnection(null);
    } finally {
      setWpConnectionLoading(false);
    }
  }, [user]);

  const loadSummary = useCallback(async () => {
    try {
      setSummary(await api<CatalogueSummary>(user, "/admin/catalogue/summary"));
    } catch {
      /* ignore transient summary errors so primary view stays interactive */
    }
  }, [user]);

  const loadCatalogue = useCallback(async (productOffset = 0, categoryOffset = 0, append = false, searchTerm = query) => {
    const requestId = ++catalogueRequestId.current;
    setLoading(true); setError("");
    const [categoriesResult, productsResult, cataloguesResult, summaryResult] = await Promise.allSettled([
      api<Category[]>(user, `/admin/catalogue/categories?limit=500&offset=${categoryOffset}`),
      api<{ items: Product[]; total: number }>(user, `/admin/catalogue/products?limit=500&offset=${productOffset}&q=${encodeURIComponent(searchTerm)}`),
      api<CategoryCatalogue[]>(user, "/admin/catalogue/category-catalogues"),
      api<CatalogueSummary>(user, "/admin/catalogue/summary"),
    ]);
    if (requestId !== catalogueRequestId.current) return;

    const errors: string[] = [];
    if (categoriesResult.status === "fulfilled") {
      setCategories((current) => append ? [...current, ...categoriesResult.value] : categoriesResult.value);
      setCategoryHasMore(categoriesResult.value.length === 500);
    } else {
      if (!append) {
        setCategories([]);
        setCategoryHasMore(false);
      }
      errors.push(`Collections: ${categoriesResult.reason instanceof Error ? categoriesResult.reason.message : "could not be loaded"}`);
    }

    if (productsResult.status === "fulfilled") {
      const page = productsResult.value;
      setProducts((current) => append ? [...current, ...page.items] : page.items);
      setProductTotal(page.total);
      setProductHasMore(productOffset + page.items.length < page.total);
    } else {
      if (!append) {
        setProducts([]);
        setProductTotal(0);
        setProductHasMore(false);
      }
      errors.push(`Products: ${productsResult.reason instanceof Error ? productsResult.reason.message : "could not be loaded"}`);
    }
    if (cataloguesResult.status === "fulfilled") {
      setCategoryCatalogues(cataloguesResult.value);
    }
    if (summaryResult.status === "fulfilled") {
      setSummary(summaryResult.value);
    }
    if (errors.length) setError(errors.join(" "));
    setLoading(false);
  }, [query, user]);

  const loadContent = useCallback(async (key: string) => {
    setLoading(true); setError("");
    try { const envelope = await api<ContentEnvelope>(user, `/admin/app-config/${key}`); setContent(envelope); setContentDraft(envelope.draft_payload); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load app content."); }
    finally { setLoading(false); }
  }, [user]);

  const loadRequests = useCallback(async (kind: CustomerRequest["kind"], offset = 0, append = false) => {
    setLoading(true); setError("");
    if (!append) setCustomerRequests([]);
    try {
      const params = new URLSearchParams({ kind, limit: "100", offset: String(offset), q: requestQuery.trim() });
      if (requestStatusFilter !== "all" && requestStatuses[kind].includes(requestStatusFilter)) params.set("status", requestStatusFilter);
      const rows = await api<CustomerRequest[]>(user, `/admin/requests?${params.toString()}`);
      setCustomerRequests((current) => append ? [...current, ...rows] : rows);
      setRequestAssignees((current) => ({ ...current, ...Object.fromEntries(rows.map((row) => [row.id, row.assigned_to ?? ""])) }));
      setRequestNotes((current) => ({ ...current, ...Object.fromEntries(rows.map((row) => [row.id, row.resolution_note ?? ""])) }));
      setRequestsHasMore(rows.length === 100);
    }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load customer requests."); }
    finally { setLoading(false); }
  }, [requestQuery, requestStatusFilter, user]);

  const loadAssignableStaff = useCallback(async () => {
    try { setAssignableStaff(await api<AdminAccount[]>(user, "/admin/assignable-staff")); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load active request assignees."); }
  }, [user]);

  const loadContactInquiries = useCallback(async (offset = 0, append = false) => {
    setLoading(true); setError("");
    try {
      const params = new URLSearchParams({ limit: "50", offset: String(offset), q: inquiryQuery.trim() });
      if (inquiryStatusFilter !== "all") params.set("status", inquiryStatusFilter);
      const rows = await api<ContactInquiry[]>(user, `/admin/contact-inquiries?${params.toString()}`);
      setContactInquiries((current) => append ? [...current, ...rows] : rows);
      setInquiryNotes((current) => ({ ...current, ...Object.fromEntries(rows.map((row) => [row.id, row.notes ?? ""])) }));
      setInquiryStatuses((current) => ({ ...current, ...Object.fromEntries(rows.map((row) => [row.id, row.status])) }));
      setInquiryHasMore(rows.length === 50);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load contact enquiries."); }
    finally { setLoading(false); }
  }, [inquiryQuery, inquiryStatusFilter, user]);

  const loadKnowledge = useCallback(async (offset = 0, append = false) => {
    setLoading(true); setError("");
    try {
      const rows = await api<KnowledgeArticle[]>(user, `/admin/knowledge?q=${encodeURIComponent(query)}&limit=100&offset=${offset}`);
      setKnowledgeArticles((current) => append ? [...current, ...rows] : rows);
      setKnowledgeHasMore(rows.length === 100);
    }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load support content."); }
    finally { setLoading(false); }
  }, [query, user]);

  const loadCustomers = useCallback(async (offset = 0, append = false) => {
    setLoading(true); setError("");
    try {
      const rows = await api<CustomerProfile[]>(user, `/admin/customers?q=${encodeURIComponent(query)}&limit=100&offset=${offset}`);
      setCustomerProfiles((current) => append ? [...current, ...rows] : rows);
      setCustomersHasMore(rows.length === 100);
    }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load customer profiles."); }
    finally { setLoading(false); }
  }, [query, user]);

  const loadAdmins = useCallback(async () => {
    setLoading(true); setError("");
    try { setAdminAccounts(await api<AdminAccount[]>(user, "/admin/accounts")); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load administrator accounts."); }
    finally { setLoading(false); }
  }, [user]);

  const loadAudit = useCallback(async (offset = 0, append = false) => {
    setLoading(true); setError("");
    try {
      const params = new URLSearchParams({ limit: "100", offset: String(offset), q: auditQuery.trim() });
      if (auditEntityFilter !== "all") params.set("entity_type", auditEntityFilter);
      const rows = await api<AuditEvent[]>(user, `/admin/audit-events?${params.toString()}`);
      setAuditEvents((current) => append ? [...current, ...rows] : rows);
      setAuditHasMore(rows.length === 100);
    }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load audit history."); }
    finally { setLoading(false); }
  }, [auditEntityFilter, auditQuery, user]);

  useEffect(() => {
    const timer = window.setTimeout(() => { if (section === "products" || section === "categories" || section === "overview") void loadCatalogue(); }, 0);
    return () => window.clearTimeout(timer);
  }, [section, loadCatalogue]);
  useEffect(() => {
    const timer = window.setTimeout(() => { void loadSummary(); }, 0);
    return () => window.clearTimeout(timer);
  }, [loadSummary]);
  useEffect(() => {
    const timer = window.setTimeout(() => { if (section === "wordpress") void loadWordPressStatus(); }, 0);
    return () => window.clearTimeout(timer);
  }, [section, loadWordPressStatus]);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (section === "app_content") {
        void loadContent(appContentTab);
        if (appContentTab === "home") void loadCatalogue(0, 0, false, "");
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, [section, appContentTab, loadContent, loadCatalogue]);
  useEffect(() => {
    const timer = window.setTimeout(() => { if (["service", "quotes", "warranty", "amc"].includes(section)) void loadRequests(requestKindForSection(section)); }, 0);
    return () => window.clearTimeout(timer);
  }, [section, loadRequests]);
  useEffect(() => {
    const timer = window.setTimeout(() => { if (["service", "quotes", "warranty", "amc"].includes(section)) void loadAssignableStaff(); }, 0);
    return () => window.clearTimeout(timer);
  }, [section, loadAssignableStaff]);
  useEffect(() => {
    const timer = window.setTimeout(() => { if (section === "contact_inquiries") void loadContactInquiries(); }, 200);
    return () => window.clearTimeout(timer);
  }, [section, loadContactInquiries]);
  useEffect(() => {
    const timer = window.setTimeout(() => { if (section === "knowledge") void loadKnowledge(); }, 0);
    return () => window.clearTimeout(timer);
  }, [section, loadKnowledge]);
  useEffect(() => {
    const timer = window.setTimeout(() => { if ((section === "customers" || section === "overview") && (role === "admin" || role === "super_admin")) void loadCustomers(); }, 0);
    return () => window.clearTimeout(timer);
  }, [section, loadCustomers, role]);
  useEffect(() => {
    const timer = window.setTimeout(() => { if (section === "admins") void loadAdmins(); }, 0);
    return () => window.clearTimeout(timer);
  }, [section, loadAdmins]);
  useEffect(() => {
    const timer = window.setTimeout(() => { if (section === "audit") void loadAudit(); }, 0);
    return () => window.clearTimeout(timer);
  }, [section, loadAudit]);
  useEffect(() => {
    const timer = window.setTimeout(() => { setNotice(""); setError(""); }, 0);
    return () => window.clearTimeout(timer);
  }, [section]);

  const categoryMap = new Map(categories.map((cat) => [cat.id, cat]));

  const filteredProducts = products.filter((p) => {
    const q = query.trim().toLowerCase();
    const matchesQuery = !q || p.name.toLowerCase().includes(q) || p.slug.toLowerCase().includes(q) || (p.model_code && p.model_code.toLowerCase().includes(q)) || (p.summary?.toLowerCase().includes(q) ?? false) || (p.description?.toLowerCase().includes(q) ?? false);
    const matchesCategory = selectedProductCategory === "all" || (selectedProductCategory === "unassigned" && p.app_collection_ids.length === 0) || p.category_id === selectedProductCategory || (p.category_ids ?? []).includes(selectedProductCategory);
    const matchesStatus = productStatusFilter === "all" || (productStatusFilter === "published" ? p.is_published : !p.is_published);
    const pdfDoc = productDatasheet(p);
    const matchesPdf = productPdfFilter === "all" || (productPdfFilter === "has_pdf" ? Boolean(pdfDoc) : !pdfDoc);
    const matchesSource =
      productSourceFilter === "all"
      || (productSourceFilter === "wp" && Boolean(p.wordpress_source_id))
      || (productSourceFilter === "cms" && !p.wordpress_source_id)
      || (productSourceFilter === "overridden" && Boolean(p.category_override || p.documents_override));
    return matchesQuery && matchesCategory && matchesStatus && matchesPdf && matchesSource;
  });

  const filteredCategories = categories.filter((c) => {
    const q = query.trim().toLowerCase();
    const matchesQuery = !q || c.name.toLowerCase().includes(q) || c.slug.toLowerCase().includes(q) || (c.description?.toLowerCase().includes(q) ?? false);
    const count = c.product_count ?? 0;
    const matchesFilter =
      categoryFilter === "all"
      || (categoryFilter === "visible" && c.is_published)
      || (categoryFilter === "hidden" && !c.is_published)
      || (categoryFilter === "empty" && count === 0)
      || (categoryFilter === "missing_pdf" && !c.catalog_pdf_url);
    return matchesQuery && matchesFilter;
  });

  const emptyPublishedCategories = categories.filter((c) => c.is_published && (c.product_count ?? 0) === 0);

  const filteredCustomers = customerProfiles.filter((c) => {
    const q = query.trim().toLowerCase();
    const matchesQuery = !q || c.name.toLowerCase().includes(q) || c.email.toLowerCase().includes(q) || c.mobile_number.includes(q) || (c.company_name && c.company_name.toLowerCase().includes(q)) || (c.gst_number && c.gst_number.toLowerCase().includes(q)) || c.location.toLowerCase().includes(q);
    const matchesRole = customerRoleFilter === "all" || c.customer_type === customerRoleFilter;
    return matchesRole && matchesQuery;
  });

  async function deleteProductItem(id: string, name: string) {
    if (!window.confirm(`Are you sure you want to delete "${name}"? This action cannot be undone.`)) return;
    setError(""); setNotice("");
    try {
      await api(user, `/admin/catalogue/products/${id}`, { method: "DELETE" });
      setNotice(`Product "${name}" deleted successfully.`);
      await loadCatalogue();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not delete product.");
    }
  }

  async function deleteCategoryItem(id: string, name: string) {
    if (!window.confirm(`Are you sure you want to delete category "${name}"?`)) return;
    setError(""); setNotice("");
    try {
      await api(user, `/admin/catalogue/categories/${id}`, { method: "DELETE" });
      setNotice(`Category "${name}" deleted successfully.`);
      await loadCatalogue();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not delete category.");
    }
  }

  async function toggleCategoryVisibility(category: Category) {
    setError(""); setNotice("");
    try {
      const action = category.is_published ? "unpublish" : "publish";
      await api(user, `/admin/catalogue/categories/${category.id}/${action}`, { method: "POST" });
      setNotice(`Collection "${category.name}" is now ${category.is_published ? "hidden from" : "visible in"} the mobile app.`);
      await loadCatalogue();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update collection visibility.");
    }
  }

  async function bulkUpdateCategoryVisibility(ids: string[], isPublished: boolean) {
    if (!ids.length) return;
    setError(""); setNotice("");
    try {
      const result = await api<{ updated: number }>(user, "/admin/catalogue/categories/bulk-visibility", {
        method: "POST",
        body: JSON.stringify({ category_ids: ids, is_published: isPublished }),
      });
      setSelectedCategoryIds(new Set());
      setNotice(`${result.updated} collection${result.updated === 1 ? "" : "s"} ${isPublished ? "published to" : "hidden from"} the customer app.`);
      await loadCatalogue();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update selected collections.");
    }
  }

  async function bulkMoveProductsToCategory() {
    if (!selectedProductIds.size || !bulkTargetCategoryId) return;
    setError(""); setNotice("");
    try {
      const result = await api<{ updated: number }>(user, "/admin/catalogue/products/bulk-category", {
        method: "POST",
        body: JSON.stringify({
          product_ids: [...selectedProductIds],
          category_id: bulkTargetCategoryId,
          keep_secondary_categories: true,
        }),
      });
      const targetName = categoryMap.get(bulkTargetCategoryId)?.name ?? "selected collection";
      setSelectedProductIds(new Set());
      setBulkTargetCategoryId("");
      setNotice(`Moved ${result.updated} product${result.updated === 1 ? "" : "s"} to "${targetName}" as primary collection.`);
      await loadCatalogue();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update selected products.");
    }
  }

  async function submitProduct(event: FormEvent) {
    event.preventDefault(); setError(""); setNotice("");
    try {
      let specifications: Record<string, unknown>;
      try {
        const parsed = JSON.parse(specificationsText);
        if (parsed == null || Array.isArray(parsed) || typeof parsed !== "object") throw new Error("Specifications must be a JSON object.");
        specifications = parsed as Record<string, unknown>;
      } catch {
        setSpecificationsError("Enter a valid JSON object before saving.");
        setError("Fix the product specifications JSON before saving.");
        return;
      }
      setSpecificationsError("");
      const documents = (productForm.documents ?? []).filter((document) => document.title.trim() || document.url.trim());
      if (documents.some((document) => !document.title.trim() || !document.url.trim().startsWith("https://"))) {
        setError("Each document needs a title and an HTTPS URL.");
        return;
      }
      const payload = { ...productForm, category_ids: [...new Set([productForm.category_id, ...(productForm.category_ids ?? [])].filter(Boolean))], specifications, applications: Array.isArray(productForm.applications) ? productForm.applications : [], features: Array.isArray(productForm.features) ? productForm.features : [], gallery_images: Array.isArray(productForm.gallery_images) ? productForm.gallery_images : [], documents };
      const saved = await api<Product>(user, editingProduct ? `/admin/catalogue/products/${editingProduct}` : "/admin/catalogue/products", { method: editingProduct ? "PATCH" : "POST", body: JSON.stringify(payload) });
      setNotice("Product draft saved."); setProductForm({ ...saved, documents: saved.own_documents }); setEditingProduct(saved.id); await loadCatalogue();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not save product."); }
  }

  async function publish(path: string) {
    setError(""); setNotice("");
    try { await api(user, path, { method: "POST" }); setNotice("Published successfully. The app now receives the published version."); await loadCatalogue(); if (section === "app_content") await loadContent(appContentTab); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not publish this change."); }
  }

  async function unpublish(path: string) {
    if (!window.confirm("Unpublish this item? It will stop appearing in the customer app until it is published again.")) return;
    setError(""); setNotice("");
    try {
      await api(user, path, { method: "POST" });
      setNotice("Unpublished. This content is no longer delivered to the customer app.");
      await loadCatalogue();
      if (section === "app_content") await loadContent(appContentTab);
      if (section === "knowledge") await loadKnowledge();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not unpublish this content."); }
  }

  async function saveContent() {
    setError(""); setNotice("");
    try { const envelope = await api<ContentEnvelope>(user, `/admin/app-config/${appContentTab}`, { method: "PUT", body: JSON.stringify(contentDraft) }); setContent(envelope); setContentDraft(envelope.draft_payload); setNotice("Draft saved."); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not save content."); }
  }

  async function wordpressPreview() {
    setWpStatus(""); setError("");
    try { const result = await api<{ items: Array<Record<string, unknown>>; message?: string }>(user, "/admin/integrations/wordpress/products?limit=20"); setWpPreview(result.items); setWpStatus(result.message ?? `${result.items.length} WordPress products found.`); await loadWordPressStatus(); }
    catch (cause) { setWpStatus(cause instanceof Error ? cause.message : "WordPress connection is not configured."); }
  }

  async function wordpressSync() {
    setWpStatus(""); setError(""); setNotice("");
    try {
      setNotice("Syncing products, categories, and brochure PDFs from WooCommerce...");
      const result = await api<WordPressSyncSummary>(user, "/admin/integrations/wordpress/sync", { method: "POST" });
      setLastWpSync(result);
      const created = result.created || 0;
      const updated = result.updated || 0;
      const docsLinked = result.documents_linked || 0;
      setNotice(
        `${result.message || "WooCommerce sync complete."} (${created} new, ${updated} updated, ${docsLinked} PDFs linked.)`,
      );
      setWpStatus(
        `Source: ${result.source_mode || "wc/v3"} | Preserved CMS overrides: ${result.cms_preserved_category_products || 0} product categories, ${result.cms_preserved_pdf_products || 0} product PDFs.`,
      );
      await loadCatalogue();
      await loadWordPressStatus();
    } catch (cause) {
      setNotice("");
      setError(cause instanceof Error ? cause.message : "WooCommerce sync failed.");
      await loadWordPressStatus();
    }
  }

  async function updateCustomerRequest(record: CustomerRequest, nextStatus: string, assignedTo: string) {
    setError(""); setNotice("");
    try {
      await api(user, `/admin/requests/${record.id}`, { method: "PATCH", body: JSON.stringify({ status: nextStatus, assigned_to: assignedTo || null, resolution_note: requestNotes[record.id] ?? record.resolution_note ?? "" }) });
      setNotice("Request update saved. The customer can see the latest status in the app."); await loadRequests(record.kind);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not update request."); }
  }

  async function updateContactInquiry(record: ContactInquiry) {
    setError(""); setNotice("");
    try {
      await api(user, `/admin/contact-inquiries/${record.id}`, { method: "PATCH", body: JSON.stringify({ status: inquiryStatuses[record.id] ?? record.status, notes: inquiryNotes[record.id] ?? "" }) });
      setNotice("Contact enquiry updated and recorded in the audit history.");
      await loadContactInquiries();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not update this contact enquiry."); }
  }

  function exportLoadedAudit() {
    const columns = ["created_at", "action", "entity_type", "entity_id", "actor_uid", "change_summary"];
    const safeCell = (value: unknown) => {
      let text = typeof value === "string" ? value : JSON.stringify(value ?? "") ?? "";
      if (/^[\t\r ]*[=+@\-]/.test(text)) text = `'${text}`;
      return `"${text.replaceAll('"', '""')}"`;
    };
    const rows = auditEvents.map((event) => [event.created_at, event.action, event.entity_type, event.entity_id, event.actor_uid, JSON.stringify(event.change_summary)]);
    const csv = [columns, ...rows].map((row) => row.map(safeCell).join(",")).join("\r\n");
    const url = URL.createObjectURL(new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `enertech-audit-loaded-${new Date().toISOString().slice(0, 10)}.csv`;
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function saveKnowledgeArticle(publishAfterSave: boolean) {
    setError(""); setNotice("");
    const title = knowledgeForm.title.trim();
    const answer = knowledgeForm.answer ?? "";
    const imageUrls = knowledgeForm.image_urls ?? [];
    const videoUrls = knowledgeForm.video_urls ?? [];
    if (title.length < 2) {
      setError("Enter a question title.");
      return;
    }
    if (!answer.trim() && !imageUrls.length && !videoUrls.length) {
      setError("Add an answer, image, or video before saving this FAQ.");
      return;
    }
    const autoSlug = title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 140);
    const slug = (knowledgeForm.slug.trim() || autoSlug || `faq-${Date.now()}`).slice(0, 180);
    const sourceRef = knowledgeForm.source_reference?.trim() || null;
    try {
      const payload = {
        slug,
        title,
        category: knowledgeForm.category.trim() || "General",
        answer,
        image_urls: imageUrls,
        video_urls: videoUrls,
        source_reference: sourceRef,
        sort_order: Number(knowledgeForm.sort_order) || 0,
      };
      let saved = await api<KnowledgeArticle>(user, editingKnowledge ? `/admin/knowledge/${editingKnowledge}` : "/admin/knowledge", { method: editingKnowledge ? "PATCH" : "POST", body: JSON.stringify(payload) });
      if (publishAfterSave) {
        saved = await api<KnowledgeArticle>(user, `/admin/knowledge/${saved.id}/publish`, { method: "POST" });
        setNotice("FAQ saved and published to the customer app.");
        setShowKnowledgeForm(false);
      } else {
        setNotice("Support content draft saved.");
        setKnowledgeForm(saved);
        setEditingKnowledge(saved.id);
        setKnowledgeSlugTouched(true);
      }
      await loadKnowledge();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not save support content."); }
  }

  async function submitKnowledge(event: FormEvent) {
    event.preventDefault();
    await saveKnowledgeArticle(false);
  }

  function insertKnowledgeSnippet(snippet: string) {
    const el = knowledgeAnswerRef.current;
    const current = knowledgeForm.answer ?? "";
    if (!el) {
      setKnowledgeForm({ ...knowledgeForm, answer: current ? `${current}\n${snippet}` : snippet });
      return;
    }
    const start = el.selectionStart ?? current.length;
    const end = el.selectionEnd ?? current.length;
    const selected = current.slice(start, end);
    let inserted = snippet;
    if (snippet === "**bold**" && selected) inserted = `**${selected}**`;
    else if (snippet === "# " && selected) inserted = `# ${selected}`;
    else if (snippet === "- " && selected) inserted = selected.split("\n").map((line) => (line.trim() ? `- ${line}` : line)).join("\n");
    const next = `${current.slice(0, start)}${inserted}${current.slice(end)}`;
    setKnowledgeForm({ ...knowledgeForm, answer: next });
    window.requestAnimationFrame(() => {
      el.focus();
      const cursor = start + inserted.length;
      el.setSelectionRange(cursor, cursor);
    });
  }

  async function uploadKnowledgeFiles(files: FileList | null, kind: "image_urls" | "video_urls") {
    if (!files?.length) return;
    setKnowledgeMediaUploading(true); setError("");
    try {
      const urls: string[] = [];
      for (const file of Array.from(files)) {
        const result = await uploadMedia(user, file);
        urls.push(result.url);
      }
      setKnowledgeForm((current) => {
        const existing = current[kind] ?? [];
        const updated = [...existing, ...urls.filter((url) => !existing.includes(url))];
        return { ...current, [kind]: updated };
      });
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not upload FAQ media."); }
    finally { setKnowledgeMediaUploading(false); }
  }

  async function submitAdmin(event: FormEvent) {
    event.preventDefault(); setError(""); setNotice("");
    try {
      const uid = editingAdminUid ?? adminForm.firebase_uid.trim();
      const saved = await api<AdminAccount>(user, `/admin/accounts/${encodeURIComponent(uid)}`, { method: "PUT", body: JSON.stringify({ ...adminForm, firebase_uid: uid }) });
      setNotice(`CMS access ${editingAdminUid ? "updated" : "granted"} for ${saved.email || saved.firebase_uid}.`);
      setAdminForm({ firebase_uid: "", email: "", display_name: "", role: "content_editor", is_active: true }); setEditingAdminUid(null); await loadAdmins();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not save CMS access."); }
  }

  function editCategory(category: Category) { setCollectionEditorTarget(category); setShowCreateCollection(true); }
  function openCategoryCatalogueModal(category: Category) { setCataloguePdfTarget(category); }
  function editProduct(product: Product) { setProductForm({ ...product, documents: product.own_documents }); setSpecificationsText(JSON.stringify(product.specifications ?? {}, null, 2)); setSpecificationsError(""); setEditingProduct(product.id); setShowProductForm(true); }

  function toggleSelectProduct(id: string) {
    const next = new Set(selectedProductIds);
    if (next.has(id)) next.delete(id); else next.add(id);
    setSelectedProductIds(next);
  }

  function toggleSelectAllProducts() {
    if (selectedProductIds.size === filteredProducts.length) {
      setSelectedProductIds(new Set());
    } else {
      setSelectedProductIds(new Set(filteredProducts.map((p) => p.id)));
    }
  }

  function toggleSelectCategory(id: string) {
    const next = new Set(selectedCategoryIds);
    if (next.has(id)) next.delete(id); else next.add(id);
    setSelectedCategoryIds(next);
  }

  function toggleSelectAllCategories() {
    if (selectedCategoryIds.size === filteredCategories.length) {
      setSelectedCategoryIds(new Set());
    } else {
      setSelectedCategoryIds(new Set(filteredCategories.map((c) => c.id)));
    }
  }

  return (
    <>
      <div className="admin-frame font-sans">
        {menuOpen && <button className="mobile-overlay overlay-open" aria-label="Close navigation" onClick={() => setMenuOpen(false)} />}
        
        {/* SIDEBAR NAVIGATION */}
        <aside className={`sidebar ${menuOpen ? "sidebar-open" : ""}`}>
          <a className="brand-lockup" href="#overview" onClick={(event) => { event.preventDefault(); setSection("overview"); setMenuOpen(false); }}>
            <span className="brand-mark">E</span>
            <span><strong>EnerTech</strong><small>Customer Platform CMS</small></span>
          </a>
          <div className="workspace-label">WORKSPACE</div>
          <nav className="grow" aria-label="Admin navigation">
            <div className="nav-section">OVERVIEW</div>
            <ul className="menu nav-menu">
              <li>
                <button className={section === "overview" ? "active" : ""} onClick={() => { setSection("overview"); setMenuOpen(false); }}>
                  <AdminIcon name="overview" /><span>Overview</span>
                </button>
              </li>
            </ul>

            <div className="nav-section">CATALOGUE</div>
            <ul className="menu nav-menu">
              <li>
                <button className={section === "products" ? "active" : ""} onClick={() => { setSection("products"); setMenuOpen(false); }}>
                  <AdminIcon name="product" />
                  <span className="flex-1">Products</span>
                  {summary && <span className="badge badge-xs badge-ghost font-mono">{summary.products_total}</span>}
                </button>
              </li>
              <li>
                <button className={section === "categories" ? "active" : ""} onClick={() => { setSection("categories"); setMenuOpen(false); }}>
                  <AdminIcon name="collection" />
                  <span className="flex-1">Collections</span>
                  {summary && <span className="badge badge-xs badge-ghost font-mono">{summary.categories_published}/{summary.categories_total}</span>}
                </button>
              </li>
              <li>
                <button className={section === "wordpress" ? "active" : ""} onClick={() => { setSection("wordpress"); setMenuOpen(false); }}>
                  <AdminIcon name="import" />
                  <span>WordPress Sync</span>
                </button>
              </li>
            </ul>

            {(role === "super_admin" || role === "admin") && (
              <>
                <div className="nav-section">CUSTOMER REQUESTS</div>
                <ul className="menu nav-menu">
                  <li>
                    <button className={section === "service" ? "active" : ""} onClick={() => { setSection("service"); setMenuOpen(false); }}>
                      <AdminIcon name="service" />
                      <span className="flex-1">{sectionNames.service}</span>
                      {summary && summary.open_service_requests > 0 && <span className="badge badge-xs badge-warning font-mono">{summary.open_service_requests}</span>}
                    </button>
                  </li>
                  <li>
                    <button className={section === "quotes" ? "active" : ""} onClick={() => { setSection("quotes"); setMenuOpen(false); }}>
                      <AdminIcon name="quote" />
                      <span className="flex-1">{sectionNames.quotes}</span>
                      {summary && summary.open_quote_requests > 0 && <span className="badge badge-xs badge-warning font-mono">{summary.open_quote_requests}</span>}
                    </button>
                  </li>
                  <li><button className={section === "warranty" ? "active" : ""} onClick={() => { setSection("warranty"); setMenuOpen(false); }}><AdminIcon name="service" /><span className="flex-1">Warranty registrations</span></button></li>
                  <li><button className={section === "amc" ? "active" : ""} onClick={() => { setSection("amc"); setMenuOpen(false); }}><AdminIcon name="service" /><span className="flex-1">AMC requests</span></button></li>
                  <li>
                    <button className={section === "contact_inquiries" ? "active" : ""} onClick={() => { setSection("contact_inquiries"); setMenuOpen(false); }}>
                      <AdminIcon name="inquiry" />
                      <span className="flex-1">{sectionNames.contact_inquiries}</span>
                      {summary && summary.open_contact_inquiries > 0 && <span className="badge badge-xs badge-warning font-mono">{summary.open_contact_inquiries}</span>}
                    </button>
                  </li>
                </ul>
              </>
            )}

            <div className="nav-section">MOBILE APP</div>
            <ul className="menu nav-menu">
              <li>
                <button className={section === "app_content" ? "active" : ""} onClick={() => { setSection("app_content"); setMenuOpen(false); }}>
                  <AdminIcon name="home" /><span>App Content</span>
                </button>
              </li>
              <li>
                <button className={section === "knowledge" ? "active" : ""} onClick={() => { setSection("knowledge"); setMenuOpen(false); }}>
                  <AdminIcon name="solution" /><span>FAQs &amp; Knowledge</span>
                </button>
              </li>
            </ul>

            {(role === "super_admin" || role === "admin") && (
              <>
                <div className="nav-section">ADMINISTRATION</div>
                <ul className="menu nav-menu">
                  <li>
                    <button className={section === "customers" ? "active" : ""} onClick={() => { setSection("customers"); setMenuOpen(false); }}>
                      <AdminIcon name="customer" />
                      <span className="flex-1">Customers</span>
                      {summary && <span className="badge badge-xs badge-ghost font-mono">{summary.customers_total}</span>}
                    </button>
                  </li>
                  {role === "super_admin" && (
                    <li>
                      <button className={section === "admins" ? "active" : ""} onClick={() => { setSection("admins"); setMenuOpen(false); }}>
                        <AdminIcon name="admin" /><span>{sectionNames.admins}</span>
                      </button>
                    </li>
                  )}
                  <li>
                    <button className={section === "audit" ? "active" : ""} onClick={() => { setSection("audit"); setMenuOpen(false); }}>
                      <AdminIcon name="audit" /><span>{sectionNames.audit}</span>
                    </button>
                  </li>
                </ul>
              </>
            )}
          </nav>

          <div className="sidebar-bottom">
            <div className="environment-pill flex items-center justify-between w-full p-2 text-xs text-base-content/60">
              <span>API connection</span>
              <span>Private proxy</span>
            </div>
            <div className="user-row">
              <span className="avatar-circle">{(user.displayName || user.email || "A").slice(0, 1).toUpperCase()}</span>
              <div className="min-w-0">
                <strong className="truncate">{user.displayName || user.email}</strong>
                <small>{role.replaceAll("_", " ").toUpperCase()}</small>
              </div>
            </div>
          </div>
        </aside>

        {/* MAIN COLUMN */}
        <div className="main-column">
          <header className="topbar">
            <div className="flex min-w-0 items-center gap-2">
              <button className="btn btn-ghost btn-square mobile-menu shrink-0" aria-label="Open navigation" onClick={() => setMenuOpen(true)}><AdminIcon name="menu" className="h-5 w-5" /></button>
              <div className="breadcrumbs truncate">Workspace <span className="mx-1.5 text-base-300">/</span><strong>{title}</strong></div>
            </div>
            <div className="topbar-actions">
              <button className="btn btn-xs btn-outline border-sky-300 text-sky-900 hover:bg-sky-50" onClick={() => void wordpressSync()} title="Pull latest product data from WooCommerce while keeping CMS overrides">
                <BoltMark className="h-3.5 w-3.5" /> Quick Sync WP
              </button>
              <span className="hidden max-w-48 truncate text-xs text-base-content/65 md:inline font-medium">{user.email}</span>
              <button className="btn btn-ghost btn-xs sm:btn-sm shrink-0" onClick={() => { const auth = getFirebaseAuth(); if (auth) void signOut(auth); }}>Sign out</button>
            </div>
          </header>

          <main className="content-wrap">
            {notice && <div role="status" className="alert alert-success mb-3 py-2.5 text-sm font-medium">{notice}</div>}
            {error && <div role="alert" className="alert alert-error mb-3 py-2.5 text-sm font-medium">{error}</div>}

            {/* OVERVIEW */}
            {section === "overview" && (
              <>
                <div className="page-heading">
                  <div>
                    <p className="eyebrow">OPERATIONS DASHBOARD</p>
                    <h1>Platform Overview</h1>
                    <p>Live catalogue coverage, customer request queue, and mobile app sync health.</p>
                  </div>
                  <div className="page-actions">
                    <button className="btn btn-outline btn-sm" onClick={() => void wordpressSync()}><BoltMark className="h-3.5 w-3.5" /> Sync WordPress</button>
                    <button className="btn btn-outline btn-sm" onClick={() => { void loadCatalogue(); if (role === "admin" || role === "super_admin") void loadCustomers(); }}>Refresh</button>
                  </div>
                </div>

                <div className="metrics-grid">
                  <button
                    type="button"
                    className="card metric-card text-left"
                    onClick={() => {
                      setProductPdfFilter("all");
                      setSelectedProductCategory("all");
                      setSection("products");
                    }}
                  >
                    <div className="card-body">
                      <div className="metric-top">
                        <span className="metric-label">Products</span>
                        <span className="metric-icon"><AdminIcon name="product" /></span>
                      </div>
                      <strong className="metric-value">{summary?.products_published ?? products.length}</strong>
                      <span className="metric-foot">{summary?.products_total ?? productTotal} total in catalogue</span>
                    </div>
                  </button>

                  <button
                    type="button"
                    className="card metric-card text-left"
                    onClick={() => {
                      setProductPdfFilter("missing_pdf");
                      setSelectedProductCategory("all");
                      setSection("products");
                    }}
                  >
                    <div className="card-body">
                      <div className="metric-top">
                        <span className="metric-label">Missing PDFs</span>
                        <span className="metric-icon"><AdminIcon name="document" /></span>
                      </div>
                      <strong className="metric-value">{summary?.products_missing_pdf ?? "—"}</strong>
                      <span className="metric-foot">Click to attach product or collection PDFs</span>
                    </div>
                  </button>

                  <button
                    type="button"
                    className="card metric-card text-left"
                    onClick={() => {
                      setCategoryFilter("all");
                      setSection("categories");
                    }}
                  >
                    <div className="card-body">
                      <div className="metric-top">
                        <span className="metric-label">Visible Collections</span>
                        <span className="metric-icon"><AdminIcon name="collection" /></span>
                      </div>
                      <strong className="metric-value">{summary?.categories_published ?? categories.filter((c) => c.is_published).length}</strong>
                      <span className="metric-foot">{summary?.categories_hidden ?? 0} hidden · {summary?.categories_empty ?? 0} empty</span>
                    </div>
                  </button>

                  <button
                    type="button"
                    className="card metric-card text-left"
                    onClick={() => setSection(role === "admin" || role === "super_admin" ? "service" : "app_content")}
                  >
                    <div className="card-body">
                      <div className="metric-top">
                        <span className="metric-label">{role === "admin" || role === "super_admin" ? "Open Customer Queue" : "App Content"}</span>
                        <span className="metric-icon"><AdminIcon name={role === "admin" || role === "super_admin" ? "service" : "home"} /></span>
                      </div>
                      <strong className="metric-value">
                        {role === "admin" || role === "super_admin"
                          ? (summary ? summary.open_service_requests + summary.open_quote_requests + summary.open_contact_inquiries : "—")
                          : appContentTabs.length}
                      </strong>
                      <span className="metric-foot">
                        {role === "admin" || role === "super_admin"
                          ? `${summary?.open_service_requests ?? 0} service · ${summary?.open_quote_requests ?? 0} quotes · ${summary?.open_contact_inquiries ?? 0} enquiries`
                          : "Edit mobile screens and branding"}
                      </span>
                    </div>
                  </button>
                </div>

                <section className="section-grid">
                  <article className="card panel">
                    <header className="panel-head">
                      <div>
                        <h2>Quick Workspace Actions</h2>
                        <p>Curate WordPress data without breaking syncs.</p>
                      </div>
                    </header>
                    <div className="grid gap-2.5 p-4 sm:grid-cols-2">
                      <button className="module-card text-left" onClick={() => { setCategoryFilter("empty"); setSection("categories"); }}>
                        <div>
                          <strong>Clean Empty Collections ({summary?.categories_empty ?? 0})</strong>
                          <p>Review or hide 0-product WooCommerce tags from the app</p>
                        </div>
                        <span aria-hidden="true">→</span>
                      </button>
                      <button className="module-card text-left" onClick={() => { setProductPdfFilter("missing_pdf"); setSection("products"); }}>
                        <div>
                          <strong>Products Missing PDFs ({summary?.products_missing_pdf ?? 0})</strong>
                          <p>Upload product datasheets or attach collection brochures</p>
                        </div>
                        <span aria-hidden="true">→</span>
                      </button>
                      <button className="module-card text-left" onClick={() => setSection("app_content")}>
                        <div>
                          <strong>Mobile App Screens</strong>
                          <p>Home, contacts, Solution Finder, chat, and brand logo</p>
                        </div>
                        <span aria-hidden="true">→</span>
                      </button>
                      <button className="module-card text-left" onClick={() => setSection("knowledge")}>
                        <div>
                          <strong>FAQs &amp; Support Knowledge</strong>
                          <p>Publish verified technical support answers</p>
                        </div>
                        <span aria-hidden="true">→</span>
                      </button>
                    </div>
                  </article>

                  <article className="card panel">
                    <header className="panel-head">
                      <div>
                        <h2>Catalogue Override Status</h2>
                        <p>CMS changes pinned across WordPress syncs</p>
                      </div>
                    </header>
                    <div className="queue-list">
                      <div className="queue-row">
                        <i className="queue-dot bg-sky-500" />
                        <div>
                          <strong>Assigned to collections</strong>
                          <span>Products in one or more app collections</span>
                        </div>
                        <span className="queue-count font-mono font-bold">{(summary?.products_total ?? 0) - (summary?.products_unassigned ?? 0)}</span>
                      </div>
                      <button className="queue-row" onClick={() => { setSelectedProductCategory("unassigned"); setSection("products"); }}>
                        <strong>Unassigned (staging)</strong><span className="queue-count">{summary?.products_unassigned ?? 0}</span>
                      </button>
                      <div className="queue-row">
                        <i className="queue-dot bg-sky-500" />
                        <div>
                          <strong>Product PDF Overrides</strong>
                          <span>Products with CMS-uploaded or cleared brochures</span>
                        </div>
                        <span className="queue-count font-mono font-bold">{summary?.products_pdf_overridden ?? 0}</span>
                      </div>
                      <div className="queue-row">
                        <i className="queue-dot bg-amber-400" />
                        <div>
                          <strong>Collections Missing Catalogue PDF</strong>
                          <span>Collections without an inherited fallback brochure</span>
                        </div>
                        <span className="queue-count font-mono font-bold">{summary?.categories_missing_pdf ?? 0}</span>
                      </div>
                      {(role === "admin" || role === "super_admin") && (
                        <div className="queue-row">
                          <i className="queue-dot bg-emerald-500" />
                          <div>
                            <strong>Registered App Customers</strong>
                            <span>Active verified profiles synced from mobile app</span>
                          </div>
                          <span className="queue-count font-mono font-bold">{summary?.customers_total ?? customerProfiles.length}</span>
                        </div>
                      )}
                    </div>
                  </article>
                </section>
              </>
            )}

            {/* PRODUCTS & COLLECTIONS CATALOGUE */}
            {(section === "products" || section === "categories") && (
              <>
                <div className="page-heading">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <h1>{section === "products" ? "Products" : "Collections"}</h1>
                      <span className="badge badge-sm badge-ghost font-mono">
                        {section === "products"
                          ? `${productTotal} products`
                          : `${categories.length}${categoryHasMore ? "+" : ""} collections`}
                      </span>
                    </div>
                    <div className="tabs tabs-boxed mt-2 inline-flex bg-base-200/70 p-1 rounded-lg">
                      <button
                        className={`tab tab-xs px-3 font-semibold ${section === "products" ? "tab-active bg-base-100 shadow-xs text-primary" : "text-base-content/70"}`}
                        onClick={() => setSection("products")}
                      >
                        Products ({productTotal})
                      </button>
                      <button
                        className={`tab tab-xs px-3 font-semibold ${section === "categories" ? "tab-active bg-base-100 shadow-xs text-primary" : "text-base-content/70"}`}
                        onClick={() => setSection("categories")}
                      >
                        Collections ({categories.length})
                      </button>
                    </div>
                  </div>

                  <div className="page-actions">
                    <button className="btn btn-sm btn-outline gap-1.5" onClick={() => void wordpressSync()} title="Sync latest WooCommerce catalogue while keeping CMS overrides">
                      <BoltMark className="h-3.5 w-3.5" /> Sync WP
                    </button>
                    <button className="btn btn-sm btn-outline" onClick={() => void loadCatalogue()}>
                      Refresh
                    </button>
                    <button
                      className="btn btn-sm btn-primary gap-1"
                      onClick={() => {
                        if (section === "products") {
                          setProductForm({ ...emptyProduct, category_id: categories[0]?.id ?? "", category_ids: categories[0] ? [categories[0].id] : [] });
                          setSpecificationsText("{}"); setSpecificationsError("");
                          setEditingProduct(null);
                          setShowProductForm(true);
                        } else {
                          setCollectionEditorTarget(null);
                          setShowCreateCollection(true);
                        }
                      }}
                    >
                      <span>+</span> {section === "products" ? "New Product" : "New Collection"}
                    </button>
                  </div>
                </div>

                <article className="card panel table-panel overflow-hidden border border-base-200 rounded-xl">
                  <div className="table-toolbar">
                    <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
                      <label className="input input-bordered input-sm flex min-w-0 w-full items-center gap-2 rounded-lg sm:w-56">
                        <span aria-hidden="true" className="text-base-content/40">⌕</span>
                        <input
                          className="min-w-0 flex-1"
                          maxLength={120}
                          placeholder={`Search ${section}...`}
                          value={query}
                          onChange={(event) => setQuery(event.target.value)}
                          aria-label={`Search ${section}`}
                        />
                      </label>

                      {section === "products" && (
                        <>
                          <select
                            className="select select-bordered select-sm w-full min-w-0 rounded-lg text-xs sm:w-48"
                            value={selectedProductCategory}
                            onChange={(e) => setSelectedProductCategory(e.target.value)}
                          >
                            <option value="all">All collections ({categories.length})</option>
                            <option value="unassigned">Unassigned (staging)</option>
                            {categories.map((c) => (
                              <option key={c.id} value={c.id}>
                                {c.name} ({c.product_count ?? 0}){c.is_published ? "" : " [Hidden]"}
                              </option>
                            ))}
                          </select>

                          <select
                            className="select select-bordered select-sm rounded-lg text-xs"
                            value={productPdfFilter}
                            onChange={(e) => setProductPdfFilter(e.target.value as "all" | "has_pdf" | "missing_pdf")}
                          >
                            <option value="all">PDF: All</option>
                            <option value="has_pdf">Has PDF</option>
                            <option value="missing_pdf">Missing PDF</option>
                          </select>

                          <select
                            className="select select-bordered select-sm rounded-lg text-xs"
                            value={productSourceFilter}
                            onChange={(e) => setProductSourceFilter(e.target.value as "all" | "wp" | "cms" | "overridden")}
                          >
                            <option value="all">Source: All</option>
                            <option value="wp">WooCommerce</option>
                            <option value="cms">CMS managed</option>
                            <option value="overridden">CMS Overridden</option>
                          </select>

                          <select
                            className="select select-bordered select-sm rounded-lg text-xs"
                            value={productStatusFilter}
                            onChange={(e) => setProductStatusFilter(e.target.value as "all" | "published" | "draft")}
                          >
                            <option value="all">Status: All</option>
                            <option value="published">Published</option>
                            <option value="draft">Draft</option>
                          </select>
                        </>
                      )}

                      {section === "categories" && (
                        <div className="flex flex-wrap items-center gap-1">
                          {([
                            ["all", `All (${categories.length})`],
                            ["visible", `Visible (${categories.filter((c) => c.is_published).length})`],
                            ["hidden", `Hidden (${categories.filter((c) => !c.is_published).length})`],
                            ["empty", `Empty (${categories.filter((c) => (c.product_count ?? 0) === 0).length})`],
                            ["missing_pdf", `No PDF (${categories.filter((c) => !c.catalog_pdf_url).length})`],
                          ] as const).map(([key, label]) => (
                            <button
                              key={key}
                              type="button"
                              className={`btn btn-xs rounded-lg ${categoryFilter === key ? "btn-primary text-white" : "btn-ghost text-base-content/75"}`}
                              onClick={() => setCategoryFilter(key)}
                            >
                              {label}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="flex flex-wrap items-center gap-2 shrink-0">
                      {section === "categories" && emptyPublishedCategories.length > 0 && (
                        <button
                          type="button"
                          className="btn btn-xs btn-outline btn-warning"
                          onClick={() => void bulkUpdateCategoryVisibility(emptyPublishedCategories.map((c) => c.id), false)}
                          title="Hide all WooCommerce categories that have 0 linked products"
                        >
                          Hide {emptyPublishedCategories.length} Empty
                        </button>
                      )}
                      {section === "products" && (
                        <div className="join border border-base-300 rounded-lg overflow-hidden bg-base-200/50">
                          <button
                            className={`join-item btn btn-xs px-2.5 font-semibold ${productViewMode === "table" ? "btn-active btn-primary text-white" : "btn-ghost"}`}
                            onClick={() => setProductViewMode("table")}
                          >
                            <AdminIcon name="table" /> Table
                          </button>
                          <button
                            className={`join-item btn btn-xs px-2.5 font-semibold ${productViewMode === "grid" ? "btn-active btn-primary text-white" : "btn-ghost"}`}
                            onClick={() => setProductViewMode("grid")}
                          >
                            <AdminIcon name="grid" /> Grid
                          </button>
                        </div>
                      )}
                      <span className="text-xs text-base-content/60 font-medium">
                        {loading ? "Loading…" : section === "products" ? `${filteredProducts.length} / ${productTotal}` : `${filteredCategories.length} shown`}
                      </span>
                    </div>
                  </div>

                  {/* BULK BAR: PRODUCTS */}
                  {section === "products" && selectedProductIds.size > 0 && (
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-primary/20 bg-primary/5 px-4 py-2 text-xs">
                      <strong>{selectedProductIds.size} product{selectedProductIds.size === 1 ? "" : "s"} selected</strong>
                      <div className="flex flex-wrap items-center gap-2">
                        <select
                          className="select select-bordered select-xs w-56"
                          value={bulkTargetCategoryId}
                          onChange={(e) => setBulkTargetCategoryId(e.target.value)}
                        >
                          <option value="">Choose new primary collection…</option>
                          {categories.map((c) => (
                            <option key={c.id} value={c.id}>{c.name} ({c.product_count ?? 0})</option>
                          ))}
                        </select>
                        <button
                          type="button"
                          className="btn btn-xs btn-primary"
                          disabled={!bulkTargetCategoryId}
                          onClick={() => void bulkMoveProductsToCategory()}
                        >
                          Set Primary Collection
                        </button>
                        <button type="button" className="btn btn-xs btn-ghost" onClick={() => setSelectedProductIds(new Set())}>
                          Clear
                        </button>
                      </div>
                    </div>
                  )}

                  {/* BULK BAR: COLLECTIONS */}
                  {section === "categories" && selectedCategoryIds.size > 0 && (
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-primary/20 bg-primary/5 px-4 py-2 text-xs">
                      <strong>{selectedCategoryIds.size} collection{selectedCategoryIds.size === 1 ? "" : "s"} selected</strong>
                      <div className="flex flex-wrap items-center gap-2">
                        <button
                          type="button"
                          className="btn btn-xs btn-success"
                          onClick={() => void bulkUpdateCategoryVisibility([...selectedCategoryIds], true)}
                        >
                          Show in App
                        </button>
                        <button
                          type="button"
                          className="btn btn-xs btn-warning"
                          onClick={() => void bulkUpdateCategoryVisibility([...selectedCategoryIds], false)}
                        >
                          Hide from App
                        </button>
                        <button type="button" className="btn btn-xs btn-ghost" onClick={() => setSelectedCategoryIds(new Set())}>
                          Clear
                        </button>
                      </div>
                    </div>
                  )}

                  {/* PRODUCTS: TABLE VIEW */}
                  {section === "products" && productViewMode === "table" && (
                    <div className="overflow-x-auto">
                      <table className="table content-table w-full">
                        <thead>
                          <tr>
                            <th className="w-9">
                              <input
                                type="checkbox"
                                className="checkbox checkbox-xs rounded"
                                checked={selectedProductIds.size === filteredProducts.length && filteredProducts.length > 0}
                                onChange={toggleSelectAllProducts}
                              />
                            </th>
                            <th>Product</th>
                            <th>App Collections</th>
                            <th>Status &amp; Source</th>
                            <th>Price / Stock</th>
                            <th>Brochure PDF</th>
                            <th className="text-right">Actions</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-base-200">
                          {filteredProducts.map((product) => {
                            const primaryCategory = categoryMap.get(product.category_id);
                            const secondary = product.app_collection_ids.filter((id) => id !== product.category_id);
                            const isSelected = selectedProductIds.has(product.id);
                            const pdfDoc = productDatasheet(product);

                            return (
                              <tr key={product.id} className={`hover:bg-base-200/40 transition-colors ${isSelected ? "bg-primary/5" : ""}`}>
                                <td>
                                  <input
                                    type="checkbox"
                                    className="checkbox checkbox-xs rounded"
                                    checked={isSelected}
                                    onChange={() => toggleSelectProduct(product.id)}
                                  />
                                </td>
                                <td>
                                  <div className="flex items-center gap-2.5">
                                    <div className="relative h-10 w-10 rounded-lg bg-base-200 border border-base-300 flex items-center justify-center overflow-hidden shrink-0">
                                      {product.image_url ? (
                                        <Image src={product.image_url} alt={product.name} fill sizes="40px" unoptimized className="object-contain p-1" />
                                      ) : (
                                        <BoltMark className="h-4 w-4 text-base-content/40" />
                                      )}
                                    </div>
                                    <div className="min-w-0 max-w-xs md:max-w-sm">
                                      <strong className="block font-semibold text-base-content truncate" title={product.name}>
                                        {product.name}
                                      </strong>
                                      <span className="block font-mono text-[11px] text-base-content/50 truncate">
                                        {product.model_code || product.slug}
                                      </span>
                                    </div>
                                  </div>
                                </td>
                                <td>
                                  <div className="flex items-center gap-1.5">
                                    <button
                                      type="button"
                                      onClick={() => setProductCategoryTarget(product)}
                                      className={`badge badge-sm gap-1 cursor-pointer hover:border-primary ${primaryCategory?.is_published === false ? "badge-warning" : "badge-ghost"}`}
                                      title="Click to change primary or linked collections"
                                    >
                                      <span className="max-w-36 truncate">{primaryCategory?.name ?? "Unassigned"}</span>
                                      {secondary.map((id) => <span className="badge badge-xs" key={id}>{categoryMap.get(id)?.name ?? "Collection"}</span>)}
                                    </button>
                                    {product.category_override && (
                                      <span className="badge badge-xs badge-info" title="Collection pinned in CMS">CMS</span>
                                    )}
                                  </div>
                                </td>
                                <td>
                                  <div className="flex flex-wrap items-center gap-1.5">
                                    <span className="inline-flex items-center gap-1 whitespace-nowrap text-xs font-medium">
                                      <span className={`w-2 h-2 rounded-full ${product.is_published ? "bg-emerald-500" : "bg-amber-400"}`} />
                                      <span>{product.is_published ? "Live" : "Draft"}</span>
                                    </span>
                                    <span className={`badge badge-xs ${product.wordpress_source_id ? "badge-outline" : "badge-secondary"}`}>
                                      {product.wordpress_source_id ? "WP" : "CMS"}
                                    </span>
                                  </div>
                                </td>
                                <td>
                                  <div className="flex flex-col items-start gap-0.5 whitespace-nowrap">
                                    {product.price_minor != null && (
                                      <strong className="text-xs font-bold text-base-content">{catalogPrice(product)}</strong>
                                    )}
                                    <span className={`badge badge-xs whitespace-nowrap ${stockBadgeClass(product.stock_status)}`}>{stockLabel(product.stock_status)}</span>
                                  </div>
                                </td>
                                <td>
                                  <div className="flex items-center gap-1.5">
                                    {pdfDoc ? (
                                      <a
                                        href={pdfDoc.url}
                                        target="_blank"
                                        rel="noreferrer"
                                        className="link link-primary text-xs font-semibold whitespace-nowrap"
                                        title={pdfDoc.title}
                                      >
                                        {pdfDoc.inherited ? "Collection PDF" : "Product PDF"}
                                      </a>
                                    ) : (
                                      <span className="text-xs text-base-content/45">Missing</span>
                                    )}
                                    {product.documents_override && (
                                      <span className="badge badge-xs badge-info" title="PDF override saved in CMS">Pinned</span>
                                    )}
                                  </div>
                                </td>
                                <td className="text-right whitespace-nowrap">
                                  <div className="flex items-center justify-end gap-1">
                                    <button className="btn btn-ghost btn-xs text-primary" onClick={() => setProductPdfTarget(product)}>
                                      {pdfDoc && !pdfDoc.inherited ? "Edit PDF" : "Upload PDF"}
                                    </button>
                                    <button className="btn btn-ghost btn-xs" onClick={() => setProductCategoryTarget(product)}>
                                      Collection
                                    </button>
                                    {!product.wordpress_source_id && (
                                      <>
                                        <button className="btn btn-ghost btn-xs" onClick={() => editProduct(product)}>Edit</button>
                                        <button className="btn btn-ghost btn-xs" onClick={() => product.is_published ? void unpublish(`/admin/catalogue/products/${product.id}/unpublish`) : void publish(`/admin/catalogue/products/${product.id}/publish`)}>
                                          {product.is_published ? "Unpublish" : "Publish"}
                                        </button>
                                        <button className="btn btn-ghost btn-xs text-error" onClick={() => deleteProductItem(product.id, product.name)}>Delete</button>
                                      </>
                                    )}
                                  </div>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                      {!filteredProducts.length && (
                        <Empty title="No matching products" detail="Adjust filters or sync WooCommerce products." />
                      )}
                    </div>
                  )}

                  {/* PRODUCTS: GRID VIEW */}
                  {section === "products" && productViewMode === "grid" && (
                    <div className="p-4">
                      <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
                        {filteredProducts.map((product) => {
                          const primaryCategory = categoryMap.get(product.category_id);
                          const secondary = product.app_collection_ids.filter((id) => id !== product.category_id);
                          const pdfDoc = productDatasheet(product);

                          return (
                            <div
                              key={product.id}
                              className="rounded-xl border border-base-200 bg-base-100 shadow-xs hover:shadow-md transition duration-200 flex flex-col justify-between overflow-hidden group"
                            >
                              <div className="relative bg-[#f4f7fb] h-36 flex items-center justify-center p-2.5 overflow-hidden border-b border-base-200">
                                <span className={`absolute top-2 left-2 px-1.5 py-0.5 text-[10px] font-bold rounded border ${product.wordpress_source_id ? "bg-[#e0f2fe] text-[#0369a1] border-[#bae6fd]" : "bg-purple-100 text-purple-700 border-purple-200"}`}>
                                  {product.wordpress_source_id ? "WP" : "CMS"}
                                </span>
                                {(product.category_override || product.documents_override) && (
                                  <span className="absolute top-2 right-2 badge badge-xs badge-info">Override</span>
                                )}
                                {product.image_url ? (
                                  <Image
                                    src={product.image_url}
                                    alt={product.name}
                                    fill
                                    sizes="(max-width: 768px) 100vw, 25vw"
                                    unoptimized
                                    className="object-contain p-2 group-hover:scale-105 transition-transform duration-200"
                                  />
                                ) : (
                                  <BoltMark className="h-7 w-7 text-base-content/35" />
                                )}
                              </div>

                              <div className="p-3 flex flex-col flex-1 justify-between gap-2.5">
                                <div>
                                  <h3 className="font-bold text-xs text-base-content line-clamp-2 min-h-8 leading-snug" title={product.name}>
                                    {product.name}
                                  </h3>
                                  <p className="font-mono text-[11px] text-base-content/50 truncate mt-0.5">
                                    {product.model_code || product.slug}
                                  </p>
                                  <div className="mt-1.5 flex items-center gap-1">
                                    <span className="badge badge-xs badge-ghost max-w-36 truncate">{primaryCategory?.name ?? "Unassigned"}</span>
                                    {secondary.map((id) => <span className="badge badge-xs" key={id}>{categoryMap.get(id)?.name ?? "Collection"}</span>)}
                                  </div>
                                </div>

                                <div className="flex items-center justify-between gap-1 pt-2 border-t border-base-200">
                                  {pdfDoc ? (
                                    <a
                                      href={pdfDoc.url}
                                      target="_blank"
                                      rel="noreferrer"
                                      className="link link-primary text-[11px] font-semibold truncate"
                                      title={pdfDoc.title}
                                    >
                                      {pdfDoc.inherited ? "Cat PDF" : "PDF"}
                                    </a>
                                  ) : (
                                    <span className="text-[11px] text-base-content/40">No PDF</span>
                                  )}
                                  <div className="flex items-center gap-1">
                                    <button className="btn btn-xs btn-ghost text-primary px-1.5" onClick={() => setProductPdfTarget(product)}>
                                      PDF
                                    </button>
                                    <button className="btn btn-xs btn-ghost px-1.5" onClick={() => setProductCategoryTarget(product)}>
                                      Cat
                                    </button>
                                    {!product.wordpress_source_id && (
                                      <button className="btn btn-xs btn-ghost px-1.5" onClick={() => editProduct(product)}>Edit</button>
                                    )}
                                  </div>
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                      {!filteredProducts.length && (
                        <Empty title="No matching products" detail="Adjust filters or sync WooCommerce products." />
                      )}
                    </div>
                  )}

                  {section === "products" && productHasMore && (
                    <div className="flex justify-center border-t border-base-200 p-3">
                      <button className="btn btn-outline btn-sm" disabled={loading} onClick={() => void loadCatalogue(products.length, categories.length, true)}>
                        {loading ? <span className="loading loading-spinner loading-sm" /> : `Load more products (${Math.max(0, productTotal - products.length)} remaining)`}
                      </button>
                    </div>
                  )}

                  {/* CATEGORIES / COLLECTIONS VIEW */}
                  {section === "categories" && (
                    <div className="overflow-x-auto">
                      <table className="table content-table">
                        <thead>
                          <tr>
                            <th className="w-9">
                              <input
                                type="checkbox"
                                className="checkbox checkbox-xs rounded"
                                checked={selectedCategoryIds.size === filteredCategories.length && filteredCategories.length > 0}
                                onChange={toggleSelectAllCategories}
                              />
                            </th>
                            <th>Collection</th>
                            <th>Slug</th>
                            <th>Products</th>
                            <th>Catalogue PDF</th>
                            <th>App Visibility</th>
                            <th>Sort</th>
                            <th className="text-right">Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {filteredCategories.map((category) => {
                            const count = category.product_count ?? 0;
                            return (
                              <tr key={category.id} className={!category.is_published ? "opacity-75 bg-base-200/25" : ""}>
                                <td>
                                  <input
                                    type="checkbox"
                                    className="checkbox checkbox-xs rounded"
                                    checked={selectedCategoryIds.has(category.id)}
                                    onChange={() => toggleSelectCategory(category.id)}
                                  />
                                </td>
                                <td>
                                  <div className="flex flex-wrap items-center gap-1.5">
                                    <strong className="text-base-content">{category.name}</strong>
                                  </div>
                                  {category.description && <span className="block text-xs text-base-content/55 truncate max-w-md">{category.description}</span>}
                                </td>
                                <td className="font-mono text-xs">{category.slug}</td>
                                <td>
                                  <button
                                    type="button"
                                    className={`badge badge-sm font-mono ${count === 0 ? "badge-ghost text-base-content/50" : "badge-outline"}`}
                                    onClick={() => {
                                      setSelectedProductCategory(category.id);
                                      setSection("products");
                                    }}
                                    title="View products in this collection"
                                  >
                                    {count}
                                  </button>
                                </td>
                                <td>
                                  {category.catalog_pdf_url ? (
                                    <a href={category.catalog_pdf_url} target="_blank" rel="noreferrer" className="link link-primary text-xs font-medium" title={category.catalog_pdf_title || "Open collection PDF"}>
                                      View PDF
                                    </a>
                                  ) : (
                                    <span className="text-xs text-base-content/45">None</span>
                                  )}
                                </td>
                                <td>
                                  <label className="inline-flex cursor-pointer items-center gap-2">
                                    <input
                                      type="checkbox"
                                      className="toggle toggle-xs toggle-success"
                                      checked={category.is_published}
                                      onChange={() => void toggleCategoryVisibility(category)}
                                    />
                                    <span className="text-xs font-medium">{category.is_published ? "Visible" : "Hidden"}</span>
                                  </label>
                                </td>
                                <td className="font-mono text-xs">{category.sort_order}</td>
                                <td className="text-right whitespace-nowrap">
                                  <div className="flex items-center justify-end gap-1">
                                    <button className="btn btn-outline btn-xs" onClick={() => setAssignTarget(category)}>Assign products</button>
                                    <button className="btn btn-ghost btn-xs text-primary" onClick={() => openCategoryCatalogueModal(category)}>
                                      Catalogue PDF
                                    </button>
                                    <button className="btn btn-ghost btn-xs" onClick={() => editCategory(category)}>Edit</button>
                                    {count === 0 && (
                                      <button className="btn btn-ghost btn-xs text-error" onClick={() => deleteCategoryItem(category.id, category.name)}>Delete</button>
                                    )}
                                  </div>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                      {!filteredCategories.length && <Empty title="No matching collections" detail="Try another filter or create an app collection." />}
                    </div>
                  )}
                  {section === "categories" && categoryHasMore && (
                    <div className="flex justify-center border-t border-base-200 p-3">
                      <button className="btn btn-outline btn-sm" disabled={loading} onClick={() => void loadCatalogue(products.length, categories.length, true)}>
                        {loading ? <span className="loading loading-spinner loading-sm" /> : "Load more collections"}
                      </button>
                    </div>
                  )}
                </article>
              </>
            )}

            {/* CUSTOMERS DIRECTORY (Thumper CRM Layout: media_1795500316676_358b8775.png) */}
            {section === "customers" && (role === "super_admin" || role === "admin") && (
              <>
                <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
                  <div>
                    <div className="breadcrumbs text-xs text-base-content/60">Collections / <strong>Customers</strong></div>
                    <h1 className="text-2xl font-bold tracking-tight">Customer Directory</h1>
                    <p className="text-sm text-base-content/65">Customer profile and business details supplied during account registration.</p>
                  </div>
                  <button className="btn btn-sm btn-outline" onClick={() => void loadCustomers()}>Refresh</button>
                </div>

                <article className="card panel table-panel border border-base-200 rounded-xl overflow-hidden">
                  {/* Role Filter Tabs */}
                  <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 border-b border-base-200 bg-base-100">
                    <div className="flex flex-wrap items-center gap-1.5">
                      {[
                        ["all", "All"],
                        ["end_user", "End Users"],
                        ["reseller", "Resellers"],
                        ["epc", "EPC Contractors"],
                        ["distributor", "Distributors"],
                      ].map(([key, label]) => (
                        <button
                          key={key}
                          className={`btn btn-xs rounded-lg font-semibold ${customerRoleFilter === key ? "btn-primary text-white" : "btn-ghost text-base-content/70"}`}
                          onClick={() => setCustomerRoleFilter(key as typeof customerRoleFilter)}
                        >
                          {label}
                        </button>
                      ))}
                    </div>

                    <label className="input input-bordered input-sm flex w-full min-w-0 items-center gap-2 rounded-lg sm:w-80">
                      <span aria-hidden="true" className="text-base-content/40">⌕</span>
                      <input
                        className="min-w-0 flex-1"
                        placeholder="Search name, company, email, phone, GST..."
                        value={query}
                        onChange={(event) => setQuery(event.target.value)}
                        aria-label="Search customers"
                      />
                    </label>
                  </div>

                  {/* Thumper Table */}
                  <div className="overflow-x-auto">
                    <table className="table content-table w-full">
                      <thead>
                        <tr>
                          <th>Customer Name</th>
                          <th>Account Role</th>
                          <th>Company</th>
                          <th>GSTIN</th>
                          <th>Contact Details</th>
                          <th>Location</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-base-200">
                        {filteredCustomers.map((profile) => {
                          const initial = (profile.name || profile.email || "C").slice(0, 1).toUpperCase();
                          const roleBadges: Record<string, string> = {
                            end_user: "bg-blue-100 text-blue-800 border-blue-200",
                            reseller: "bg-emerald-100 text-emerald-800 border-emerald-200",
                            epc: "bg-purple-100 text-purple-800 border-purple-200",
                            distributor: "bg-amber-100 text-amber-800 border-amber-200",
                          };

                          return (
                            <tr key={profile.id} className="hover:bg-base-200/40 transition-colors">
                              <td>
                                <div className="flex items-center gap-3">
                                  <div className="w-9 h-9 rounded-full bg-primary/10 text-primary font-bold flex items-center justify-center shrink-0 text-sm">
                                    {initial}
                                  </div>
                                  <div>
                                    <strong className="block font-semibold text-base-content">{profile.name}</strong>
                                    <span className="block text-xs text-base-content/55 font-mono">{profile.email}</span>
                                  </div>
                                </div>
                              </td>
                              <td>
                                <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-bold border tracking-wider uppercase ${roleBadges[profile.customer_type] || "bg-base-200 text-base-content"}`}>
                                  {profile.customer_type.replaceAll("_", " ")}
                                </span>
                              </td>
                              <td>
                                <strong className="text-xs text-base-content font-medium">
                                  {profile.company_name || "—"}
                                </strong>
                              </td>
                              <td>
                                {profile.gst_number ? (
                                  <span className="font-mono text-xs px-2 py-0.5 rounded-md bg-base-200 border border-base-300 font-semibold tracking-wider text-base-content/85">
                                    {profile.gst_number}
                                  </span>
                                ) : (
                                  <span className="text-base-content/40 text-xs">—</span>
                                )}
                              </td>
                              <td>
                                <div className="text-xs">
                                  <span className="font-mono block text-base-content">{profile.mobile_number}</span>
                                </div>
                              </td>
                              <td>
                                <span className="text-xs text-base-content/75 capitalize">{profile.location}</span>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                    {!filteredCustomers.length && (
                      <Empty title="No customer profiles found" detail="Customer details appear after a user registers and completes onboarding in the mobile app." />
                    )}
                    {customersHasMore && (
                      <div className="flex justify-center border-t border-base-200 p-4">
                        <button className="btn btn-outline btn-sm" disabled={loading} onClick={() => void loadCustomers(customerProfiles.length, true)}>
                          {loading ? <span className="loading loading-spinner loading-sm" /> : "Load more customers"}
                        </button>
                      </div>
                    )}
                  </div>
                </article>
              </>
            )}

            {/* CUSTOMER REQUESTS & ENQUIRIES */}
            {(["service", "quotes", "warranty", "amc"].includes(section)) && (
              <>
                <div className="page-heading">
                  <div>
                    <p className="eyebrow">CUSTOMER OPERATIONS</p>
                    <h1>{title}</h1>
                    <p>Review customer submissions, update status, and share a progress note.</p>
                  </div>
                  <button className="btn btn-outline" onClick={() => void loadRequests(requestKindForSection(section))}>Refresh</button>
                </div>
                <div className="card panel mb-3">
                  <div className="grid gap-3 p-4 sm:grid-cols-[minmax(0,1fr)_15rem]">
                    <label className="form-control gap-1">
                      <span className="label-text">Search requests</span>
                      <input className="input input-bordered input-sm" placeholder="Customer email, model, location, or request ID" maxLength={200} value={requestQuery} onChange={(event) => setRequestQuery(event.target.value)} />
                    </label>
                    <label className="form-control gap-1">
                      <span className="label-text">Filter by status</span>
                      <select className="select select-bordered select-sm" value={requestStatuses[requestKindForSection(section)].includes(requestStatusFilter) ? requestStatusFilter : "all"} onChange={(event) => setRequestStatusFilter(event.target.value)}>
                        <option value="all">All statuses</option>
                        {requestStatuses[requestKindForSection(section)].map((status) => <option key={status} value={status}>{status.replaceAll("_", " ")}</option>)}
                      </select>
                    </label>
                  </div>
                </div>
                <div className="grid gap-3">
                  {loading && customerRequests.length === 0 ? (
                    <div className="card panel empty-state"><span className="loading loading-spinner text-primary" /></div>
                  ) : customerRequests.length === 0 ? (
                    <article className="card panel"><Empty title="No requests yet" detail="Customer service requests and quote enquiries appear here after submission." /></article>
                  ) : (
                    customerRequests.map((record) => (
                      <article className="card panel" key={record.id}>
                        <header className="panel-head">
                          <div>
                            <h2>{record.kind === "service" ? String(record.payload.product_model ?? "Service request") : record.kind === "warranty" ? "Warranty registration" : record.kind === "amc" ? "AMC request" : String(record.payload.application ?? "Quote enquiry")}</h2>
                            <p>{record.customer_name ? `${record.customer_name} · ` : ""}{record.customer_email} · {new Date(record.created_at).toLocaleString()}</p>
                          </div>
                          <span className="badge badge-info">{record.status.replaceAll("_", " ")}</span>
                        </header>
                        <div className="grid gap-4 p-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
                          <div className="text-sm leading-6 text-base-content/75">
                            <div className="mb-3 flex flex-wrap gap-x-5 gap-y-1 rounded-box bg-base-200/60 p-3">
                              <span><strong className="text-base-content">Customer:</strong> {record.customer_name || "Profile not completed"}</span>
                              {record.customer_phone && <a className="link link-primary" href={`tel:${encodeURIComponent(record.customer_phone)}`}>{record.customer_phone}</a>}
                              {record.customer_company && <span>{record.customer_company}</span>}
                              {record.customer_location && <span>{record.customer_location}</span>}
                              {!record.customer_phone && <span>{record.customer_email}</span>}
                            </div>
                            {(record.kind === "warranty" || record.kind === "amc") && <div><p>Serial number: {String(record.payload.serial_number ?? "")}</p><p>Date of purchase: {String(record.payload.purchase_date ?? "")}</p>{record.kind === "warranty" ? <><p>Customer: {String(record.payload.customer_name ?? "")}</p><p>Email: {String(record.payload.email ?? "")}</p><p>Mobile: {String(record.payload.mobile_number ?? "")}</p></> : <p>Location: {String(record.payload.location ?? "")}</p>}</div>}
                            {record.kind !== "warranty" && record.kind !== "amc" && <strong className="text-base-content">{record.kind === "service" ? "Problem Description" : "Equipment or Load"}</strong>}
                            {record.kind !== "warranty" && record.kind !== "amc" && <p className="whitespace-pre-wrap">{String(record.payload.description ?? record.payload.equipment_or_load ?? "")}</p>}
                            {record.kind !== "warranty" && record.kind !== "amc" && <p className="mt-2">Location: {String(record.payload.service_location ?? record.payload.project_location ?? "Not provided")}</p>}
                            <p>Reference: {record.id.slice(0, 8).toUpperCase()}</p>
                            {record.kind === "service" && Array.isArray(record.payload.attachments) && record.payload.attachments.length > 0 && (
                              <div className="mt-3">
                                <strong className="mb-1.5 block text-xs uppercase tracking-wider text-base-content/60">
                                  Attached Customer Photos ({record.payload.attachments.length})
                                </strong>
                                <div className="flex flex-wrap gap-2">
                                  {record.payload.attachments
                                    .filter((item): item is string => typeof item === "string" && item.startsWith("https://"))
                                    .map((photoUrl, idx) => (
                                      <a
                                        key={`${photoUrl}-${idx}`}
                                        href={photoUrl}
                                        target="_blank"
                                        rel="noreferrer"
                                        className="group relative block h-20 w-20 overflow-hidden rounded-lg border border-base-300 bg-base-200 hover:border-primary"
                                        title={`Open photo ${idx + 1}`}
                                      >
                                        <Image src={photoUrl} alt={`Service fault photo ${idx + 1}`} fill sizes="80px" unoptimized className="object-cover group-hover:scale-105 transition-transform" />
                                      </a>
                                    ))}
                                </div>
                              </div>
                            )}
                          </div>
                          <div className="space-y-2">
                            <label className="form-control gap-1">
                              <span className="label-text">Update status</span>
                              <select className="select select-bordered select-sm" defaultValue={record.status} id={`status-${record.id}`}>
                                <option value={record.status}>{record.status.replaceAll("_", " ")} (current)</option>
                                {(requestTransitions[record.kind]?.[record.status] ?? []).map((status) => <option key={status} value={status}>{status.replaceAll("_", " ")}</option>)}
                              </select>
                            </label>
                            <label className="form-control gap-1">
                              <span className="label-text">Assign to active staff</span>
                              <select className="select select-bordered select-sm" value={requestAssignees[record.id] ?? ""} onChange={(event) => setRequestAssignees((current) => ({ ...current, [record.id]: event.target.value }))}>
                                <option value="">Unassigned</option>
                                {record.assigned_to && !assignableStaff.some((staff) => staff.firebase_uid === record.assigned_to) && <option value={record.assigned_to}>Inactive or unavailable · {record.assigned_to.slice(0, 8)}</option>}
                                {assignableStaff.map((staff) => <option key={staff.firebase_uid} value={staff.firebase_uid}>{staff.display_name || staff.email || staff.firebase_uid} · {staff.role.replaceAll("_", " ")}</option>)}
                              </select>
                              {!assignableStaff.length && <span className="label-text-alt">No active administrators are available for assignment.</span>}
                            </label>
                            <label className="form-control gap-1">
                              <span className="label-text">Customer update note</span>
                              <textarea className="textarea textarea-bordered textarea-sm" maxLength={2000} value={requestNotes[record.id] ?? record.resolution_note ?? ""} onChange={(event) => setRequestNotes((current) => ({ ...current, [record.id]: event.target.value }))} />
                            </label>
                              <button className="btn btn-primary btn-sm" onClick={() => { const select = document.getElementById(`status-${record.id}`) as HTMLSelectElement | null; void updateCustomerRequest(record, select?.value ?? record.status, requestAssignees[record.id] ?? ""); }}>
                              Save update
                            </button>
                          </div>
                        </div>
                      </article>
                    ))
                  )}
                  {requestsHasMore && (
                    <div className="flex justify-center p-2">
                      <button className="btn btn-outline btn-sm" disabled={loading} onClick={() => void loadRequests(requestKindForSection(section), customerRequests.length, true)}>
                        {loading ? <span className="loading loading-spinner loading-sm" /> : "Load older requests"}
                      </button>
                    </div>
                  )}
                </div>
              </>
            )}

            {section === "contact_inquiries" && (
              <>
                <div className="page-heading">
                  <div>
                    <p className="eyebrow">CUSTOMER OPERATIONS</p>
                    <h1>{title}</h1>
                    <p>Messages from signed-in customers. Status and internal notes are recorded in the audit history.</p>
                  </div>
                  <button className="btn btn-outline" onClick={() => void loadContactInquiries()}>Refresh</button>
                </div>
                <div className="card panel mb-4">
                  <div className="grid gap-3 p-4 sm:grid-cols-[minmax(0,1fr)_13rem]">
                    <label className="form-control gap-1">
                      <span className="label-text">Search enquiries</span>
                      <input className="input input-bordered input-sm" type="search" maxLength={200} value={inquiryQuery} onChange={(event) => setInquiryQuery(event.target.value)} placeholder="Name, email, company, subject or message" />
                    </label>
                    <label className="form-control gap-1">
                      <span className="label-text">Status</span>
                      <select className="select select-bordered select-sm" value={inquiryStatusFilter} onChange={(event) => setInquiryStatusFilter(event.target.value)}>
                        <option value="all">All statuses</option>
                        <option value="new">New</option>
                        <option value="in_progress">In progress</option>
                        <option value="waiting_for_customer">Waiting for customer</option>
                        <option value="resolved">Resolved</option>
                        <option value="closed">Closed</option>
                      </select>
                    </label>
                  </div>
                </div>
                <div className="mb-3 text-sm text-base-content/60">Showing {contactInquiries.length} matching enquiries.</div>
                <div className="grid gap-3">
                  {loading ? (
                    <div className="card panel empty-state"><span className="loading loading-spinner text-primary" /></div>
                  ) : contactInquiries.length === 0 ? (
                    <article className="card panel"><Empty title="No contact enquiries" detail="New customer messages will appear here." /></article>
                  ) : contactInquiries.map((record) => (
                    <article className="card panel" key={record.id}>
                      <header className="panel-head">
                        <div>
                          <h2>{record.subject || "Customer enquiry"}</h2>
                          <p>{record.name} · {new Date(record.created_at).toLocaleString()}</p>
                        </div>
                        <span className={`badge ${record.status === "new" ? "badge-warning" : record.status === "resolved" || record.status === "closed" ? "badge-success" : "badge-info"}`}>{record.status.replaceAll("_", " ")}</span>
                      </header>
                      <div className="grid gap-4 p-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
                          <div className="space-y-2 text-sm leading-6 text-base-content/75">
                          <div className="flex flex-wrap gap-x-4 gap-y-1">
                            <a className="link link-primary" href={`mailto:${encodeURIComponent(record.email)}`}>{record.email}</a>
                            <a className="link link-primary" href={`tel:${encodeURIComponent(record.phone)}`}>{record.phone}</a>
                          </div>
                          <p>Type: {record.inquiry_type.replaceAll("_", " ")}{record.company_name ? ` · ${record.company_name}` : ""}</p>
                          <p className="whitespace-pre-wrap rounded-box bg-base-200/60 p-3 text-base-content">{record.message}</p>
                          <p className="text-xs">Reference: {record.id.slice(0, 8).toUpperCase()}</p>
                        </div>
                        <div className="space-y-2">
                          <label className="form-control gap-1">
                            <span className="label-text">Update status</span>
                            <select className="select select-bordered select-sm" value={inquiryStatuses[record.id] ?? record.status} onChange={(event) => setInquiryStatuses((current) => ({ ...current, [record.id]: event.target.value as ContactInquiry["status"] }))}>
                              <option value="new">New</option>
                              <option value="in_progress">In progress</option>
                              <option value="waiting_for_customer">Waiting for customer</option>
                              <option value="resolved">Resolved</option>
                              <option value="closed">Closed</option>
                            </select>
                          </label>
                          <label className="form-control gap-1">
                            <span className="label-text">Internal notes</span>
                            <textarea className="textarea textarea-bordered textarea-sm" maxLength={2000} value={inquiryNotes[record.id] ?? ""} onChange={(event) => setInquiryNotes((current) => ({ ...current, [record.id]: event.target.value }))} />
                          </label>
                          <button className="btn btn-primary btn-sm" onClick={() => void updateContactInquiry(record)}>Save enquiry update</button>
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
                {!loading && inquiryHasMore && <div className="mt-4 flex justify-center"><button className="btn btn-outline" onClick={() => void loadContactInquiries(contactInquiries.length, true)}>Load older enquiries</button></div>}
              </>
            )}

            {/* APP CONTENT EDITORS */}
            {section === "app_content" && (
              <>
                <div className="page-heading">
                  <div>
                    <p className="eyebrow">CUSTOMER MOBILE APP</p>
                    <h1>App Content &amp; Configuration</h1>
                    <p>Configure Home, contacts, Solution Finder, chat, and brand logo; publish updates directly to the mobile app.</p>
                  </div>
                  <div className="page-actions">
                    <button className="btn btn-outline btn-sm" onClick={() => void saveContent()}>Save draft</button>
                    <button className="btn btn-primary btn-sm" disabled={!content || content.draft_revision === 0} onClick={() => void publish(`/admin/app-config/${appContentTab}/publish`)}>Publish to App</button>
                    {(role === "admin" || role === "super_admin") && content?.published_payload && <button className="btn btn-outline btn-error btn-sm" onClick={() => void unpublish(`/admin/app-config/${appContentTab}/unpublish`)}>Unpublish</button>}
                  </div>
                </div>

                <div className="tabs tabs-boxed mb-4 inline-flex flex-wrap gap-1 rounded-lg bg-base-200/70 p-1">
                  {appContentTabs.map((tab) => (
                    <button
                      key={tab.key}
                      className={`tab tab-sm rounded-md font-semibold ${appContentTab === tab.key ? "tab-active bg-base-100 text-primary shadow-xs" : "text-base-content/70"}`}
                      onClick={() => setAppContentTab(tab.key)}
                    >
                      {tab.title}
                    </button>
                  ))}
                </div>

                {loading ? (
                  <div className="card panel empty-state"><span className="loading loading-spinner text-primary" /></div>
                ) : (
                  <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_18rem]">
                    <div className="grid gap-4 min-w-0">
                      <article className="card panel">
                        <header className="panel-head">
                          <div>
                            <h2>Edit {appContentTabs.find((t) => t.key === appContentTab)?.title}</h2>
                            <p>Save draft first, then click Publish to App.</p>
                          </div>
                        </header>
                        <div className="grid min-w-0 gap-4 p-4 sm:grid-cols-2">
                          {Object.entries(contentDraft).map(([key, value]) => (
                            <ContentField key={key} field={key} value={value} categories={categories} products={products} onChange={(next) => setContentDraft((current) => ({ ...current, [key]: next }))} />
                          ))}
                          {appContentTab === "home" && (productHasMore || categoryHasMore) && (
                            <div className="flex flex-col gap-2 rounded-lg border border-base-300 p-3 sm:col-span-2 sm:flex-row sm:items-center sm:justify-between">
                              <p className="text-sm text-base-content/70">Featured selectors include {products.length} products and {categories.length} collections.</p>
                              <button className="btn btn-outline btn-sm" disabled={loading} onClick={() => void loadCatalogue(products.length, categories.length, true, "")}>Load more options</button>
                            </div>
                          )}
                        </div>
                      </article>
                      <ContentComparison defaultOpen={false} draft={contentDraft} published={content?.published_payload ?? null} />
                    </div>
                    <aside className="card panel h-fit xl:sticky xl:top-20">
                      <header className="panel-head">
                        <div><h2>Publication status</h2><p>App delivery</p></div>
                      </header>
                      <div className="space-y-3 p-4 text-sm">
                        <div className="flex items-center justify-between">
                          <span className="text-base-content/65">Draft revision</span>
                          <strong>{content?.draft_revision ?? 0}</strong>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-base-content/65">Published revision</span>
                          <strong>{content?.published_revision ?? "None"}</strong>
                        </div>
                        <div className="text-xs text-base-content/65">
                          Last update: <strong>{content?.updated_at ? new Date(content.updated_at).toLocaleString() : "Not saved"}</strong>
                        </div>
                        <div className={content?.published_payload ? "alert alert-success py-2 text-xs" : "alert alert-info py-2 text-xs"}>
                          {content?.published_payload ? "Published version is active in the mobile app." : "Not published yet; app uses local defaults."}
                        </div>
                      </div>
                    </aside>
                  </div>
                )}
              </>
            )}

            {/* WORDPRESS SYNC TOOL */}
            {section === "wordpress" && (
              <>
                <div className="page-heading">
                  <div>
                    <p className="eyebrow">CATALOGUE SOURCE</p>
                    <h1>WooCommerce Sync &amp; Integration</h1>
                    <p>Syncs products, prices, stock, and specs from WordPress while respecting CMS collection &amp; PDF overrides.</p>
                  </div>
                  <div className="page-actions">
                    <button className="btn btn-outline btn-sm" disabled={wpConnectionLoading} onClick={() => void wordpressPreview()}>Preview Source</button>
                    <button className="btn btn-primary btn-sm" disabled={wpConnectionLoading || !wpSyncReady} onClick={() => void wordpressSync()}>Sync Catalogue Now</button>
                  </div>
                </div>
                <div className="card panel">
                  <header className="panel-head">
                    <div>
                      <h2>WooCommerce Connection</h2>
                      <p>Authenticated REST with Store API fallback; CMS-pinned collections &amp; PDFs are preserved automatically.</p>
                    </div>
                    <button className="btn btn-outline btn-xs" disabled={wpConnectionLoading} onClick={() => void loadWordPressStatus()}>Check Status</button>
                  </header>
                  <div className="p-4 space-y-4">
                    <div className={`alert py-3 text-sm ${wpSyncReady ? "alert-success" : "alert-warning"}`} role="status">
                      <div className="flex flex-wrap items-center justify-between gap-2 w-full">
                        <div>
                          <strong>{wpConnectionLoading ? "Checking WooCommerce settings…" : wpSyncReady ? wpConnection?.authenticated ? "WooCommerce REST Connected" : "Store API Fallback Ready" : "WooCommerce sync not configured"}</strong>
                          <p className="text-xs opacity-85 mt-0.5">{wpConnection?.site || wpConnection?.message || "Verify environment settings in Coolify."}</p>
                        </div>
                        {wpConnection?.authenticated && <span className="badge badge-sm badge-outline">Authenticated REST</span>}
                      </div>
                    </div>

                    {lastWpSync && (
                      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                        <div className="rounded-lg border border-base-200 bg-base-200/40 p-3">
                          <span className="text-xs text-base-content/60">Products Synced</span>
                          <strong className="mt-1 block text-lg">{(lastWpSync.created ?? 0) + (lastWpSync.updated ?? 0)}</strong>
                          <span className="text-[11px] text-base-content/55">{lastWpSync.created ?? 0} new · {lastWpSync.updated ?? 0} updated</span>
                        </div>
                        <div className="rounded-lg border border-base-200 bg-base-200/40 p-3">
                          <span className="text-xs text-base-content/60">PDFs Linked</span>
                          <strong className="mt-1 block text-lg">{lastWpSync.documents_linked ?? 0}</strong>
                        </div>
                        <div className="rounded-lg border border-base-200 bg-base-200/40 p-3">
                          <span className="text-xs text-base-content/60">CMS Overrides Kept</span>
                          <strong className="mt-1 block text-lg">{lastWpSync.cms_preserved_category_products ?? 0}</strong>
                          <span className="text-[11px] text-base-content/55">{lastWpSync.cms_preserved_pdf_products ?? 0} PDFs</span>
                        </div>
                        <div className="rounded-lg border border-base-200 bg-base-200/40 p-3">
                          <span className="text-xs text-base-content/60">Media / Withdrawn</span>
                          <strong className="mt-1 block text-lg">{lastWpSync.media_pdf_count ?? 0}</strong>
                          <span className="text-[11px] text-base-content/55">{lastWpSync.withdrawn ?? 0} withdrawn</span>
                        </div>
                      </div>
                    )}

                    {wpStatus && <p className="text-xs font-medium text-base-content/75" role="status">{wpStatus}</p>}
                    {wpPreview.length > 0 && (
                      <div className="overflow-x-auto">
                        <table className="table table-sm">
                          <thead>
                            <tr><th>Source ID</th><th>Title</th><th>Slug</th><th>Source URL</th><th>Status</th></tr>
                          </thead>
                          <tbody>
                            {wpPreview.map((row, index) => (
                              <tr key={String(row.id ?? index)}>
                                <td>{String(row.id ?? "—")}</td>
                                <td>{String(row.title ?? "—")}</td>
                                <td>{String(row.slug ?? "—")}</td>
                                <td className="max-w-52 truncate">{String(row.link ?? "—")}</td>
                                <td><span className="badge badge-outline badge-sm">Source record</span></td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                </div>
              </>
            )}

            {/* KNOWLEDGE ARTICLES */}
            {section === "knowledge" && (
              <>
                <div className="page-heading">
                  <div>
                    <p className="eyebrow">CUSTOMER SUPPORT</p>
                    <h1>FAQs & Knowledge</h1>
                    <p>Publish customer FAQs with formatted answers, photos, links, or videos.</p>
                  </div>
                  <button className="btn btn-primary" onClick={() => { setKnowledgeForm(emptyKnowledge); setKnowledgeVideoInput(""); setKnowledgePreview(false); setKnowledgeSlugTouched(false); setEditingKnowledge(null); setShowKnowledgeForm(true); }}>+ Add answer</button>
                </div>
                <article className="card panel">
                  <div className="table-toolbar">
                    <label className="input input-bordered input-sm">
                      <span aria-hidden="true">⌕</span>
                      <input placeholder="Search questions..." value={query} onChange={(event) => setQuery(event.target.value)} aria-label="Search knowledge" />
                    </label>
                    <span className="text-xs text-base-content/55">{loading ? "Loading…" : `${knowledgeArticles.length} answers`}</span>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="table content-table">
                      <thead>
                        <tr><th>Question</th><th>Category</th><th>Source</th><th>Status</th><th>Actions</th></tr>
                      </thead>
                      <tbody>
                        {knowledgeArticles.map((article) => (
                          <tr key={article.id}>
                            <td>
                              <strong className="text-base-content">{article.title}</strong>
                              <span className="block max-w-xl truncate text-xs text-base-content/60">{article.answer}</span>
                            </td>
                            <td>{article.category}</td>
                            <td className="text-xs text-base-content/70">{article.source_reference || "—"}</td>
                            <td><span className={`badge ${article.is_published ? "badge-success" : "badge-ghost"}`}>{article.is_published ? "Published" : "Draft"}</span></td>
                            <td>
                              <div className="flex gap-1">
                                <button className="btn btn-ghost btn-xs" onClick={() => { const imgs = article.image_urls ?? []; const vids = article.video_urls ?? []; setKnowledgeForm({ ...article, image_urls: imgs, video_urls: vids }); setKnowledgeVideoInput(""); setKnowledgePreview(false); setKnowledgeSlugTouched(true); setEditingKnowledge(article.id); setShowKnowledgeForm(true); }}>Edit</button>
                                {(!article.is_published || article.has_draft) && <button className="btn btn-primary btn-xs" onClick={async () => { setError(""); try { await api(user, `/admin/knowledge/${article.id}/publish`, { method: "POST" }); setNotice("FAQ published to the app."); await loadKnowledge(); } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not publish FAQ."); } }}>Publish</button>}
                                {article.is_published && (role === "admin" || role === "super_admin") && <button className="btn btn-ghost btn-xs text-error" onClick={() => void unpublish(`/admin/knowledge/${article.id}/unpublish`)}>Unpublish</button>}
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {!knowledgeArticles.length && <Empty title="No articles found" detail="Add approved technical answers and solutions." />}
                    {knowledgeHasMore && (
                      <div className="flex justify-center border-t border-base-200 p-4">
                        <button className="btn btn-outline btn-sm" disabled={loading} onClick={() => void loadKnowledge(knowledgeArticles.length, true)}>
                          {loading ? <span className="loading loading-spinner loading-sm" /> : "Load more answers"}
                        </button>
                      </div>
                    )}
                  </div>
                </article>
              </>
            )}

            {/* ADMIN ACCESS */}
            {section === "admins" && role === "super_admin" && (
              <>
                <div className="page-heading">
                  <div>
                    <p className="eyebrow">ACCESS CONTROL</p>
                    <h1>Admin Access & Roles</h1>
                    <p>Manage administrative CMS privileges for team members.</p>
                  </div>
                  <button className="btn btn-outline" onClick={() => void loadAdmins()}>Refresh</button>
                </div>
                <article className="card panel mb-4">
                  <header className="panel-head">
                    <div><h2>{editingAdminUid ? "Edit CMS account" : "Grant CMS access"}</h2></div>
                  </header>
                  <form onSubmit={submitAdmin} className="grid gap-3 p-4 sm:grid-cols-2">
                    <label className="form-control gap-1"><span className="label-text">Firebase UID</span><input className="input input-bordered input-sm" required minLength={1} maxLength={128} disabled={Boolean(editingAdminUid)} value={adminForm.firebase_uid} onChange={(e) => setAdminForm({ ...adminForm, firebase_uid: e.target.value })} /></label>
                    <label className="form-control gap-1"><span className="label-text">Email</span><input className="input input-bordered input-sm" type="email" value={adminForm.email} onChange={(e) => setAdminForm({ ...adminForm, email: e.target.value })} /></label>
                    <label className="form-control gap-1"><span className="label-text">Display name</span><input className="input input-bordered input-sm" value={adminForm.display_name} onChange={(e) => setAdminForm({ ...adminForm, display_name: e.target.value })} /></label>
                    <label className="form-control gap-1"><span className="label-text">Role</span><select className="select select-bordered select-sm" value={adminForm.role} onChange={(e) => setAdminForm({ ...adminForm, role: e.target.value as AdminAccount["role"] })}><option value="content_editor">Content editor</option><option value="admin">Admin</option><option value="super_admin">Super-admin</option></select></label>
                    <div className="flex items-center gap-2 sm:col-span-2 sm:justify-end">
                      <button type="button" className="btn btn-ghost btn-sm" onClick={() => { setEditingAdminUid(null); setAdminForm({ firebase_uid: "", email: "", display_name: "", role: "content_editor", is_active: true }); }}>Clear</button>
                      <button className="btn btn-primary btn-sm">{editingAdminUid ? "Save access" : "Grant access"}</button>
                    </div>
                  </form>
                </article>
                <article className="card panel">
                  <div className="overflow-x-auto">
                    <table className="table content-table">
                      <thead>
                        <tr><th>Administrator</th><th>Firebase UID</th><th>Role</th><th>Status</th><th>Actions</th></tr>
                      </thead>
                      <tbody>
                        {adminAccounts.map((account) => (
                          <tr key={account.id}>
                            <td><strong>{account.display_name || account.email || "Admin"}</strong></td>
                            <td className="font-mono text-xs">{account.firebase_uid}</td>
                            <td><span className="badge badge-outline">{account.role}</span></td>
                            <td><span className={account.is_active ? "badge badge-success" : "badge badge-error"}>{account.is_active ? "Active" : "Disabled"}</span></td>
                            <td><button className="btn btn-ghost btn-xs" onClick={() => { setEditingAdminUid(account.firebase_uid); setAdminForm({ firebase_uid: account.firebase_uid, email: account.email || "", display_name: account.display_name || "", role: account.role, is_active: account.is_active }); window.scrollTo({ top: 0, behavior: "smooth" }); }}>Edit</button></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </article>
              </>
            )}

            {/* AUDIT HISTORY */}
            {section === "audit" && (role === "super_admin" || role === "admin") && (
              <>
                <div className="page-heading">
                  <div>
                    <p className="eyebrow">CHANGE HISTORY</p>
                    <h1>Audit History</h1>
                    <p>Platform modifications, publishing events, and role updates.</p>
                  </div>
                  <div className="page-actions">
                    <button className="btn btn-outline" disabled={!auditEvents.length} onClick={exportLoadedAudit}>Export loaded events</button>
                    <button className="btn btn-outline" onClick={() => void loadAudit()}>Refresh</button>
                  </div>
                </div>
                <article className="card panel">
                  <div className="grid gap-3 border-b border-base-200 p-4 sm:grid-cols-[minmax(0,1fr)_15rem]">
                    <label className="form-control gap-1">
                      <span className="label-text">Search audit history</span>
                      <input className="input input-bordered input-sm" maxLength={200} placeholder="Actor, action, entity ID, or summary" value={auditQuery} onChange={(event) => setAuditQuery(event.target.value)} />
                    </label>
                    <label className="form-control gap-1">
                      <span className="label-text">Entity type</span>
                      <select className="select select-bordered select-sm" value={auditEntityFilter} onChange={(event) => setAuditEntityFilter(event.target.value)}>
                        <option value="all">All entities</option>
                        {["app_config", "admin_account", "catalogue_sync", "contact_inquiry", "customer_profile", "customer_request", "knowledge_article", "media_asset", "product", "product_category"].map((entityType) => <option key={entityType} value={entityType}>{entityType.replaceAll("_", " ")}</option>)}
                      </select>
                    </label>
                    <p className="text-xs text-base-content/60 sm:col-span-2">Export includes the {auditEvents.length} filtered events currently loaded. Load more before exporting larger result sets.</p>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="table content-table">
                      <thead>
                        <tr><th>When</th><th>Action</th><th>Entity</th><th>Actor UID</th><th>Summary</th></tr>
                      </thead>
                      <tbody>
                        {auditEvents.map((event) => (
                          <tr key={event.id}>
                            <td className="text-xs">{new Date(event.created_at).toLocaleString()}</td>
                            <td><strong className="text-base-content">{event.action.replaceAll("_", " ")}</strong></td>
                            <td>{event.entity_type} · {event.entity_id}</td>
                            <td className="font-mono text-xs">{event.actor_uid}</td>
                            <td className="max-w-64 truncate text-xs">{JSON.stringify(event.change_summary)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {!auditEvents.length && <Empty title="No audit events recorded" detail="Audit logs are recorded whenever CMS changes are saved." />}
                    {auditHasMore && (
                      <div className="flex justify-center border-t border-base-200 p-4">
                        <button className="btn btn-outline btn-sm" disabled={loading} onClick={() => void loadAudit(auditEvents.length, true)}>
                          {loading ? <span className="loading loading-spinner loading-sm" /> : "Load older events"}
                        </button>
                      </div>
                    )}
                  </div>
                </article>
              </>
            )}
          </main>
        </div>
      </div>

      {showCreateCollection && <CreateCollectionModal key={collectionEditorTarget?.id ?? "new"} target={collectionEditorTarget} user={user} onClose={() => { setShowCreateCollection(false); setCollectionEditorTarget(null); }} onNotice={setNotice} onError={setError} onRefresh={loadCatalogue} />}

      {assignTarget && <AssignProductsModal target={assignTarget} user={user} onClose={() => setAssignTarget(null)} onNotice={setNotice} onError={setError} onRefresh={loadCatalogue} />}

      {cataloguePdfTarget && (
        <CollectionCataloguePdfModal
          key={cataloguePdfTarget.id}
          target={cataloguePdfTarget}
          catalogueRecord={categoryCatalogues.find((c) => c.category_id === cataloguePdfTarget.id || c.category_key === cataloguePdfTarget.slug)}
          onClose={() => setCataloguePdfTarget(null)}
          user={user}
          onNotice={setNotice}
          onError={setError}
          onRefresh={loadCatalogue}
        />
      )}

      {productPdfTarget && (
        <ProductPdfOverrideModal
          key={productPdfTarget.id}
          target={productPdfTarget}
          onClose={() => setProductPdfTarget(null)}
          user={user}
          onNotice={setNotice}
          onError={setError}
          onRefresh={loadCatalogue}
        />
      )}

      {productCategoryTarget && (
        <ProductCategoryOverrideModal
          key={productCategoryTarget.id}
          target={productCategoryTarget}
          categories={categories}
          onClose={() => setProductCategoryTarget(null)}
          user={user}
          onNotice={setNotice}
          onError={setError}
          onRefresh={loadCatalogue}
        />
      )}

      {/* EDIT/CREATE PRODUCT MODAL */}
      {showProductForm && (
        <dialog open className="modal modal-open">
          <div className="modal-box max-h-[90dvh] overflow-y-auto max-w-3xl">
            <h2 className="text-xl font-bold">{editingProduct ? "Edit Product" : "New Product"}</h2>
            <p className="mb-4 mt-1 text-sm text-base-content/60">Configure product specifications, images, and downloadable PDF datasheets.</p>
            <form onSubmit={submitProduct} className="grid gap-3 sm:grid-cols-2">
              <label className="form-control gap-1">
                <span className="label-text font-semibold">Collection / Category</span>
                <select className="select select-bordered" required value={productForm.category_id} onChange={(event) => { const category_id = event.target.value; setProductForm({ ...productForm, category_id, category_ids: [...new Set([category_id, ...(productForm.category_ids ?? []).filter((id) => id !== productForm.category_id)])] }); }}>
                  <option value="">Choose a category</option>
                  {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
                </select>
              </label>
              <fieldset className="form-control gap-2 sm:col-span-2">
                <legend className="label-text font-semibold">Also show in collections</legend>
                <p className="text-xs text-base-content/60">Choose every collection where this product should appear in the app.</p>
                <div className="grid max-h-48 grid-cols-1 gap-1 overflow-y-auto rounded-lg border border-base-300 p-2 sm:grid-cols-2">
                  {categories.map((category) => {
                    const checked = category.id === productForm.category_id || (productForm.category_ids ?? []).includes(category.id);
                    return <label key={category.id} className="label flex cursor-pointer justify-start gap-2 rounded-md px-2 py-1">
                      <input className="checkbox checkbox-sm checkbox-primary" type="checkbox" checked={checked} disabled={category.id === productForm.category_id} onChange={(event) => {
                        const current = new Set([productForm.category_id, ...(productForm.category_ids ?? [])].filter(Boolean));
                        if (event.target.checked) current.add(category.id); else current.delete(category.id);
                        setProductForm({ ...productForm, category_ids: [...current] });
                      }} />
                      <span className="label-text">{category.name}{category.id === productForm.category_id ? " · primary" : ""}</span>
                    </label>;
                  })}
                </div>
              </fieldset>
              {(["name", "slug", "model_code", "summary", "source_reference"] as const).map((field) => (
                <label key={field} className={`form-control gap-1 ${["summary", "source_reference"].includes(field) ? "sm:col-span-2" : ""}`}>
                  <span className="label-text font-semibold">{humanize(field)}</span>
                  <input className="input input-bordered" required={field === "name" || field === "slug" || field === "source_reference"} value={(productForm as typeof emptyProduct)[field] ?? ""} onChange={(event) => setProductForm({ ...productForm, [field]: event.target.value })} />
                </label>
              ))}
              <label className="form-control gap-1 sm:col-span-2">
                <span className="label-text font-semibold">Description</span>
                <textarea className="textarea textarea-bordered min-h-24" value={productForm.description ?? ""} onChange={(event) => setProductForm({ ...productForm, description: event.target.value })} />
              </label>
              <div className="sm:col-span-2"><ImageUrlField value={productForm.image_url ?? ""} onChange={(value) => setProductForm({ ...productForm, image_url: value || null })} /></div>
              <label className="form-control gap-1 sm:col-span-2">
                <span className="label-text font-semibold">Gallery images · one HTTPS URL per line</span>
                <textarea className="textarea textarea-bordered min-h-20" value={(productForm.gallery_images ?? []).join("\n")} onChange={(event) => setProductForm({ ...productForm, gallery_images: event.target.value.split("\n").map((item) => item.trim()).filter(Boolean) })} />
              </label>
              {(["applications", "features"] as const).map((field) => (
                <label className="form-control gap-1" key={field}>
                  <span className="label-text font-semibold">{humanize(field)} · one per line</span>
                  <textarea className="textarea textarea-bordered" value={(productForm[field] ?? []).join("\n")} onChange={(event) => setProductForm({ ...productForm, [field]: event.target.value.split("\n").filter(Boolean) })} />
                </label>
              ))}
              <label className="form-control gap-1">
                <span className="label-text font-semibold">Price ({productForm.currency_code})</span>
                <input className="input input-bordered font-mono" type="number" min="0" inputMode="decimal" step={1 / (10 ** productPriceDigits(productForm))} aria-label={`Price in ${productForm.currency_code}`} placeholder="Enter the published price" value={productForm.price_minor != null ? productForm.price_minor / (10 ** productPriceDigits(productForm)) : ""} onChange={(event) => setProductForm({ ...productForm, price_minor: event.target.value === "" ? null : Math.round(Number(event.target.value) * (10 ** productPriceDigits(productForm))) })} />
              </label>
              <label className="form-control gap-1">
                <span className="label-text font-semibold">Stock Status</span>
                <select className="select select-bordered" value={productForm.stock_status || "unknown"} onChange={(event) => setProductForm({ ...productForm, stock_status: event.target.value as Product["stock_status"] })}>
                  <option value="unknown">Not confirmed</option>
                  <option value="instock">In Stock</option>
                  <option value="outofstock">Out of Stock</option>
                  <option value="onbackorder">Available on Request</option>
                </select>
              </label>
              <label className="form-control gap-1"><span className="label-text font-semibold">Stock quantity (optional)</span><input className="input input-bordered" type="number" min="0" step="1" value={productForm.stock_quantity ?? ""} onChange={(event) => setProductForm({ ...productForm, stock_quantity: event.target.value === "" ? null : Number(event.target.value) })} /></label>
              <fieldset className="form-control gap-2 sm:col-span-2">
                <legend className="font-semibold">Datasheets and documents</legend>
                {(productForm.documents ?? []).map((document, index) => (
                  <div key={`${index}-${document.title}`} className="grid gap-2 rounded-lg border border-base-200 p-2.5 sm:grid-cols-[1fr_2fr_auto]">
                    <input className="input input-bordered input-sm" aria-label={`Document ${index + 1} title`} placeholder="Title" value={document.title} onChange={(event) => { const documents = [...(productForm.documents ?? [])]; documents[index] = { ...document, title: event.target.value }; setProductForm({ ...productForm, documents }); }} />
                    <input className="input input-bordered input-sm" aria-label={`Document ${index + 1} HTTPS URL`} type="url" placeholder="https://…" value={document.url} onChange={(event) => { const documents = [...(productForm.documents ?? [])]; documents[index] = { ...document, url: event.target.value }; setProductForm({ ...productForm, documents }); }} />
                    <button type="button" className="btn btn-ghost btn-sm text-error" aria-label={`Remove document ${index + 1}`} onClick={() => setProductForm({ ...productForm, documents: (productForm.documents ?? []).filter((_, itemIndex) => itemIndex !== index) })}>Remove</button>
                    <div className="sm:col-span-3 flex items-center gap-2">
                      <input
                        className="file-input file-input-bordered file-input-xs w-full max-w-xs"
                        type="file"
                        accept="application/pdf,.pdf"
                        disabled={docUploadingIndex === index}
                        onChange={async (event) => {
                          const file = event.target.files?.[0];
                          const authUser = getFirebaseAuth()?.currentUser;
                          if (!file || !authUser) return;
                          setDocUploadingIndex(index);
                          setError("");
                          try {
                            const asset = await uploadMedia(authUser, file);
                            const nextDocs = [...(productForm.documents ?? [])];
                            const prevDoc = nextDocs[index];
                            nextDocs[index] = {
                              title: prevDoc?.title?.trim() || file.name.replace(/\.pdf$/i, "") || "Product Brochure",
                              url: asset.url,
                            };
                            setProductForm({ ...productForm, documents: nextDocs });
                          } catch (cause) {
                            setError(cause instanceof Error ? cause.message : "PDF upload failed.");
                          } finally {
                            setDocUploadingIndex(null);
                            event.target.value = "";
                          }
                        }}
                      />
                      {docUploadingIndex === index && <span className="text-xs text-base-content/60">Uploading PDF…</span>}
                    </div>
                  </div>
                ))}
                <button type="button" className="btn btn-outline btn-sm w-fit" onClick={() => setProductForm({ ...productForm, documents: [...(productForm.documents ?? []), { title: "", url: "" }] })}>Add document</button>
              </fieldset>
              <label className="form-control gap-1 sm:col-span-2">
                <span className="label-text font-semibold">Specifications (JSON Object)</span>
                <textarea className="textarea textarea-bordered font-mono text-xs" value={specificationsText} onChange={(event) => { setSpecificationsText(event.target.value); try { const parsed = JSON.parse(event.target.value); if (parsed == null || Array.isArray(parsed) || typeof parsed !== "object") throw new Error(); setProductForm({ ...productForm, specifications: parsed as Record<string, unknown> }); setSpecificationsError(""); } catch { setSpecificationsError("Specifications must be a valid JSON object."); } }} />{specificationsError && <span role="alert" className="text-xs text-error">{specificationsError}</span>}
              </label>
              <div className="sm:col-span-2"><ContentComparison defaultOpen={false} draft={{ category_id: productForm.category_id, category_ids: productForm.category_ids, slug: productForm.slug, name: productForm.name, model_code: productForm.model_code, summary: productForm.summary, description: productForm.description, applications: productForm.applications, features: productForm.features, specifications: productForm.specifications, image_url: productForm.image_url, gallery_images: productForm.gallery_images, price_minor: productForm.price_minor, currency_code: productForm.currency_code, currency_minor_unit: productForm.currency_minor_unit, stock_status: productForm.stock_status, stock_quantity: productForm.stock_quantity, documents: productForm.documents, source_reference: productForm.source_reference, wordpress_source_id: productForm.wordpress_source_id, wordpress_source_url: productForm.wordpress_source_url }} published={"published_payload" in productForm ? productForm.published_payload ?? null : null} /></div>
              <div className="modal-action sm:col-span-2">
                <button type="button" className="btn btn-ghost" onClick={() => setShowProductForm(false)}>Close</button>
                <button className="btn btn-primary">Save Product</button>
              </div>
            </form>
          </div>
          <form method="dialog" className="modal-backdrop"><button onClick={() => setShowProductForm(false)}>close</button></form>
        </dialog>
      )}

      {/* EDIT/CREATE KNOWLEDGE MODAL */}
      {showKnowledgeForm && (
        <dialog open className="modal modal-open">
          <div className="modal-box max-h-[90dvh] w-11/12 max-w-3xl overflow-y-auto">
            <div className="mb-4 flex items-center justify-between gap-2">
              <div>
                <h2 className="text-xl font-bold">{editingKnowledge ? "Edit Support FAQ" : "New Support FAQ"}</h2>
                <p className="text-xs text-base-content/60">Write a formatted answer with links, photos, and videos, then publish to Support.</p>
              </div>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowKnowledgeForm(false)}>✕</button>
            </div>
            <form onSubmit={submitKnowledge} className="space-y-4">
              <div className="flex flex-col gap-1.5">
                <span className="text-xs font-semibold text-base-content/80">Question *</span>
                <input
                  className="input input-bordered w-full"
                  required
                  minLength={3}
                  placeholder="e.g. How to check UPS battery health and maintenance?"
                  value={knowledgeForm.title}
                  onChange={(e) => {
                    const nextTitle = e.target.value;
                    const autoSlug = nextTitle.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 140);
                    setKnowledgeForm({
                      ...knowledgeForm,
                      title: nextTitle,
                      slug: !editingKnowledge && !knowledgeSlugTouched ? autoSlug : knowledgeForm.slug,
                    });
                  }}
                />
              </div>

              <div className="grid gap-3 sm:grid-cols-3">
                <div className="flex flex-col gap-1.5">
                  <span className="text-xs font-semibold text-base-content/80">Category</span>
                  <input className="input input-bordered input-sm w-full" maxLength={100} placeholder="General" value={knowledgeForm.category} onChange={(e) => setKnowledgeForm({ ...knowledgeForm, category: e.target.value })} />
                </div>
                <div className="flex flex-col gap-1.5">
                  <span className="text-xs font-semibold text-base-content/80">URL Slug (auto)</span>
                  <input className="input input-bordered input-sm w-full font-mono text-xs" pattern="[a-z0-9]+(?:-[a-z0-9]+)*" placeholder="auto-generated" value={knowledgeForm.slug} onChange={(e) => { setKnowledgeSlugTouched(true); setKnowledgeForm({ ...knowledgeForm, slug: e.target.value }); }} />
                </div>
                <div className="flex flex-col gap-1.5">
                  <span className="text-xs font-semibold text-base-content/80">Display Order</span>
                  <input className="input input-bordered input-sm w-full" type="number" min="0" max="10000" value={knowledgeForm.sort_order} onChange={(e) => setKnowledgeForm({ ...knowledgeForm, sort_order: Number(e.target.value) })} />
                </div>
              </div>

              <div className="rounded-xl border border-base-300 bg-base-100">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-base-200 bg-base-200/40 px-3 py-2">
                  <div className="flex flex-wrap items-center gap-1">
                    <button type="button" className="btn btn-ghost btn-xs" onClick={() => insertKnowledgeSnippet("\n# Heading\n")}>Heading</button>
                    <button type="button" className="btn btn-ghost btn-xs font-bold" onClick={() => insertKnowledgeSnippet("**bold**")}>Bold</button>
                    <button type="button" className="btn btn-ghost btn-xs" onClick={() => insertKnowledgeSnippet("\n- Step or point")}>• Bullet</button>
                    <button type="button" className="btn btn-ghost btn-xs" onClick={() => insertKnowledgeSnippet("\nhttps://")}>+ Link URL</button>
                    <label className="btn btn-ghost btn-xs cursor-pointer">
                      + Upload Image
                      <input className="hidden" type="file" accept="image/png,image/jpeg,image/webp" multiple disabled={knowledgeMediaUploading} aria-label="Upload FAQ images" onChange={(e) => { void uploadKnowledgeFiles(e.target.files, "image_urls"); e.target.value = ""; }} />
                    </label>
                    <label className="btn btn-ghost btn-xs cursor-pointer">
                      + Upload Video
                      <input className="hidden" type="file" accept="video/mp4,video/webm" disabled={knowledgeMediaUploading} aria-label="Upload FAQ video" onChange={(e) => { void uploadKnowledgeFiles(e.target.files, "video_urls"); e.target.value = ""; }} />
                    </label>
                  </div>
                  <div className="join">
                    <button type="button" className={`btn btn-xs join-item ${!knowledgePreview ? "btn-active btn-neutral" : "btn-ghost"}`} onClick={() => setKnowledgePreview(false)}>Write</button>
                    <button type="button" className={`btn btn-xs join-item ${knowledgePreview ? "btn-active btn-neutral" : "btn-ghost"}`} onClick={() => setKnowledgePreview(true)}>Preview</button>
                  </div>
                </div>

                {!knowledgePreview ? (
                  <textarea
                    ref={knowledgeAnswerRef}
                    className="textarea w-full min-h-48 rounded-none border-0 text-sm leading-relaxed focus:outline-none"
                    placeholder={"Write or paste your answer here (or attach an image/video below)...\n\nSupports:\n# Section heading\n- Bullet points\n**Bold text**\nhttps://enertechups.com/... (clickable links)"}
                    value={knowledgeForm.answer}
                    onChange={(e) => setKnowledgeForm({ ...knowledgeForm, answer: e.target.value })}
                  />
                ) : (
                  <div className="min-h-48 space-y-2 p-4 text-sm leading-relaxed">
                    {(knowledgeForm.answer || "").split("\n").map((line, idx) => {
                      const trimmed = line.trim();
                      if (!trimmed) return <div key={idx} className="h-2" />;
                      if (trimmed.startsWith("# ")) return <h3 key={idx} className="text-base font-bold">{trimmed.slice(2)}</h3>;
                      if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) return <p key={idx} className="pl-3">• {trimmed.slice(2)}</p>;
                      return <p key={idx}>{trimmed}</p>;
                    })}
                    {(knowledgeForm.image_urls?.length ?? 0) > 0 && (
                      <div className="grid grid-cols-2 gap-2 pt-2 sm:grid-cols-3">
                        {(knowledgeForm.image_urls ?? []).map((url) => (
                          <img key={url} src={url} alt="FAQ attachment" className="h-28 w-full rounded-lg border border-base-200 object-cover" />
                        ))}
                      </div>
                    )}
                    {(knowledgeForm.video_urls?.length ?? 0) > 0 && (
                      <div className="space-y-1 pt-2 text-xs text-primary">
                        {(knowledgeForm.video_urls ?? []).map((url) => (
                          <p key={url}>▶ {url}</p>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                <div className="space-y-3 border-t border-base-200 bg-base-200/25 p-3">
                  {knowledgeMediaUploading && <p className="text-xs text-primary">Uploading media to cloud storage…</p>}
                  {(knowledgeForm.image_urls?.length ?? 0) > 0 && (
                    <div>
                      <p className="mb-1.5 text-xs font-semibold text-base-content/70">Attached Images ({knowledgeForm.image_urls.length})</p>
                      <div className="flex flex-wrap gap-2">
                        {(knowledgeForm.image_urls ?? []).map((url, index) => (
                          <div key={`${url}-${index}`} className="flex items-center gap-1.5 rounded-lg border border-base-300 bg-base-100 p-1 pr-2 text-xs">
                            <img src={url} alt="" className="h-8 w-8 rounded object-cover" />
                            <a href={url} target="_blank" rel="noreferrer" className="max-w-36 truncate link link-hover">{url.split("/").pop() || "Image"}</a>
                            <button type="button" className="btn btn-ghost btn-xs text-error" onClick={() => setKnowledgeForm({ ...knowledgeForm, image_urls: knowledgeForm.image_urls.filter((_, i) => i !== index) })}>✕</button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="flex flex-col gap-1.5">
                    <span className="text-xs font-semibold text-base-content/70">Add Video Link (YouTube, Vimeo, or direct MP4/WebM URL)</span>
                    <div className="flex gap-2">
                      <input
                        className="input input-bordered input-sm flex-1"
                        type="url"
                        placeholder="https://youtube.com/... or https://.../video.mp4"
                        value={knowledgeVideoInput}
                        onChange={(e) => setKnowledgeVideoInput(e.target.value)}
                      />
                      <button
                        type="button"
                        className="btn btn-outline btn-sm"
                        onClick={() => {
                          const candidate = knowledgeVideoInput.trim();
                          if (!candidate.startsWith("https://")) {
                            setError("Video links must start with https://");
                            return;
                          }
                          const existing = knowledgeForm.video_urls ?? [];
                          if (!existing.includes(candidate)) {
                            setKnowledgeForm({ ...knowledgeForm, video_urls: [...existing, candidate] });
                          }
                          setKnowledgeVideoInput("");
                        }}
                      >
                        Add Video
                      </button>
                    </div>
                    {(knowledgeForm.video_urls?.length ?? 0) > 0 && (
                      <div className="mt-1 flex flex-wrap gap-1.5">
                        {(knowledgeForm.video_urls ?? []).map((url, index) => (
                          <div key={`${url}-${index}`} className="badge badge-outline gap-1.5 py-3 text-xs">
                            <a href={url} target="_blank" rel="noreferrer" className="max-w-52 truncate link link-hover">{url}</a>
                            <button type="button" className="text-error font-bold" onClick={() => setKnowledgeForm({ ...knowledgeForm, video_urls: knowledgeForm.video_urls.filter((_, i) => i !== index) })}>✕</button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex flex-col gap-1.5">
                <span className="text-xs font-semibold text-base-content/80">Source Reference (Optional)</span>
                <input
                  className="input input-bordered input-sm w-full"
                  maxLength={1000}
                  placeholder="Optional document URL, manual section, or internal note"
                  value={knowledgeForm.source_reference ?? ""}
                  onChange={(e) => setKnowledgeForm({ ...knowledgeForm, source_reference: e.target.value })}
                />
              </div>

              <div className="modal-action flex-wrap justify-between gap-2 pt-2">
                <button type="button" className="btn btn-ghost" onClick={() => setShowKnowledgeForm(false)}>Cancel</button>
                <div className="flex flex-wrap gap-2">
                  <button type="submit" className="btn btn-outline" disabled={knowledgeMediaUploading}>Save Draft</button>
                  <button type="button" className="btn btn-primary" disabled={knowledgeMediaUploading} onClick={() => void saveKnowledgeArticle(true)}>Save &amp; Publish</button>
                </div>
              </div>
            </form>
          </div>
          <form method="dialog" className="modal-backdrop"><button onClick={() => setShowKnowledgeForm(false)}>close</button></form>
        </dialog>
      )}
    </>
  );
}

function Empty({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="p-12 text-center flex flex-col items-center justify-center">
      <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-base-200 text-base-content/45">
        <svg aria-hidden="true" focusable="false" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5">
          <path d="M3.5 6.5h6l2 2h9v9.25A1.75 1.75 0 0 1 20.75 19.5h-17A1.75 1.75 0 0 1 2 17.75V8.25A1.75 1.75 0 0 1 3.5 6.5Z" />
        </svg>
      </div>
      <h3 className="font-bold text-base text-base-content">{title}</h3>
      <p className="text-xs text-base-content/60 max-w-sm mt-1">{detail}</p>
    </div>
  );
}

function ContentComparison({ draft, published, defaultOpen = true }: { draft: Record<string, unknown>; published: Record<string, unknown> | null; defaultOpen?: boolean }) {
  const keys = [...new Set([...Object.keys(draft), ...Object.keys(published ?? {})])].sort();
  const changedCount = published ? keys.filter((key) => JSON.stringify(draft[key]) !== JSON.stringify(published[key])).length : 0;
  const formatValue = (value: unknown) => value === undefined ? "Not set" : typeof value === "string" ? value || "(empty)" : JSON.stringify(value, null, 2);
  return (
    <details open={defaultOpen} className="card panel">
      <summary className="panel-head cursor-pointer list-none">
        <div>
          <h2>Draft vs published</h2>
          <p>{published ? `${changedCount} changed field${changedCount === 1 ? "" : "s"} · compare what customers see before publishing` : "No published version yet · the app still uses its local defaults"}</p>
        </div>
        <span className={`badge ${changedCount ? "badge-warning" : "badge-success"}`}>{published ? changedCount ? "Changes pending" : "In sync" : "Not published"}</span>
      </summary>
      <div className="grid gap-3 p-4 xl:grid-cols-2">
        {keys.map((key) => {
          const changed = published !== null && JSON.stringify(draft[key]) !== JSON.stringify(published[key]);
          return (
            <section key={key} className={`rounded-box border p-3 ${changed ? "border-warning/50 bg-warning/5" : "border-base-300"}`}>
              <h3 className="mb-2 text-sm font-semibold">{humanize(key)}{changed && <span className="ml-2 badge badge-warning badge-xs">Changed</span>}</h3>
              <div className="grid gap-2 md:grid-cols-2">
                <div className="min-w-0">
                  <p className="mb-1 text-xs font-semibold text-base-content/60">Draft</p>
                  <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-base-200/60 p-2 text-xs">{formatValue(draft[key])}</pre>
                </div>
                <div className="min-w-0">
                  <p className="mb-1 text-xs font-semibold text-base-content/60">Published</p>
                  <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-base-200/60 p-2 text-xs">{formatValue(published?.[key])}</pre>
                </div>
              </div>
            </section>
          );
        })}
      </div>
    </details>
  );
}

function ImageUrlField({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  return <label className="form-control gap-2"><span className="label-text font-semibold">Image URL</span><input className="input input-bordered" type="url" value={value} onChange={(event) => onChange(event.target.value)} placeholder="https://…" /><input className="file-input file-input-bordered file-input-sm w-full" type="file" accept="image/png,image/jpeg,image/webp" aria-label="Upload image" disabled={uploading} onChange={async (event) => { const file = event.target.files?.[0]; const authUser = getFirebaseAuth()?.currentUser; if (!file || !authUser) return; setUploading(true); setError(""); try { const asset = await uploadMedia(authUser, file); onChange(asset.url); } catch (cause) { setError(cause instanceof Error ? cause.message : "Image upload failed."); } finally { setUploading(false); event.target.value = ""; } }} />{uploading && <span className="label-text-alt">Uploading image…</span>}{error && <span role="alert" className="text-xs text-error">{error}</span>}{value.startsWith("https://") && <div role="img" aria-label="Image preview" className="max-h-40 min-h-20 w-full rounded-lg border border-base-300 bg-contain bg-left bg-no-repeat" style={{ backgroundImage: `url("${value.replaceAll('"', '')}")` }} />}</label>;
}

function ContentField({ field, value, categories, products, onChange }: { field: string; value: unknown; categories: Category[]; products: Product[]; onChange: (value: unknown) => void }) {
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const homeSections = [
    ["categories", "Categories"],
    ["featured_products", "Featured products"],
    ["requests", "Requests"],
    ["announcements", "Announcements"],
  ] as const;
  if (field === "section_order") {
    const current = Array.isArray(value) ? value.filter((item): item is string => typeof item === "string" && homeSections.some(([key]) => key === item)) : [];
    const ordered = [...new Set([...current, ...homeSections.map(([key]) => key)])];
    const move = (index: number, delta: number) => {
      const target = index + delta;
      if (target < 0 || target >= ordered.length) return;
      const next = [...ordered];
      [next[index], next[target]] = [next[target], next[index]];
      onChange(next);
    };
    return <fieldset className="form-control min-w-0 gap-2 sm:col-span-2"><legend className="font-semibold">Home section order</legend><p className="text-xs text-base-content/60">Choose the order shown on the customer app Home screen.</p><ol className="grid gap-2">{ordered.map((key, index) => <li key={key} className="flex min-w-0 items-center gap-3 rounded-box border border-base-300 p-2"><span className="badge badge-neutral">{index + 1}</span><span className="min-w-0 flex-1">{homeSections.find(([section]) => section === key)?.[1] ?? key}</span><button type="button" className="btn btn-square btn-sm btn-ghost" aria-label={`Move ${key} up`} disabled={index === 0} onClick={() => move(index, -1)}>↑</button><button type="button" className="btn btn-square btn-sm btn-ghost" aria-label={`Move ${key} down`} disabled={index === ordered.length - 1} onClick={() => move(index, 1)}>↓</button></li>)}</ol></fieldset>;
  }
  if (field === "visible_sections") {
    const selected = new Set(Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : []);
    return <fieldset className="form-control min-w-0 gap-2 sm:col-span-2"><legend className="font-semibold">Visible Home sections</legend><p className="text-xs text-base-content/60">Choose which sections customers can see. Hidden sections keep their saved content.</p><div className="grid gap-2 sm:grid-cols-2">{homeSections.map(([key, label]) => <label key={key} className="label cursor-pointer justify-start gap-3 rounded-box border border-base-300 p-3"><input className="checkbox checkbox-primary" type="checkbox" checked={selected.has(key)} onChange={(event) => { const next = new Set(selected); if (event.target.checked) next.add(key); else next.delete(key); onChange(homeSections.map(([section]) => section).filter((section) => next.has(section))); }} /><span className="label-text">{label}</span></label>)}</div></fieldset>;
  }
  if (typeof value === "boolean") return <label className="label cursor-pointer justify-start gap-3 rounded-lg border border-base-300 p-3"><input className="toggle toggle-primary" type="checkbox" checked={value} onChange={(event) => onChange(event.target.checked)} /><span className="label-text">{humanize(field)}</span></label>;
  if (["featured_category_ids", "featured_product_ids", "featured_product_category_ids"].includes(field)) {
    const options = (field === "featured_product_ids" ? products : categories).filter((item) => item.is_published);
    const selected = new Set((Array.isArray(value) ? value : []).filter((item: unknown): item is string => typeof item === "string"));
    const label = field === "featured_category_ids" ? "Featured collections" : field === "featured_product_category_ids" ? "Featured product source collections" : "Featured products";
    return <fieldset className="form-control grid min-w-0 gap-2 sm:col-span-2"><legend className="font-semibold">{label}</legend><p className="text-xs text-base-content/60">Select up to 12. Leave empty to apply no filter.</p><div className="grid min-w-0 max-h-56 grid-cols-1 gap-1 overflow-y-auto overflow-x-hidden rounded-lg border border-base-300 p-2 sm:grid-cols-2">{options.length ? options.map((item) => <label key={item.id} className="label flex min-w-0 w-full cursor-pointer items-start justify-start gap-2 rounded-md px-2 py-1"><input className="checkbox checkbox-sm checkbox-primary mt-0.5 shrink-0" type="checkbox" checked={selected.has(item.id)} disabled={!selected.has(item.id) && selected.size >= 12} onChange={(event) => { const next = new Set(selected); if (event.target.checked) next.add(item.id); else next.delete(item.id); onChange([...next]); }} /><span className="label-text min-w-0 flex-1 whitespace-normal break-words leading-snug">{item.name}</span></label>) : <span className="p-2 text-xs text-base-content/60">Publish items in the catalogue first.</span>}</div>{selected.size >= 12 && <span className="label-text-alt">Maximum of 12 selected.</span>}</fieldset>;
  }
  if (Array.isArray(value)) {
    const inputId = `content-${field}`;
    return <div className="form-control flex min-w-0 flex-col items-stretch gap-1 sm:col-span-2"><label className="block text-sm font-semibold" htmlFor={inputId}>{humanize(field)} · one per line</label><textarea id={inputId} className="textarea textarea-bordered min-h-28 w-full" value={value.join("\n")} onChange={(event) => onChange(event.target.value.split("\n").map((item) => item.trim()).filter(Boolean))} /></div>;
  }
  const choices: Record<string, string[]> = { hero_cta_target: ["products", "solution_finder", "quote", "support"], integration: ["iframe", "hosted_widget"] };
  if (choices[field]) return <label className="form-control gap-1"><span className="label-text font-semibold">{humanize(field)}</span><select className="select select-bordered" value={String(value)} onChange={(event) => onChange(event.target.value)}>{choices[field].map((choice) => <option key={choice} value={choice}>{humanize(choice)}</option>)}</select></label>;
  if (field === "logo_url" || field === "support_icon_url") return <label className="form-control gap-2"><span className="label-text font-semibold">{humanize(field)}</span><input className="input input-bordered" type="url" value={textValue(value)} onChange={(event) => onChange(event.target.value)} /><input className="file-input file-input-bordered file-input-sm w-full" type="file" accept="image/png,image/jpeg,image/webp" aria-label={`Upload ${humanize(field)}`} disabled={uploading} onChange={async (event) => { const file = event.target.files?.[0]; const authUser = getFirebaseAuth()?.currentUser; if (!file || !authUser) return; setUploading(true); setUploadError(""); try { const asset = await uploadMedia(authUser, file); onChange(asset.url); } catch (cause) { setUploadError(cause instanceof Error ? cause.message : "Image upload failed."); } finally { setUploading(false); event.target.value = ""; } }} />{uploading && <span className="label-text-alt">Uploading to Supabase Storage…</span>}{uploadError && <span role="alert" className="text-xs text-error">{uploadError}</span>}</label>;
  const long = ["description", "body", "message", "address", "hours"].some((part) => field.includes(part));
  const inputType = field.includes("email") ? "email" : field.includes("phone") || field.includes("whatsapp") ? "tel" : field.includes("url") || field.includes("logo") || field.includes("handoff") ? "url" : "text";
  const inputId = `content-${field}`;
  return <div className={`min-w-0 ${long ? "sm:col-span-2" : ""}`}><label className="mb-1 block text-sm font-semibold" htmlFor={inputId}>{humanize(field)}</label>{long ? <textarea id={inputId} className="textarea textarea-bordered min-h-20 w-full" value={textValue(value)} onChange={(event) => onChange(event.target.value)} /> : <input id={inputId} className="input input-bordered w-full" type={inputType} value={textValue(value)} onChange={(event) => onChange(event.target.value)} />}</div>;
}
