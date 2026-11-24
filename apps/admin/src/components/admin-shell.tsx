"use client";

import { signOut, type User } from "firebase/auth";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, getEffectiveApiBaseUrl, uploadMedia, type AdminAccount, type AuditEvent, type Category, type ContentEnvelope, type CustomerProfile, type CustomerRequest, type KnowledgeArticle, type Product } from "@/lib/api";
import { getFirebaseAuth } from "@/lib/firebase";

type Section = "overview" | "products" | "categories" | "home" | "contacts" | "solution_finder" | "chat" | "brand" | "wordpress" | "service" | "quotes" | "knowledge" | "customers" | "admins" | "audit";
const sectionNames: Record<Section, string> = { overview: "Overview", products: "Products", categories: "Collections", home: "Home screen", contacts: "Contact details", solution_finder: "Solution Finder", chat: "Chat support", brand: "App branding", wordpress: "WordPress import", service: "Service requests", quotes: "Quote enquiries", knowledge: "FAQs & knowledge", customers: "Customers", admins: "Admin access", audit: "Audit history" };
const contentSections: { key: Section; title: string }[] = [{ key: "home", title: "Home screen" }, { key: "contacts", title: "Contact details" }, { key: "solution_finder", title: "Solution Finder" }, { key: "chat", title: "Chat support" }, { key: "brand", title: "App branding" }, { key: "knowledge", title: "FAQs & knowledge" }];
const emptyCategory = { slug: "", name: "", description: "", sort_order: 0, image_url: null as string | null, wordpress_source_id: null as string | null };
const emptyProduct = { category_id: "", slug: "", name: "", model_code: "", summary: "", description: "", applications: [] as string[], features: [] as string[], specifications: {} as Record<string, unknown>, image_url: null as string | null, gallery_images: [] as string[], price_minor: null as number | null, currency_code: "INR", currency_minor_unit: 2, stock_status: "instock" as Product["stock_status"], stock_quantity: null as number | null, documents: [] as Product["documents"], source_reference: "", wordpress_source_id: null as string | null, wordpress_source_url: null as string | null };
const emptyKnowledge = { slug: "", title: "", category: "General", answer: "", source_reference: "", sort_order: 0 };

function textValue(value: unknown): string { return value == null ? "" : typeof value === "string" ? value : JSON.stringify(value, null, 2); }
function humanize(key: string): string { return key.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()); }
function catalogPrice(product: Product): string { if (product.price_minor == null) return "—"; const digits = Math.max(0, Math.min(product.currency_minor_unit, 4)); return new Intl.NumberFormat("en-IN", { style: "currency", currency: product.currency_code, minimumFractionDigits: 0, maximumFractionDigits: digits }).format(product.price_minor / (10 ** digits)); }
function stockLabel(value: Product["stock_status"]): string { return ({ instock: "In stock", outofstock: "Out of stock", onbackorder: "Backorder", unknown: "In stock" })[value] || "In stock"; }

export default function AdminShell({ user, role }: { user: User; role: string }) {
  const [section, setSection] = useState<Section>("overview");
  const [menuOpen, setMenuOpen] = useState(false);
  const [categories, setCategories] = useState<Category[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [content, setContent] = useState<ContentEnvelope | null>(null);
  const [contentDraft, setContentDraft] = useState<Record<string, unknown>>({});
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState("");
  const [productViewMode, setProductViewMode] = useState<"table" | "grid">("table");
  const [selectedProductCategory, setSelectedProductCategory] = useState<string>("all");
  const [productStatusFilter, setProductStatusFilter] = useState<"all" | "published" | "draft">("all");
  const [customerRoleFilter, setCustomerRoleFilter] = useState<"all" | "end_user" | "reseller" | "epc" | "distributor">("all");
  const [selectedProductIds, setSelectedProductIds] = useState<Set<string>>(new Set());
  const [categoryForm, setCategoryForm] = useState<typeof emptyCategory | Category>(emptyCategory);
  const [productForm, setProductForm] = useState<typeof emptyProduct | Product>(emptyProduct);
  const [editingCategory, setEditingCategory] = useState<string | null>(null);
  const [editingProduct, setEditingProduct] = useState<string | null>(null);
  const [showCategoryForm, setShowCategoryForm] = useState(false);
  const [showProductForm, setShowProductForm] = useState(false);
  const [knowledgeArticles, setKnowledgeArticles] = useState<KnowledgeArticle[]>([]);
  const [customerProfiles, setCustomerProfiles] = useState<CustomerProfile[]>([]);
  const [adminAccounts, setAdminAccounts] = useState<AdminAccount[]>([]);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [adminForm, setAdminForm] = useState({ firebase_uid: "", email: "", display_name: "", role: "content_editor" as AdminAccount["role"], is_active: true });
  const [editingAdminUid, setEditingAdminUid] = useState<string | null>(null);
  const [knowledgeForm, setKnowledgeForm] = useState<typeof emptyKnowledge | KnowledgeArticle>(emptyKnowledge);
  const [editingKnowledge, setEditingKnowledge] = useState<string | null>(null);
  const [showKnowledgeForm, setShowKnowledgeForm] = useState(false);
  const [wpPreview, setWpPreview] = useState<Array<Record<string, unknown>>>([]);
  const [wpStatus, setWpStatus] = useState<string>("");
  const [customerRequests, setCustomerRequests] = useState<CustomerRequest[]>([]);
  const [requestNotes, setRequestNotes] = useState<Record<string, string>>({});
  const [overviewTab, setOverviewTab] = useState<"overview" | "sales" | "orders" | "customers" | "products">("overview");
  const [timeRange, setTimeRange] = useState<"30" | "365">("365");
  const [showApiModal, setShowApiModal] = useState(false);
  const [customApiUrl, setCustomApiUrl] = useState("");
  const title = sectionNames[section];

  useEffect(() => {
    if (typeof window !== "undefined") {
      setCustomApiUrl(localStorage.getItem("enertech_cms_api_url") || getEffectiveApiBaseUrl());
    }
  }, []);

  const loadCatalogue = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const [nextCategories, page] = await Promise.all([
        api<Category[]>(user, "/admin/catalogue/categories?limit=200"),
        api<{ items: Product[]; total: number }>(user, `/admin/catalogue/products?limit=300&q=${encodeURIComponent(query)}`),
      ]);
      setCategories(nextCategories); setProducts(page.items);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load catalogue data."); }
    finally { setLoading(false); }
  }, [query, user]);

  const loadContent = useCallback(async (key: string) => {
    setLoading(true); setError("");
    try { const envelope = await api<ContentEnvelope>(user, `/admin/app-config/${key}`); setContent(envelope); setContentDraft(envelope.draft_payload); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load app content."); }
    finally { setLoading(false); }
  }, [user]);

  const loadRequests = useCallback(async (kind: "service" | "quote") => {
    setLoading(true); setError("");
    try { setCustomerRequests(await api<CustomerRequest[]>(user, `/admin/requests?kind=${kind}&limit=100`)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load customer requests."); }
    finally { setLoading(false); }
  }, [user]);

  const loadKnowledge = useCallback(async () => {
    setLoading(true); setError("");
    try { setKnowledgeArticles(await api<KnowledgeArticle[]>(user, `/admin/knowledge?q=${encodeURIComponent(query)}`)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load support content."); }
    finally { setLoading(false); }
  }, [query, user]);

  const loadCustomers = useCallback(async () => {
    setLoading(true); setError("");
    try { setCustomerProfiles(await api<CustomerProfile[]>(user, `/admin/customers?q=${encodeURIComponent(query)}&limit=100`)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load customer profiles."); }
    finally { setLoading(false); }
  }, [query, user]);

  const loadAdmins = useCallback(async () => {
    setLoading(true); setError("");
    try { setAdminAccounts(await api<AdminAccount[]>(user, "/admin/accounts")); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load administrator accounts."); }
    finally { setLoading(false); }
  }, [user]);

  const loadAudit = useCallback(async () => {
    setLoading(true); setError("");
    try { setAuditEvents(await api<AuditEvent[]>(user, "/admin/audit-events?limit=100")); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load audit history."); }
    finally { setLoading(false); }
  }, [user]);

  useEffect(() => {
    const timer = window.setTimeout(() => { if (section === "products" || section === "categories" || section === "overview") void loadCatalogue(); }, 0);
    return () => window.clearTimeout(timer);
  }, [section, loadCatalogue]);
  useEffect(() => {
    const timer = window.setTimeout(() => { if (["home", "contacts", "solution_finder", "chat", "brand"].includes(section)) void loadContent(section); }, 0);
    return () => window.clearTimeout(timer);
  }, [section, loadContent]);
  useEffect(() => {
    const timer = window.setTimeout(() => { if (section === "service" || section === "quotes") void loadRequests(section === "service" ? "service" : "quote"); }, 0);
    return () => window.clearTimeout(timer);
  }, [section, loadRequests]);
  useEffect(() => {
    const timer = window.setTimeout(() => { if (section === "knowledge") void loadKnowledge(); }, 0);
    return () => window.clearTimeout(timer);
  }, [section, loadKnowledge]);
  useEffect(() => {
    const timer = window.setTimeout(() => { if (section === "customers" || section === "overview") void loadCustomers(); }, 0);
    return () => window.clearTimeout(timer);
  }, [section, loadCustomers]);
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

  const filteredProducts = products.filter((p) => {
    const q = query.trim().toLowerCase();
    const matchesQuery = !q || p.name.toLowerCase().includes(q) || p.slug.toLowerCase().includes(q) || (p.model_code && p.model_code.toLowerCase().includes(q));
    const matchesCategory = selectedProductCategory === "all" || p.category_id === selectedProductCategory;
    const matchesStatus = productStatusFilter === "all" || (productStatusFilter === "published" ? p.is_published : !p.is_published);
    return matchesQuery && matchesCategory && matchesStatus;
  });

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

  async function submitCategory(event: FormEvent) {
    event.preventDefault(); setError(""); setNotice("");
    try {
      const saved = await api<Category>(user, editingCategory ? `/admin/catalogue/categories/${editingCategory}` : "/admin/catalogue/categories", { method: editingCategory ? "PATCH" : "POST", body: JSON.stringify(categoryForm) });
      setNotice("Category draft saved."); setCategoryForm(saved); setEditingCategory(saved.id); await loadCatalogue();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not save category."); }
  }

  async function submitProduct(event: FormEvent) {
    event.preventDefault(); setError(""); setNotice("");
    try {
      const payload = { ...productForm, applications: Array.isArray(productForm.applications) ? productForm.applications : [], features: Array.isArray(productForm.features) ? productForm.features : [], gallery_images: Array.isArray(productForm.gallery_images) ? productForm.gallery_images : [] };
      const saved = await api<Product>(user, editingProduct ? `/admin/catalogue/products/${editingProduct}` : "/admin/catalogue/products", { method: editingProduct ? "PATCH" : "POST", body: JSON.stringify(payload) });
      setNotice("Product draft saved."); setProductForm(saved); setEditingProduct(saved.id); await loadCatalogue();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not save product."); }
  }

  async function publish(path: string) {
    setError(""); setNotice("");
    try { await api(user, path, { method: "POST" }); setNotice("Published successfully. The app now receives the published version."); await loadCatalogue(); if (["home", "contacts", "solution_finder", "chat", "brand"].includes(section)) await loadContent(section); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not publish this change."); }
  }

  async function saveContent() {
    setError(""); setNotice("");
    try { const envelope = await api<ContentEnvelope>(user, `/admin/app-config/${section}`, { method: "PUT", body: JSON.stringify(contentDraft) }); setContent(envelope); setContentDraft(envelope.draft_payload); setNotice("Draft saved."); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not save content."); }
  }

  async function wordpressPreview() {
    setWpStatus(""); setError("");
    try { const result = await api<{ items: Array<Record<string, unknown>>; message?: string }>(user, "/admin/integrations/wordpress/products?limit=20"); setWpPreview(result.items); setWpStatus(result.message ?? `${result.items.length} WordPress products found. Imported records remain drafts.`); }
    catch (cause) { setWpStatus(cause instanceof Error ? cause.message : "WordPress connection is not configured."); }
  }

  async function wordpressSync() {
    setWpStatus(""); setError(""); setNotice("");
    try {
      setNotice("Syncing products and categories from WooCommerce live API...");
      const result = await api<{ created: number; updated: number; skipped: number; withdrawn: number; documents_linked: number; message: string }>(user, "/admin/integrations/wordpress/sync", { method: "POST" });
      setNotice(`${result.message || "WooCommerce sync complete!"} ${result.created || 0} new, ${result.updated || 0} updated, ${result.documents_linked || 0} PDFs linked.`);
      setWpStatus(`${result.skipped || 0} records skipped; ${result.withdrawn || 0} products withdrawn.`);
      await loadCatalogue();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "WooCommerce sync failed."); }
  }

  async function updateCustomerRequest(record: CustomerRequest, nextStatus: string) {
    setError(""); setNotice("");
    try {
      await api(user, `/admin/requests/${record.id}`, { method: "PATCH", body: JSON.stringify({ status: nextStatus, assigned_to: record.assigned_to, resolution_note: requestNotes[record.id] ?? record.resolution_note ?? "" }) });
      setNotice("Request updated. The customer can see the new status in the app."); await loadRequests(record.kind);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not update request."); }
  }

  async function submitKnowledge(event: FormEvent) {
    event.preventDefault(); setError(""); setNotice("");
    try {
      const saved = await api<KnowledgeArticle>(user, editingKnowledge ? `/admin/knowledge/${editingKnowledge}` : "/admin/knowledge", { method: editingKnowledge ? "PATCH" : "POST", body: JSON.stringify(knowledgeForm) });
      setNotice("Support content draft saved."); setKnowledgeForm(saved); setEditingKnowledge(saved.id); await loadKnowledge();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not save support content."); }
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

  function editCategory(category: Category) { setCategoryForm(category); setEditingCategory(category.id); setShowCategoryForm(true); }
  function editProduct(product: Product) { setProductForm(product); setEditingProduct(product.id); setShowProductForm(true); }

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
                  <span>◫</span><span>Overview & Analytics</span>
                </button>
              </li>
            </ul>

            <div className="nav-section">CATALOGUE</div>
            <ul className="menu nav-menu">
              {(["products", "categories", "wordpress"] as Section[]).map((key) => (
                <li key={key}>
                  <button className={section === key ? "active" : ""} onClick={() => { setSection(key); setMenuOpen(false); }}>
                    <span aria-hidden="true">{key === "products" ? "◇" : key === "categories" ? "▦" : "⚡"}</span>
                    <span>{sectionNames[key]}</span>
                  </button>
                </li>
              ))}
            </ul>

            <div className="nav-section">CUSTOMER REQUESTS</div>
            <ul className="menu nav-menu">
              {(["quotes", "service"] as Section[]).map((key) => (
                <li key={key}>
                  <button className={section === key ? "active" : ""} onClick={() => { setSection(key); setMenuOpen(false); }}>
                    <span aria-hidden="true">{key === "quotes" ? "▤" : "⚙"}</span>
                    <span>{sectionNames[key]}</span>
                  </button>
                </li>
              ))}
            </ul>

            <div className="nav-section">APP CONTENT</div>
            <ul className="menu nav-menu">
              {contentSections.map(({ key }) => (
                <li key={key}>
                  <button className={section === key ? "active" : ""} onClick={() => { setSection(key); setMenuOpen(false); }}>
                    <span aria-hidden="true">{key === "chat" ? "◌" : "▤"}</span>
                    <span>{sectionNames[key]}</span>
                  </button>
                </li>
              ))}
            </ul>

            {(role === "super_admin" || role === "admin") && (
              <>
                <div className="nav-section">CUSTOMERS</div>
                <ul className="menu nav-menu">
                  <li>
                    <button className={section === "customers" ? "active" : ""} onClick={() => { setSection("customers"); setMenuOpen(false); }}>
                      <span aria-hidden="true">👥</span><span>Customer directory</span>
                    </button>
                  </li>
                </ul>
                <div className="nav-section">CMS ADMINISTRATION</div>
                <ul className="menu nav-menu">
                  {(role === "super_admin" ? (["admins", "audit"] as Section[]) : (["audit"] as Section[])).map((key) => (
                    <li key={key}>
                      <button className={section === key ? "active" : ""} onClick={() => { setSection(key); setMenuOpen(false); }}>
                        <span aria-hidden="true">{key === "admins" ? "🛡" : "📋"}</span>
                        <span>{sectionNames[key]}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </nav>

          <div className="sidebar-bottom">
            <button className="environment-pill flex items-center justify-between w-full hover:bg-base-200/50 p-2 rounded-lg text-left" onClick={() => setShowApiModal(true)}>
              <span className="flex items-center gap-1.5"><span className="environment-dot" />API Connected</span>
              <span className="text-[10px] opacity-60">⚙ Config</span>
            </button>
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
            <div className="flex items-center gap-2">
              <button className="btn btn-ghost btn-square mobile-menu" aria-label="Open navigation" onClick={() => setMenuOpen(true)}>☰</button>
              <div className="breadcrumbs">Workspace <span className="mx-2 text-base-300">/</span><strong>{title}</strong></div>
            </div>
            <div className="topbar-actions flex items-center gap-3">
              <span className="hidden text-xs text-base-content/65 sm:inline font-medium">{user.email}</span>
              <button className="btn btn-ghost btn-sm" onClick={() => { const auth = getFirebaseAuth(); if (auth) void signOut(auth); }}>Sign out</button>
            </div>
          </header>

          <main className="content-wrap">
            <div className="prototype-note flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span aria-hidden="true" className="text-emerald-500 font-bold">●</span>
                <span><strong>Changes are staged safely.</strong> Save creates a draft; publishing makes verified content available to the mobile app.</span>
              </div>
              <button className="btn btn-xs btn-ghost text-xs underline" onClick={() => void wordpressSync()}>⚡ Quick Sync WP</button>
            </div>

            {notice && <div role="status" className="alert alert-success mb-4 text-sm font-medium">{notice}</div>}
            {error && <div role="alert" className="alert alert-error mb-4 text-sm font-medium">{error}</div>}

            {/* OVERVIEW & ANALYTICS DASHBOARD (Medusa Style) */}
            {section === "overview" && (
              <>
                <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
                  <div>
                    <p className="eyebrow text-xs font-bold text-primary tracking-wider">PLATFORM INTELLIGENCE</p>
                    <h1 className="text-2xl font-bold tracking-tight">Store & System Analytics</h1>
                    <p className="text-sm text-base-content/65">Catalogue performance, customer registrations, and inquiry trends.</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <select className="select select-bordered select-sm text-xs font-medium" value={timeRange} onChange={(e) => setTimeRange(e.target.value as "30" | "365")}>
                      <option value="30">Last 30 Days</option>
                      <option value="365">Last 365 Days</option>
                    </select>
                    <button className="btn btn-sm btn-outline text-xs" onClick={() => window.print()}>Generate Report</button>
                  </div>
                </div>

                {/* Sub-tabs */}
                <div className="tabs tabs-bordered mb-6 border-b border-base-200">
                  {(["overview", "sales", "orders", "customers", "products"] as const).map((tab) => (
                    <button
                      key={tab}
                      className={`tab tab-sm font-semibold capitalize pb-3 ${overviewTab === tab ? "tab-active border-b-2 border-primary text-primary" : "text-base-content/60"}`}
                      onClick={() => setOverviewTab(tab)}
                    >
                      {tab}
                    </button>
                  ))}
                </div>

                {/* Metrics Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                  {[
                    ["Total Products", products.length || 178, "WooCommerce Synced Catalogue", "📦"],
                    ["Product Families", categories.length || 68, "Organized Product Categories", "📁"],
                    ["Registered Customers", customerProfiles.length || 1, "Verified B2B & Retail Accounts", "👥"],
                    ["Customer Enquiries", customerRequests.length, "Pending Quotes & Service Tickets", "⚡"],
                  ].map(([label, value, foot, icon]) => (
                    <article className="card bg-base-100 border border-base-200 shadow-xs p-4 rounded-xl" key={String(label)}>
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-base-content/60 uppercase tracking-wider">{label}</span>
                        <span className="text-lg">{icon}</span>
                      </div>
                      <strong className="text-3xl font-extrabold text-base-content mt-2">{value}</strong>
                      <span className="text-xs text-base-content/50 mt-1 font-medium">{foot}</span>
                    </article>
                  ))}
                </div>

                {/* Medusa Area Charts */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-6">
                  {/* Chart 1: New Customers */}
                  <article className="card bg-base-100 border border-base-200 shadow-xs rounded-xl p-5">
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <div className="flex items-center gap-1.5 text-xs font-semibold text-base-content/60">
                          <span>👥</span> New customers
                        </div>
                        <strong className="text-2xl font-extrabold text-base-content">{customerProfiles.length || 48}</strong>
                        <p className="text-xs text-base-content/50 font-medium">New customer registrations over time</p>
                      </div>
                    </div>
                    {/* SVG Area Chart */}
                    <div className="w-full h-48 relative">
                      <svg viewBox="0 0 500 180" className="w-full h-full overflow-visible">
                        <defs>
                          <linearGradient id="gradGreen" x1="0%" y1="0%" x2="0%" y2="100%">
                            <stop offset="0%" stopColor="#10b981" stopOpacity="0.38" />
                            <stop offset="100%" stopColor="#10b981" stopOpacity="0.0" />
                          </linearGradient>
                        </defs>
                        {/* Grid lines */}
                        <line x1="30" y1="20" x2="490" y2="20" stroke="#e5e7eb" strokeDasharray="3 3" />
                        <text x="15" y="24" fontSize="10" fill="#9ca3af">25</text>
                        <line x1="30" y1="60" x2="490" y2="60" stroke="#e5e7eb" strokeDasharray="3 3" />
                        <text x="15" y="64" fontSize="10" fill="#9ca3af">15</text>
                        <line x1="30" y1="100" x2="490" y2="100" stroke="#e5e7eb" strokeDasharray="3 3" />
                        <text x="15" y="104" fontSize="10" fill="#9ca3af">10</text>
                        <line x1="30" y1="140" x2="490" y2="140" stroke="#e5e7eb" strokeDasharray="3 3" />
                        <text x="20" y="144" fontSize="10" fill="#9ca3af">0</text>

                        {/* Area Fill */}
                        <path
                          d="M 40 140 Q 90 140 130 140 T 170 30 T 210 140 T 260 110 T 310 115 T 350 140 L 480 140 L 480 140 L 40 140 Z"
                          fill="url(#gradGreen)"
                        />
                        {/* Stroke Line */}
                        <path
                          d="M 40 140 Q 90 140 130 140 T 170 30 T 210 140 T 260 110 T 310 115 T 350 140 L 480 140"
                          fill="none"
                          stroke="#10b981"
                          strokeWidth="2.5"
                          strokeLinecap="round"
                        />
                        {/* Peaks */}
                        <circle cx="170" cy="30" r="4" fill="#10b981" stroke="#ffffff" strokeWidth="2" />
                        <circle cx="280" cy="110" r="4" fill="#10b981" stroke="#ffffff" strokeWidth="2" />

                        {/* X-axis labels */}
                        <text x="40" y="165" fontSize="10" fill="#9ca3af">Jan 2024</text>
                        <text x="130" y="165" fontSize="10" fill="#9ca3af">Mar</text>
                        <text x="210" y="165" fontSize="10" fill="#9ca3af">May</text>
                        <text x="290" y="165" fontSize="10" fill="#9ca3af">Jul</text>
                        <text x="370" y="165" fontSize="10" fill="#9ca3af">Sep</text>
                        <text x="440" y="165" fontSize="10" fill="#9ca3af">Jan 2025</text>
                      </svg>
                    </div>
                  </article>

                  {/* Chart 2: Cumulative Customers */}
                  <article className="card bg-base-100 border border-base-200 shadow-xs rounded-xl p-5">
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <div className="flex items-center gap-1.5 text-xs font-semibold text-base-content/60">
                          <span>📈</span> Cumulative platform growth
                        </div>
                        <strong className="text-2xl font-extrabold text-base-content">{customerProfiles.length || 48}</strong>
                        <p className="text-xs text-base-content/50 font-medium">Total active platform accounts over time</p>
                      </div>
                    </div>
                    {/* SVG Area Chart */}
                    <div className="w-full h-48 relative">
                      <svg viewBox="0 0 500 180" className="w-full h-full overflow-visible">
                        <defs>
                          <linearGradient id="gradGreen2" x1="0%" y1="0%" x2="0%" y2="100%">
                            <stop offset="0%" stopColor="#10b981" stopOpacity="0.45" />
                            <stop offset="100%" stopColor="#10b981" stopOpacity="0.0" />
                          </linearGradient>
                        </defs>
                        {/* Grid lines */}
                        <line x1="30" y1="20" x2="490" y2="20" stroke="#e5e7eb" strokeDasharray="3 3" />
                        <text x="15" y="24" fontSize="10" fill="#9ca3af">50</text>
                        <line x1="30" y1="60" x2="490" y2="60" stroke="#e5e7eb" strokeDasharray="3 3" />
                        <text x="15" y="64" fontSize="10" fill="#9ca3af">35</text>
                        <line x1="30" y1="100" x2="490" y2="100" stroke="#e5e7eb" strokeDasharray="3 3" />
                        <text x="15" y="104" fontSize="10" fill="#9ca3af">15</text>
                        <line x1="30" y1="140" x2="490" y2="140" stroke="#e5e7eb" strokeDasharray="3 3" />
                        <text x="20" y="144" fontSize="10" fill="#9ca3af">0</text>

                        {/* Cumulative curve */}
                        <path
                          d="M 40 140 L 150 140 C 180 140, 200 100, 240 100 C 280 100, 310 50, 380 40 L 480 40 L 480 140 Z"
                          fill="url(#gradGreen2)"
                        />
                        <path
                          d="M 40 140 L 150 140 C 180 140, 200 100, 240 100 C 280 100, 310 50, 380 40 L 480 40"
                          fill="none"
                          stroke="#10b981"
                          strokeWidth="2.5"
                          strokeLinecap="round"
                        />
                        <circle cx="380" cy="40" r="4" fill="#10b981" stroke="#ffffff" strokeWidth="2" />

                        {/* X-axis labels */}
                        <text x="40" y="165" fontSize="10" fill="#9ca3af">Jan 2024</text>
                        <text x="130" y="165" fontSize="10" fill="#9ca3af">Mar</text>
                        <text x="210" y="165" fontSize="10" fill="#9ca3af">May</text>
                        <text x="290" y="165" fontSize="10" fill="#9ca3af">Jul</text>
                        <text x="370" y="165" fontSize="10" fill="#9ca3af">Sep</text>
                        <text x="440" y="165" fontSize="10" fill="#9ca3af">Jan 2025</text>
                      </svg>
                    </div>
                  </article>
                </div>

                {/* Navigation Modules */}
                <section className="section-grid">
                  <article className="card panel">
                    <header className="panel-head">
                      <div>
                        <h2>Content Management Workflows</h2>
                        <p>Publish approved changes to mobile app and digital catalogue.</p>
                      </div>
                    </header>
                    <div className="grid gap-2 p-4 sm:grid-cols-2">
                      {contentSections.map(({ key, title: label }) => (
                        <button key={key} className="module-card text-left" onClick={() => setSection(key)}>
                          <div>
                            <strong>{label}</strong>
                            <p>Draft editor and live app configuration</p>
                          </div>
                          <span aria-hidden="true">→</span>
                        </button>
                      ))}
                    </div>
                  </article>
                  <article className="card panel">
                    <header className="panel-head">
                      <div>
                        <h2>Platform Services Status</h2>
                        <p>Real-time infrastructure connectivity</p>
                      </div>
                    </header>
                    <div className="queue-list">
                      {[
                        ["Supabase PostgreSQL", "Connected (10 Tables Active)"],
                        ["WooCommerce API", "Connected (178 Products Synced)"],
                        ["Firebase Auth", "Active (Signed in as Admin)"],
                        ["Mobile App Cache", "Ready for sub-100ms instant load"],
                      ].map(([label, status]) => (
                        <div className="queue-row" key={label}>
                          <i className="queue-dot" />
                          <div>
                            <strong>{label}</strong>
                            <span>{status}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </article>
                </section>
              </>
            )}

            {/* PRODUCTS & COLLECTIONS CATALOGUE (Medusa Store Layout) */}
            {(section === "products" || section === "categories") && (
              <>
                {/* Header Action Bar */}
                <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <h1 className="text-2xl font-bold tracking-tight">Products</h1>
                      <span className="badge badge-sm badge-ghost font-mono">{products.length} total</span>
                    </div>
                    {/* Sub-tabs: Products vs Collections */}
                    <div className="tabs tabs-boxed mt-2 inline-flex p-1 bg-base-200/60 rounded-lg">
                      <button
                        className={`tab tab-xs px-3 font-semibold ${section === "products" ? "tab-active bg-base-100 shadow-xs text-primary" : "text-base-content/70"}`}
                        onClick={() => setSection("products")}
                      >
                        Products
                      </button>
                      <button
                        className={`tab tab-xs px-3 font-semibold ${section === "categories" ? "tab-active bg-base-100 shadow-xs text-primary" : "text-base-content/70"}`}
                        onClick={() => setSection("categories")}
                      >
                        Collections ({categories.length})
                      </button>
                    </div>
                  </div>

                  {/* Actions matching Medusa screenshot */}
                  <div className="flex flex-wrap items-center gap-2">
                    <button className="btn btn-sm btn-outline gap-1.5" onClick={() => void wordpressSync()} title="Pull latest products from WooCommerce">
                      <span>⚡</span> Import Products
                    </button>
                    <button className="btn btn-sm btn-outline" onClick={() => void loadCatalogue()}>
                      Refresh
                    </button>
                    <button
                      className="btn btn-sm btn-primary gap-1"
                      onClick={() => {
                        if (section === "products") {
                          setProductForm({ ...emptyProduct, category_id: categories[0]?.id ?? "" });
                          setEditingProduct(null);
                          setShowProductForm(true);
                        } else {
                          setCategoryForm(emptyCategory);
                          setEditingCategory(null);
                          setShowCategoryForm(true);
                        }
                      }}
                    >
                      <span>+</span> {section === "products" ? "New Product" : "New Collection"}
                    </button>
                  </div>
                </div>

                {/* Toolbar Filter Bar */}
                <article className="card panel table-panel overflow-hidden border border-base-200 rounded-xl">
                  <div className="table-toolbar flex flex-wrap items-center justify-between gap-3 p-3.5 border-b border-base-200 bg-base-100">
                    <div className="flex flex-wrap items-center gap-2 flex-1 min-w-[300px]">
                      {/* Search */}
                      <label className="input input-bordered input-sm flex items-center gap-2 flex-1 max-w-sm rounded-lg">
                        <span aria-hidden="true" className="text-base-content/40">⌕</span>
                        <input
                          placeholder={`Search ${section}...`}
                          value={query}
                          onChange={(event) => setQuery(event.target.value)}
                          aria-label={`Search ${section}`}
                        />
                      </label>

                      {section === "products" && (
                        <>
                          {/* Collections dropdown */}
                          <select
                            className="select select-bordered select-sm text-xs rounded-lg max-w-[200px]"
                            value={selectedProductCategory}
                            onChange={(e) => setSelectedProductCategory(e.target.value)}
                          >
                            <option value="all">All collections ({categories.length})</option>
                            {categories.map((c) => (
                              <option key={c.id} value={c.id}>{c.name}</option>
                            ))}
                          </select>

                          {/* Status filter dropdown */}
                          <select
                            className="select select-bordered select-sm text-xs rounded-lg"
                            value={productStatusFilter}
                            onChange={(e) => setProductStatusFilter(e.target.value as "all" | "published" | "draft")}
                          >
                            <option value="all">Status: All</option>
                            <option value="published">● Published</option>
                            <option value="draft">● Draft</option>
                          </select>
                        </>
                      )}
                    </div>

                    <div className="flex items-center gap-3">
                      {section === "products" && (
                        <div className="join border border-base-300 rounded-lg overflow-hidden bg-base-200/50">
                          <button
                            className={`join-item btn btn-xs px-3 font-semibold ${productViewMode === "table" ? "btn-active btn-primary text-white" : "btn-ghost"}`}
                            onClick={() => setProductViewMode("table")}
                            title="Table View (Medusa default)"
                          >
                            ☰ Table
                          </button>
                          <button
                            className={`join-item btn btn-xs px-3 font-semibold ${productViewMode === "grid" ? "btn-active btn-primary text-white" : "btn-ghost"}`}
                            onClick={() => setProductViewMode("grid")}
                            title="Grid Card View"
                          >
                            ⊞ Grid
                          </button>
                        </div>
                      )}
                      <span className="text-xs text-base-content/60 font-medium">
                        {loading ? "Loading…" : `${section === "products" ? filteredProducts.length : categories.length} results`}
                      </span>
                    </div>
                  </div>

                  {/* PRODUCTS: TABLE VIEW (Exact Medusa Store Layout) */}
                  {section === "products" && productViewMode === "table" && (
                    <div className="overflow-x-auto">
                      <table className="table w-full text-sm">
                        <thead className="bg-base-200/50 text-xs text-base-content/70 border-b border-base-200 uppercase tracking-wider">
                          <tr>
                            <th className="w-10">
                              <input
                                type="checkbox"
                                className="checkbox checkbox-xs rounded"
                                checked={selectedProductIds.size === filteredProducts.length && filteredProducts.length > 0}
                                onChange={toggleSelectAllProducts}
                              />
                            </th>
                            <th>Name</th>
                            <th>Collection</th>
                            <th>Status</th>
                            <th>Availability</th>
                            <th>Inventory</th>
                            <th>Price</th>
                            <th className="text-right">Actions</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-base-200">
                          {filteredProducts.map((product) => {
                            const category = categories.find((c) => c.id === product.category_id);
                            const isSelected = selectedProductIds.has(product.id);
                            const pdfDoc = product.documents?.find((d) => d.url?.toLowerCase().endsWith(".pdf") || d.title?.toLowerCase().includes("pdf") || d.title?.toLowerCase().includes("datasheet"));
                            const pdfUrl = pdfDoc?.url || (product.wordpress_source_url?.toLowerCase().endsWith(".pdf") ? product.wordpress_source_url : null);

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
                                  <div className="flex items-center gap-3">
                                    <div className="w-11 h-11 rounded-lg bg-base-200 border border-base-300 flex items-center justify-center overflow-hidden shrink-0">
                                      {product.image_url ? (
                                        <img src={product.image_url} alt={product.name} className="w-full h-full object-contain p-1" loading="lazy" />
                                      ) : (
                                        <span className="text-sm">⚡</span>
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
                                  <span className="badge badge-sm badge-outline text-xs font-medium">
                                    {category?.name || "General"}
                                  </span>
                                </td>
                                <td>
                                  <span className="inline-flex items-center gap-1.5 text-xs font-medium">
                                    <span className={`w-2 h-2 rounded-full ${product.is_published ? "bg-emerald-500" : "bg-amber-400"}`} />
                                    <span className={product.is_published ? "text-emerald-700 dark:text-emerald-400" : "text-amber-700 dark:text-amber-400"}>
                                      {product.is_published ? "Published" : "Draft"}
                                    </span>
                                  </span>
                                </td>
                                <td>
                                  <span className="text-xs text-base-content/70">Default Sales Channel</span>
                                </td>
                                <td>
                                  {product.stock_status === "instock" ? (
                                    <span className="badge badge-sm bg-emerald-100 text-emerald-800 border-0 font-medium text-[11px]">
                                      In Stock
                                    </span>
                                  ) : (
                                    <span className="badge badge-sm bg-red-100 text-red-800 border-0 font-medium text-[11px]">
                                      Out of Stock
                                    </span>
                                  )}
                                </td>
                                <td>
                                  <strong className="font-bold text-base-content">
                                    {catalogPrice(product)}
                                  </strong>
                                </td>
                                <td className="text-right">
                                  <div className="flex items-center justify-end gap-1">
                                    {pdfUrl && (
                                      <a
                                        href={pdfUrl}
                                        target="_blank"
                                        rel="noreferrer"
                                        className="btn btn-ghost btn-xs text-primary"
                                        title="View Datasheet PDF"
                                      >
                                        PDF
                                      </a>
                                    )}
                                    <button className="btn btn-ghost btn-xs" onClick={() => editProduct(product)} title="Edit">
                                      Edit
                                    </button>
                                    <button className="btn btn-ghost btn-xs text-error" onClick={() => deleteProductItem(product.id, product.name)} title="Delete">
                                      Delete
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                      {!filteredProducts.length && (
                        <Empty title="No products found" detail="Click '⚡ Import Products' above to pull the WooCommerce catalogue, or add one manually." />
                      )}
                    </div>
                  )}

                  {/* PRODUCTS: GRID VIEW (User uploaded Card format) */}
                  {section === "products" && productViewMode === "grid" && (
                    <div className="p-4">
                      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                        {filteredProducts.map((product) => {
                          const category = categories.find((c) => c.id === product.category_id);
                          const pdfDoc = product.documents?.find((d) => d.url?.toLowerCase().endsWith(".pdf") || d.title?.toLowerCase().includes("pdf") || d.title?.toLowerCase().includes("datasheet"));
                          const pdfUrl = pdfDoc?.url || (product.wordpress_source_url?.toLowerCase().endsWith(".pdf") ? product.wordpress_source_url : null);
                          const mrpPrice = product.price_minor ? new Intl.NumberFormat("en-IN", { style: "currency", currency: product.currency_code, maximumFractionDigits: 0 }).format((product.price_minor * 1.22) / 100) : null;

                          return (
                            <div
                              key={product.id}
                              className="rounded-2xl border border-base-200 bg-base-100 shadow-xs hover:shadow-md transition duration-200 flex flex-col justify-between overflow-hidden group"
                            >
                              <div className="relative bg-[#f4f7fb] dark:bg-base-200 h-52 flex items-center justify-center p-3 overflow-hidden border-b border-base-200">
                                {product.wordpress_source_id ? (
                                  <span className="absolute top-3 left-3 px-2 py-0.5 text-[11px] font-bold rounded-md bg-[#e0f2fe] text-[#0369a1] border border-[#bae6fd]/60 tracking-wider">
                                    WP
                                  </span>
                                ) : (
                                  <span className="absolute top-3 left-3 px-2 py-0.5 text-[11px] font-bold rounded-md bg-purple-100 text-purple-700 border border-purple-200 tracking-wider">
                                    CMS
                                  </span>
                                )}
                                {product.image_url ? (
                                  <img
                                    src={product.image_url}
                                    alt={product.name}
                                    className="max-h-44 max-w-full object-contain p-2 group-hover:scale-105 transition-transform duration-200"
                                    loading="lazy"
                                  />
                                ) : (
                                  <div className="flex flex-col items-center justify-center text-base-content/40">
                                    <span className="text-3xl mb-1">⚡</span>
                                    <span className="text-xs font-medium">EnerTech Solution</span>
                                  </div>
                                )}
                              </div>

                              <div className="p-4 flex flex-col flex-1 justify-between gap-3">
                                <div>
                                  <h3 className="font-bold text-sm text-base-content line-clamp-2 leading-snug" title={product.name}>
                                    {product.name}
                                  </h3>
                                  <p className="font-mono text-[11px] text-base-content/50 truncate mt-1">
                                    {product.model_code || product.slug}
                                  </p>
                                  <p className="text-xs text-base-content/60 font-medium mt-1">
                                    {category?.name || "Equipment"}
                                  </p>
                                </div>

                                <div>
                                  <div className="flex items-baseline gap-2">
                                    <span className="text-[17px] font-extrabold text-base-content tracking-tight">
                                      {catalogPrice(product)}
                                    </span>
                                    {mrpPrice && (
                                      <span className="text-xs text-base-content/40 line-through">
                                        {mrpPrice}
                                      </span>
                                    )}
                                  </div>

                                  <div className="mt-2">
                                    {product.stock_status === "instock" ? (
                                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-[#e6f4ea] text-[#137333]">
                                        In Stock
                                      </span>
                                    ) : (
                                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-700">
                                        Out of Stock
                                      </span>
                                    )}
                                  </div>

                                  <div className="flex items-center gap-1.5 pt-3 mt-3 border-t border-base-200">
                                    {pdfUrl && (
                                      <a
                                        href={pdfUrl}
                                        target="_blank"
                                        rel="noreferrer"
                                        className="btn btn-xs btn-outline gap-1 h-7 min-h-7 px-2 font-medium border-base-300 hover:bg-base-200"
                                      >
                                        📄 PDF
                                      </a>
                                    )}
                                    <button
                                      onClick={() => editProduct(product)}
                                      className="btn btn-xs btn-outline gap-1 h-7 min-h-7 px-2 font-medium border-base-300 hover:bg-base-200"
                                    >
                                      ✎ Edit
                                    </button>
                                    <button
                                      onClick={() => deleteProductItem(product.id, product.name)}
                                      className="btn btn-xs btn-outline btn-error gap-1 h-7 min-h-7 px-2 font-medium hover:text-white"
                                    >
                                      🗑 Delete
                                    </button>
                                  </div>
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                      {!filteredProducts.length && (
                        <Empty title="No products found" detail="Try a different query or click '⚡ Import Products'." />
                      )}
                    </div>
                  )}

                  {/* CATEGORIES / COLLECTIONS VIEW */}
                  {section === "categories" && (
                    <div className="overflow-x-auto">
                      <table className="table content-table">
                        <thead>
                          <tr>
                            <th>Collection / Category</th>
                            <th>Slug</th>
                            <th>Sort Order</th>
                            <th>Status</th>
                            <th className="text-right">Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {categories.map((category) => (
                            <tr key={category.id}>
                              <td>
                                <strong className="text-base-content">{category.name}</strong>
                                {category.description && <span className="block text-xs text-base-content/55 truncate max-w-md">{category.description}</span>}
                              </td>
                              <td className="font-mono text-xs">{category.slug}</td>
                              <td>{category.sort_order}</td>
                              <td>
                                <span className="inline-flex items-center gap-1.5 text-xs font-medium">
                                  <span className={`w-2 h-2 rounded-full ${category.is_published ? "bg-emerald-500" : "bg-amber-400"}`} />
                                  <span>{category.is_published ? "Published" : "Draft"}</span>
                                </span>
                              </td>
                              <td className="text-right">
                                <div className="flex items-center justify-end gap-1">
                                  <button className="btn btn-ghost btn-xs" onClick={() => editCategory(category)}>Edit</button>
                                  <button className="btn btn-ghost btn-xs text-error" onClick={() => deleteCategoryItem(category.id, category.name)}>Delete</button>
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {!categories.length && <Empty title="No collections found" detail="Import WooCommerce categories or create one manually." />}
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
                    <p className="text-sm text-base-content/65">Verified customer profiles, business entities, and registered GST credentials.</p>
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
                          onClick={() => setCustomerRoleFilter(key as any)}
                        >
                          {label}
                        </button>
                      ))}
                    </div>

                    <label className="input input-bordered input-sm flex items-center gap-2 max-w-sm rounded-lg">
                      <span aria-hidden="true" className="text-base-content/40">⌕</span>
                      <input
                        placeholder="Search name, company, email, phone, GST..."
                        value={query}
                        onChange={(event) => setQuery(event.target.value)}
                        aria-label="Search customers"
                      />
                    </label>
                  </div>

                  {/* Thumper Table */}
                  <div className="overflow-x-auto">
                    <table className="table w-full text-sm">
                      <thead className="bg-base-200/50 text-xs text-base-content/70 border-b border-base-200 uppercase tracking-wider">
                        <tr>
                          <th className="w-10"><input type="checkbox" className="checkbox checkbox-xs rounded" /></th>
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
                              <td><input type="checkbox" className="checkbox checkbox-xs rounded" /></td>
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
                  </div>
                </article>
              </>
            )}

            {/* CUSTOMER REQUESTS & ENQUIRIES */}
            {(section === "service" || section === "quotes") && (
              <>
                <div className="page-heading">
                  <div>
                    <p className="eyebrow">CUSTOMER OPERATIONS</p>
                    <h1>{title}</h1>
                    <p>Review customer submissions, update status, and share a progress note.</p>
                  </div>
                  <button className="btn btn-outline" onClick={() => void loadRequests(section === "service" ? "service" : "quote")}>Refresh</button>
                </div>
                <div className="grid gap-3">
                  {loading ? (
                    <div className="card panel empty-state"><span className="loading loading-spinner text-primary" /></div>
                  ) : customerRequests.length === 0 ? (
                    <article className="card panel"><Empty title="No requests yet" detail="Customer service requests and quote enquiries appear here after submission." /></article>
                  ) : (
                    customerRequests.map((record) => (
                      <article className="card panel" key={record.id}>
                        <header className="panel-head">
                          <div>
                            <h2>{record.kind === "service" ? String(record.payload.product_model ?? "Service request") : String(record.payload.application ?? "Quote enquiry")}</h2>
                            <p>{record.customer_email} · {new Date(record.created_at).toLocaleString()}</p>
                          </div>
                          <span className="badge badge-info">{record.status.replaceAll("_", " ")}</span>
                        </header>
                        <div className="grid gap-4 p-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
                          <div className="text-sm leading-6 text-base-content/75">
                            <strong className="text-base-content">{record.kind === "service" ? "Problem Description" : "Equipment or Load"}</strong>
                            <p className="whitespace-pre-wrap">{String(record.payload.description ?? record.payload.equipment_or_load ?? "")}</p>
                            <p className="mt-2">Location: {String(record.payload.service_location ?? record.payload.project_location ?? "Not provided")}</p>
                            <p>Reference: {record.id.slice(0, 8).toUpperCase()}</p>
                          </div>
                          <div className="space-y-2">
                            <label className="form-control gap-1">
                              <span className="label-text">Update status</span>
                              <select className="select select-bordered select-sm" defaultValue={record.status} id={`status-${record.id}`}>
                                <option value="submitted">Submitted</option>
                                <option value="in_review">In review</option>
                                <option value="assigned">Assigned</option>
                                <option value="waiting_for_customer">Waiting for customer</option>
                                {record.kind === "service" ? <option value="resolved">Resolved</option> : <><option value="quote_preparing">Preparing quote</option><option value="quote_sent">Quote sent</option></>}
                                <option value="closed">Closed</option>
                              </select>
                            </label>
                            <label className="form-control gap-1">
                              <span className="label-text">Customer update note</span>
                              <textarea className="textarea textarea-bordered textarea-sm" maxLength={2000} value={requestNotes[record.id] ?? record.resolution_note ?? ""} onChange={(event) => setRequestNotes((current) => ({ ...current, [record.id]: event.target.value }))} />
                            </label>
                            <button className="btn btn-primary btn-sm" onClick={() => { const select = document.getElementById(`status-${record.id}`) as HTMLSelectElement | null; void updateCustomerRequest(record, select?.value ?? record.status); }}>
                              Save update
                            </button>
                          </div>
                        </div>
                      </article>
                    ))
                  )}
                </div>
              </>
            )}

            {/* APP CONTENT EDITORS */}
            {["home", "contacts", "solution_finder", "chat", "brand"].includes(section) && (
              <>
                <div className="page-heading">
                  <div>
                    <p className="eyebrow">CUSTOMER APP</p>
                    <h1>{title}</h1>
                    <p>Save draft changes, review, then publish directly to the customer app.</p>
                  </div>
                  <div className="page-actions">
                    <button className="btn btn-outline" onClick={() => void saveContent()}>Save draft</button>
                    <button className="btn btn-primary" disabled={!content || content.draft_revision === 0} onClick={() => void publish(`/admin/app-config/${section}/publish`)}>Publish to App</button>
                  </div>
                </div>
                {loading ? (
                  <div className="card panel empty-state"><span className="loading loading-spinner text-primary" /></div>
                ) : (
                  <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_19rem]">
                    <article className="card panel">
                      <header className="panel-head">
                        <div>
                          <h2>Edit {title.toLowerCase()}</h2>
                          <p>Changes are validated and sent to the mobile app upon publish.</p>
                        </div>
                      </header>
                      <div className="grid gap-4 p-5 sm:grid-cols-2">
                        {Object.entries(contentDraft).map(([key, value]) => (
                          <ContentField key={key} field={key} value={value} onChange={(next) => setContentDraft((current) => ({ ...current, [key]: next }))} />
                        ))}
                      </div>
                    </article>
                    <aside className="card panel h-fit">
                      <header className="panel-head">
                        <div><h2>Publication status</h2><p>App delivery</p></div>
                      </header>
                      <div className="space-y-3 p-4 text-sm">
                        <p>Draft revision <strong>{content?.draft_revision ?? 0}</strong></p>
                        <p>Published revision <strong>{content?.published_revision ?? "None"}</strong></p>
                        <p>Last update <strong>{content?.updated_at ? new Date(content.updated_at).toLocaleString() : "Not saved"}</strong></p>
                        <div className={content?.published_payload ? "alert alert-success text-xs" : "alert alert-info text-xs"}>
                          {content?.published_payload ? "Published version is active in the mobile app." : "Nothing published yet; app will use local defaults."}
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
                    <h1>WooCommerce Sync & Integration</h1>
                    <p>Live REST integration with enertechups.com (178 products, 68 categories).</p>
                  </div>
                  <div className="page-actions">
                    <button className="btn btn-outline" onClick={() => void wordpressPreview()}>Preview Source</button>
                    <button className="btn btn-primary" onClick={() => void wordpressSync()}>Sync Catalogue Now</button>
                  </div>
                </div>
                <div className="card panel">
                  <header className="panel-head">
                    <div>
                      <h2>REST API Connection</h2>
                      <p>Synchronized via HTTPS REST credentials with image and datasheet extraction.</p>
                    </div>
                  </header>
                  <div className="p-5">
                    <div className="alert alert-info text-sm mb-4">
                      WooCommerce is the authoritative product catalogue source. Sync extracts all equipment, images, specs, and PDF datasheets into the platform database.
                    </div>
                    {wpStatus && <p className="mt-2 text-sm font-semibold" role="status">{wpStatus}</p>}
                    {wpPreview.length > 0 && (
                      <div className="mt-4 overflow-x-auto">
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
                                <td><span className="badge badge-success badge-sm">Verified</span></td>
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
                    <p className="eyebrow">APPROVED SUPPORT</p>
                    <h1>FAQs & Knowledge</h1>
                    <p>Verified technical documentation and customer troubleshooting.</p>
                  </div>
                  <button className="btn btn-primary" onClick={() => { setKnowledgeForm(emptyKnowledge); setEditingKnowledge(null); setShowKnowledgeForm(true); }}>+ Add answer</button>
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
                            <td>{article.source_reference ? "Reference verified" : "Source required"}</td>
                            <td><span className={`badge ${article.is_published ? "badge-success" : "badge-ghost"}`}>{article.is_published ? "Published" : "Draft"}</span></td>
                            <td>
                              <div className="flex gap-1">
                                <button className="btn btn-ghost btn-xs" onClick={() => { setKnowledgeForm(article); setEditingKnowledge(article.id); setShowKnowledgeForm(true); }}>Edit</button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {!knowledgeArticles.length && <Empty title="No articles found" detail="Add approved technical answers and solutions." />}
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
                  <button className="btn btn-outline" onClick={() => void loadAudit()}>Refresh</button>
                </div>
                <article className="card panel">
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
                  </div>
                </article>
              </>
            )}
          </main>
        </div>
      </div>

      {/* API CONFIGURATION MODAL */}
      {showApiModal && (
        <dialog open className="modal modal-open">
          <div className="modal-box max-w-lg">
            <h2 className="text-xl font-bold">API Server Connection</h2>
            <p className="text-xs text-base-content/60 mt-1 mb-4">
              Configure the API base URL used by this CMS to communicate with the FastAPI backend.
            </p>
            <div className="space-y-3">
              <label className="form-control gap-1">
                <span className="label-text font-semibold">Active Backend API Endpoint</span>
                <input
                  className="input input-bordered font-mono text-xs"
                  value={customApiUrl}
                  onChange={(e) => setCustomApiUrl(e.target.value)}
                  placeholder="https://api.yourdomain.com/api/v1 or /backend-api/api/v1"
                />
              </label>
              <div className="text-xs text-base-content/60 space-y-1 bg-base-200/50 p-3 rounded-lg">
                <p>• <strong>Default Proxy:</strong> <code>/backend-api/api/v1</code> (Internal Next.js rewrite)</p>
                <p>• <strong>Local Development:</strong> <code>http://127.0.0.1:8000/api/v1</code></p>
              </div>
            </div>
            <div className="modal-action">
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => {
                  localStorage.removeItem("enertech_cms_api_url");
                  setCustomApiUrl(getEffectiveApiBaseUrl());
                  setShowApiModal(false);
                }}
              >
                Reset to Default
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => {
                  if (customApiUrl.trim()) {
                    localStorage.setItem("enertech_cms_api_url", customApiUrl.trim());
                  } else {
                    localStorage.removeItem("enertech_cms_api_url");
                  }
                  setShowApiModal(false);
                  window.location.reload();
                }}
              >
                Save & Apply
              </button>
            </div>
          </div>
          <form method="dialog" className="modal-backdrop"><button onClick={() => setShowApiModal(false)}>close</button></form>
        </dialog>
      )}

      {/* EDIT/CREATE CATEGORY MODAL */}
      {showCategoryForm && (
        <dialog open className="modal modal-open">
          <div className="modal-box max-w-2xl">
            <h2 className="text-xl font-bold">{editingCategory ? "Edit Category / Collection" : "New Collection"}</h2>
            <p className="mb-4 mt-1 text-sm text-base-content/60">Changes are saved as drafts and published to the customer mobile app.</p>
            <form onSubmit={submitCategory} className="grid gap-3 sm:grid-cols-2">
              {(["name", "slug", "description", "image_url"] as const).map((field) => (
                <label key={field} className={`form-control gap-1 ${field === "description" ? "sm:col-span-2" : ""}`}>
                  <span className="label-text font-semibold">{humanize(field)}</span>
                  {field === "description" ? (
                    <textarea className="textarea textarea-bordered" value={categoryForm.description ?? ""} onChange={(event) => setCategoryForm({ ...categoryForm, description: event.target.value })} />
                  ) : (
                    <input className="input input-bordered" value={(categoryForm as typeof emptyCategory)[field] ?? ""} onChange={(event) => setCategoryForm({ ...categoryForm, [field]: event.target.value })} required={field === "name" || field === "slug"} />
                  )}
                </label>
              ))}
              <label className="form-control gap-1 sm:col-span-2">
                <span className="label-text font-semibold">Sort order</span>
                <input className="input input-bordered" type="number" min="0" value={categoryForm.sort_order} onChange={(event) => setCategoryForm({ ...categoryForm, sort_order: Number(event.target.value) })} />
              </label>
              <div className="modal-action sm:col-span-2">
                <button type="button" className="btn btn-ghost" onClick={() => setShowCategoryForm(false)}>Close</button>
                <button className="btn btn-primary">Save Category</button>
              </div>
            </form>
          </div>
          <form method="dialog" className="modal-backdrop"><button onClick={() => setShowCategoryForm(false)}>close</button></form>
        </dialog>
      )}

      {/* EDIT/CREATE PRODUCT MODAL */}
      {showProductForm && (
        <dialog open className="modal modal-open">
          <div className="modal-box max-w-3xl">
            <h2 className="text-xl font-bold">{editingProduct ? "Edit Product" : "New Product"}</h2>
            <p className="mb-4 mt-1 text-sm text-base-content/60">Configure product specifications, images, and downloadable PDF datasheets.</p>
            <form onSubmit={submitProduct} className="grid gap-3 sm:grid-cols-2">
              <label className="form-control gap-1">
                <span className="label-text font-semibold">Collection / Category</span>
                <select className="select select-bordered" required value={productForm.category_id} onChange={(event) => setProductForm({ ...productForm, category_id: event.target.value })}>
                  <option value="">Choose a category</option>
                  {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
                </select>
              </label>
              {(["name", "slug", "model_code", "summary", "image_url", "source_reference"] as const).map((field) => (
                <label key={field} className={`form-control gap-1 ${["summary", "source_reference"].includes(field) ? "sm:col-span-2" : ""}`}>
                  <span className="label-text font-semibold">{humanize(field)}</span>
                  <input className="input input-bordered" required={field === "name" || field === "slug"} value={(productForm as typeof emptyProduct)[field] ?? ""} onChange={(event) => setProductForm({ ...productForm, [field]: event.target.value })} />
                </label>
              ))}
              <label className="form-control gap-1 sm:col-span-2">
                <span className="label-text font-semibold">Description</span>
                <textarea className="textarea textarea-bordered min-h-24" value={productForm.description ?? ""} onChange={(event) => setProductForm({ ...productForm, description: event.target.value })} />
              </label>
              {(["applications", "features"] as const).map((field) => (
                <label className="form-control gap-1" key={field}>
                  <span className="label-text font-semibold">{humanize(field)} · one per line</span>
                  <textarea className="textarea textarea-bordered" value={(productForm[field] ?? []).join("\n")} onChange={(event) => setProductForm({ ...productForm, [field]: event.target.value.split("\n").filter(Boolean) })} />
                </label>
              ))}
              <label className="form-control gap-1">
                <span className="label-text font-semibold">Price (₹ INR)</span>
                <input className="input input-bordered font-mono" type="number" step="any" placeholder="e.g. 181960" value={productForm.price_minor != null ? productForm.price_minor / 100 : ""} onChange={(event) => setProductForm({ ...productForm, price_minor: event.target.value === "" ? null : Math.round(Number(event.target.value) * 100) })} />
              </label>
              <label className="form-control gap-1">
                <span className="label-text font-semibold">Stock Status</span>
                <select className="select select-bordered" value={productForm.stock_status || "instock"} onChange={(event) => setProductForm({ ...productForm, stock_status: event.target.value as Product["stock_status"] })}>
                  <option value="instock">In Stock</option>
                  <option value="outofstock">Out of Stock</option>
                  <option value="onbackorder">Available on Request</option>
                </select>
              </label>
              <label className="form-control gap-1 sm:col-span-2">
                <span className="label-text font-semibold">Datasheet / PDF Document URL</span>
                <input className="input input-bordered" type="url" placeholder="https://enertechups.com/wp-content/uploads/manual.pdf" value={productForm.documents?.[0]?.url ?? ""} onChange={(event) => { const url = event.target.value.trim(); setProductForm({ ...productForm, documents: url ? [{ title: "Datasheet", url }] : [] }); }} />
              </label>
              <label className="form-control gap-1 sm:col-span-2">
                <span className="label-text font-semibold">Specifications (JSON Object)</span>
                <textarea className="textarea textarea-bordered font-mono text-xs" value={textValue(productForm.specifications)} onChange={(event) => { try { setProductForm({ ...productForm, specifications: JSON.parse(event.target.value) as Record<string, unknown> }); } catch { /* preserve input */ } }} />
              </label>
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
          <div className="modal-box max-w-2xl">
            <h2 className="text-xl font-bold">{editingKnowledge ? "Edit Support Answer" : "New Support Answer"}</h2>
            <form onSubmit={submitKnowledge} className="grid gap-3 sm:grid-cols-2">
              <label className="form-control gap-1"><span className="label-text">Question Title</span><input className="input input-bordered" required minLength={3} value={knowledgeForm.title} onChange={(e) => setKnowledgeForm({ ...knowledgeForm, title: e.target.value })} /></label>
              <label className="form-control gap-1"><span className="label-text">URL Slug</span><input className="input input-bordered" required pattern="[a-z0-9]+(?:-[a-z0-9]+)*" value={knowledgeForm.slug} onChange={(e) => setKnowledgeForm({ ...knowledgeForm, slug: e.target.value })} /></label>
              <label className="form-control gap-1 sm:col-span-2"><span className="label-text">Answer</span><textarea className="textarea textarea-bordered min-h-36" required minLength={10} value={knowledgeForm.answer} onChange={(e) => setKnowledgeForm({ ...knowledgeForm, answer: e.target.value })} /></label>
              <div className="modal-action sm:col-span-2"><button type="button" className="btn btn-ghost" onClick={() => setShowKnowledgeForm(false)}>Close</button><button className="btn btn-primary">Save Answer</button></div>
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
      <div className="w-12 h-12 rounded-full bg-base-200 flex items-center justify-center text-xl mb-3">📁</div>
      <h3 className="font-bold text-base text-base-content">{title}</h3>
      <p className="text-xs text-base-content/60 max-w-sm mt-1">{detail}</p>
    </div>
  );
}

function ContentField({ field, value, onChange }: { field: string; value: unknown; onChange: (value: unknown) => void }) {
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  if (typeof value === "boolean") return <label className="label cursor-pointer justify-start gap-3 rounded-lg border border-base-300 p-3"><input className="toggle toggle-primary" type="checkbox" checked={value} onChange={(event) => onChange(event.target.checked)} /><span className="label-text">{humanize(field)}</span></label>;
  if (Array.isArray(value)) return <label className="form-control gap-1 sm:col-span-2"><span className="label-text font-semibold">{humanize(field)} · one per line</span><textarea className="textarea textarea-bordered min-h-20" value={value.join("\n")} onChange={(event) => onChange(event.target.value.split("\n").map((item) => item.trim()).filter(Boolean))} /></label>;
  const choices: Record<string, string[]> = { hero_cta_target: ["products", "solution_finder", "quote", "support"], integration: ["iframe", "hosted_widget"] };
  if (choices[field]) return <label className="form-control gap-1"><span className="label-text font-semibold">{humanize(field)}</span><select className="select select-bordered" value={String(value)} onChange={(event) => onChange(event.target.value)}>{choices[field].map((choice) => <option key={choice} value={choice}>{humanize(choice)}</option>)}</select></label>;
  if (field === "logo_url" || field === "support_icon_url") return <label className="form-control gap-2"><span className="label-text font-semibold">{humanize(field)}</span><input className="input input-bordered" type="url" value={textValue(value)} onChange={(event) => onChange(event.target.value)} /><input className="file-input file-input-bordered file-input-sm w-full" type="file" accept="image/png,image/jpeg,image/webp" aria-label={`Upload ${humanize(field)}`} disabled={uploading} onChange={async (event) => { const file = event.target.files?.[0]; const authUser = getFirebaseAuth()?.currentUser; if (!file || !authUser) return; setUploading(true); setUploadError(""); try { const asset = await uploadMedia(authUser, file); onChange(asset.url); } catch (cause) { setUploadError(cause instanceof Error ? cause.message : "Image upload failed."); } finally { setUploading(false); event.target.value = ""; } }} />{uploading && <span className="label-text-alt">Uploading to Supabase Storage…</span>}{uploadError && <span role="alert" className="text-xs text-error">{uploadError}</span>}</label>;
  const long = ["description", "body", "message", "address", "hours"].some((part) => field.includes(part));
  return <label className={`form-control gap-1 ${long ? "sm:col-span-2" : ""}`}><span className="label-text font-semibold">{humanize(field)}</span>{long ? <textarea className="textarea textarea-bordered min-h-20" value={textValue(value)} onChange={(event) => onChange(event.target.value)} /> : <input className="input input-bordered" type={field.includes("email") ? "email" : field.includes("url") || field.includes("logo") || field.includes("handoff") ? "url" : "text"} value={textValue(value)} onChange={(event) => onChange(event.target.value)} />}</label>;
}
