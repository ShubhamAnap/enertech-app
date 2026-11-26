"use client";

import type { User } from "firebase/auth";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, uploadMedia, type Category, type CategoryCatalogue, type Product } from "@/lib/api";

type ModalCallbacks = {
  user: User;
  onNotice: (message: string) => void;
  onError: (message: string) => void;
  onRefresh: () => Promise<void>;
};

export function CollectionCataloguePdfModal({
  target,
  catalogueRecord,
  onClose,
  user,
  onNotice,
  onError,
  onRefresh,
}: ModalCallbacks & {
  target: Category | null;
  catalogueRecord?: CategoryCatalogue;
  onClose: () => void;
}) {
  const [title, setTitle] = useState(target ? target.catalog_pdf_title || `${target.name} Catalogue PDF` : "");
  const [url, setUrl] = useState(target?.catalog_pdf_url || "");
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);

  if (!target) return null;

  async function handleSave(event: FormEvent) {
    event.preventDefault();
    if (!target) return;
    setSaving(true);
    onError("");
    onNotice("");
    try {
      await api(user, "/admin/catalogue/category-catalogues", {
        method: "PUT",
        body: JSON.stringify({
          category_key: target.slug,
          category_id: target.id,
          wordpress_category_id: target.wordpress_source_id,
          title: title.trim() || `${target.name} Catalogue PDF`,
          catalog_pdf_url: url.trim(),
        }),
      });
      onNotice(`Catalogue PDF saved for "${target.name}". Products without their own PDF now inherit it.`);
      onClose();
      await onRefresh();
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : "Could not save collection catalogue PDF.");
    } finally {
      setSaving(false);
    }
  }

  async function handleRemove() {
    if (!catalogueRecord || !target) return;
    if (!window.confirm(`Remove the collection catalogue PDF from "${target.name}"?`)) return;
    setSaving(true);
    onError("");
    onNotice("");
    try {
      await api(user, `/admin/catalogue/category-catalogues/${catalogueRecord.id}`, { method: "DELETE" });
      onNotice(`Removed collection catalogue PDF from "${target.name}".`);
      onClose();
      await onRefresh();
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : "Could not remove collection catalogue PDF.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <dialog open className="modal modal-open">
      <div className="modal-box max-h-[90dvh] overflow-y-auto max-w-lg">
        <h2 className="text-xl font-bold">Collection Catalogue PDF</h2>
        <p className="mb-4 mt-1 text-sm text-base-content/60">
          Products in <strong>{target.name}</strong> without a product-specific PDF inherit this brochure, and future WooCommerce syncs preserve it.
        </p>
        <form onSubmit={handleSave} className="grid gap-3">
          <label className="form-control gap-1">
            <span className="label-text font-semibold">Brochure Title</span>
            <input className="input input-bordered" required maxLength={180} value={title} onChange={(e) => setTitle(e.target.value)} />
          </label>
          <label className="form-control gap-1">
            <span className="label-text font-semibold">Catalogue PDF HTTPS URL</span>
            <input className="input input-bordered" type="url" required placeholder="https://…" value={url} onChange={(e) => setUrl(e.target.value)} />
          </label>
          <label className="form-control gap-1">
            <span className="label-text font-semibold">Or upload a PDF brochure (max 20 MB)</span>
            <input
              className="file-input file-input-bordered file-input-sm w-full"
              type="file"
              accept="application/pdf,.pdf"
              disabled={uploading || saving}
              onChange={async (event) => {
                const file = event.target.files?.[0];
                if (!file) return;
                setUploading(true);
                onError("");
                try {
                  const asset = await uploadMedia(user, file);
                  setUrl(asset.url);
                } catch (cause) {
                  onError(cause instanceof Error ? cause.message : "PDF upload failed.");
                } finally {
                  setUploading(false);
                  event.target.value = "";
                }
              }}
            />
            {uploading && <span className="label-text-alt">Uploading PDF…</span>}
          </label>
          <div className="modal-action flex-wrap justify-between">
            <div>
              {catalogueRecord && (
                <button type="button" className="btn btn-ghost btn-sm text-error" disabled={uploading || saving} onClick={() => void handleRemove()}>
                  Remove PDF
                </button>
              )}
            </div>
            <div className="flex gap-2">
              <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
              <button className="btn btn-primary" disabled={uploading || saving}>Save Catalogue PDF</button>
            </div>
          </div>
        </form>
      </div>
      <form method="dialog" className="modal-backdrop"><button onClick={onClose}>close</button></form>
    </dialog>
  );
}

export function ProductPdfOverrideModal({
  target,
  onClose,
  user,
  onNotice,
  onError,
  onRefresh,
}: ModalCallbacks & {
  target: Product | null;
  onClose: () => void;
}) {
  const existingOwn = target && target.catalog_pdf_source === "product" ? target.documents[0] : undefined;
  const [title, setTitle] = useState(existingOwn?.title || (target ? `${target.name} Brochure` : "Product brochure"));
  const [url, setUrl] = useState(existingOwn?.url || "");
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);

  if (!target) return null;

  async function handleSave(event: FormEvent) {
    event.preventDefault();
    if (!target) return;
    setSaving(true);
    onError("");
    onNotice("");
    try {
      await api(user, `/admin/catalogue/products/${target.id}/pdf`, {
        method: "PUT",
        body: JSON.stringify({
          title: title.trim() || `${target.name} Brochure`,
          url: url.trim(),
        }),
      });
      onNotice(`Updated product PDF for "${target.name}".`);
      onClose();
      await onRefresh();
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : "Could not save product PDF.");
    } finally {
      setSaving(false);
    }
  }

  async function handleClear(syncWithWordpress: boolean) {
    if (!target) return;
    setSaving(true);
    onError("");
    onNotice("");
    try {
      await api(user, `/admin/catalogue/products/${target.id}/pdf?sync_with_wordpress=${syncWithWordpress}`, {
        method: "DELETE",
      });
      onNotice(
        syncWithWordpress
          ? `Cleared CMS PDF lock for "${target.name}". Future WordPress syncs can manage its brochure.`
          : `Cleared product PDF for "${target.name}". It now falls back to its collection PDF (if configured).`,
      );
      onClose();
      await onRefresh();
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : "Could not clear product PDF.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <dialog open className="modal modal-open">
      <div className="modal-box max-h-[90dvh] overflow-y-auto max-w-lg">
        <div className="flex items-start justify-between gap-2">
          <div>
            <h2 className="text-xl font-bold">Product Brochure PDF</h2>
            <p className="mt-1 text-sm text-base-content/65">{target.name}</p>
          </div>
          {target.documents_override && <span className="badge badge-info badge-sm">Pinned in CMS</span>}
        </div>

        <div className="mt-3 rounded-lg border border-base-300 bg-base-200/50 p-3 text-xs text-base-content/75">
          <div>
            <strong>Current source:</strong>{" "}
            {target.catalog_pdf_source === "product"
              ? "Product-specific PDF"
              : target.catalog_pdf_source === "category"
                ? "Inherited from assigned collections"
                : "No brochure attached"}
          </div>
          {target.catalog_pdf_url && (
            <a href={target.catalog_pdf_url} target="_blank" rel="noreferrer" className="link link-primary mt-1 inline-block break-all">
              Open current PDF
            </a>
          )}
        </div>

        <form onSubmit={handleSave} className="mt-3 grid gap-3">
          <label className="form-control gap-1">
            <span className="label-text font-semibold">PDF Title</span>
            <input className="input input-bordered" required maxLength={180} value={title} onChange={(e) => setTitle(e.target.value)} />
          </label>
          <label className="form-control gap-1">
            <span className="label-text font-semibold">Product PDF HTTPS URL</span>
            <input className="input input-bordered" type="url" required placeholder="https://…" value={url} onChange={(e) => setUrl(e.target.value)} />
          </label>
          <label className="form-control gap-1">
            <span className="label-text font-semibold">Upload actual PDF (max 20 MB)</span>
            <input
              className="file-input file-input-bordered file-input-sm w-full"
              type="file"
              accept="application/pdf,.pdf"
              disabled={uploading || saving}
              onChange={async (event) => {
                const file = event.target.files?.[0];
                if (!file) return;
                setUploading(true);
                onError("");
                try {
                  const asset = await uploadMedia(user, file);
                  setUrl(asset.url);
                } catch (cause) {
                  onError(cause instanceof Error ? cause.message : "PDF upload failed.");
                } finally {
                  setUploading(false);
                  event.target.value = "";
                }
              }}
            />
            {uploading && <span className="label-text-alt">Uploading PDF to Supabase Storage…</span>}
          </label>

          <div className="modal-action flex-wrap justify-between gap-2">
            <div className="flex flex-wrap gap-1.5">
              {(target.catalog_pdf_source === "product" || target.documents_override) && (
                <button type="button" className="btn btn-ghost btn-sm text-error" disabled={uploading || saving} onClick={() => void handleClear(false)}>
                  Clear PDF
                </button>
              )}
              {target.wordpress_source_id && target.documents_override && (
                <button type="button" className="btn btn-ghost btn-sm" disabled={uploading || saving} onClick={() => void handleClear(true)}>
                  Reset to WP
                </button>
              )}
            </div>
            <div className="flex gap-2">
              <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
              <button className="btn btn-primary" disabled={uploading || saving}>Save PDF</button>
            </div>
          </div>
        </form>
      </div>
      <form method="dialog" className="modal-backdrop"><button onClick={onClose}>close</button></form>
    </dialog>
  );
}

export function ProductCategoryOverrideModal({
  target,
  categories,
  onClose,
  user,
  onNotice,
  onError,
  onRefresh,
}: ModalCallbacks & {
  target: Product | null;
  categories: Category[];
  onClose: () => void;
}) {
  const [primaryId, setPrimaryId] = useState(target?.app_collection_ids.includes(target.category_id) ? target.category_id : target?.app_collection_ids[0] ?? "");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(
    () => new Set(target?.app_collection_ids ?? []),
  );
  const [filterText, setFilterText] = useState("");
  const [saving, setSaving] = useState(false);

  if (!target) return null;

  const visibleCategories = categories.filter((c) => {
    const q = filterText.trim().toLowerCase();
    return !q || c.name.toLowerCase().includes(q) || c.slug.toLowerCase().includes(q);
  });

  async function save() {
    if (!target || !primaryId) return;
    setSaving(true);
    onError("");
    onNotice("");
    const orderedIds = [primaryId, ...[...selectedIds].filter((id) => id !== primaryId)];
    try {
      await api(user, `/admin/catalogue/products/${target.id}/categories`, {
        method: "PUT",
        body: JSON.stringify({
          category_id: primaryId,
          category_ids: orderedIds,
        }),
      });
      onNotice(`Updated collections for "${target.name}".`);
      onClose();
      await onRefresh();
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : "Could not update product collections.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <dialog open className="modal modal-open">
      <div className="modal-box max-h-[90dvh] overflow-y-auto max-w-xl">
        <div className="flex items-start justify-between gap-2">
          <div>
            <h2 className="text-xl font-bold">Product Collections</h2>
            <p className="mt-1 text-sm text-base-content/65">{target.name}</p>
          </div>
          {target.category_override && <span className="badge badge-info badge-sm">Pinned in CMS</span>}
        </div>
        {target.wordpress_source_id && (
          <p className="mt-2 rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-900">
            Saving here pins the primary &amp; linked collections in CMS so future WordPress syncs update prices, specs, and stock without reverting your category changes.
          </p>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            void save();
          }}
          className="mt-3 grid gap-3"
        >
          <label className="form-control gap-1">
            <span className="label-text font-semibold">Primary Collection (controls mobile category badge &amp; default PDF inheritance)</span>
            <select
              className="select select-bordered select-sm"
              required
              value={primaryId}
              onChange={(event) => {
                const nextPrimary = event.target.value;
                setPrimaryId(nextPrimary);
                setSelectedIds((current) => new Set([...current, nextPrimary]));
              }}
            >
              <option value="">Choose a collection</option>
              {categories.map((cat) => (
                <option key={cat.id} value={cat.id}>
                  {cat.name} ({cat.product_count ?? 0}){cat.is_published ? "" : " [Hidden]"}
                </option>
              ))}
            </select>
          </label>

          <div className="grid gap-1.5">
            <div className="flex items-center justify-between gap-2">
              <span className="label-text font-semibold">Additional Linked Collections ({selectedIds.size} selected)</span>
              <input
                className="input input-bordered input-xs w-48"
                placeholder="Filter collections…"
                value={filterText}
                onChange={(e) => setFilterText(e.target.value)}
              />
            </div>
            <div className="grid max-h-56 grid-cols-1 gap-1 overflow-y-auto rounded-lg border border-base-300 p-2 sm:grid-cols-2">
              {visibleCategories.map((cat) => {
                const isPrimary = cat.id === primaryId;
                const checked = isPrimary || selectedIds.has(cat.id);
                return (
                  <label key={cat.id} className={`flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-xs ${checked ? "bg-primary/5" : "hover:bg-base-200/60"}`}>
                    <input
                      type="checkbox"
                      className="checkbox checkbox-xs checkbox-primary"
                      checked={checked}
                      disabled={isPrimary}
                      onChange={(event) => {
                        setSelectedIds((current) => {
                          const next = new Set(current);
                          if (event.target.checked) next.add(cat.id);
                          else next.delete(cat.id);
                          return next;
                        });
                      }}
                    />
                    <span className="flex-1 truncate" title={cat.name}>
                      {cat.name}
                    </span>
                    {!cat.is_published && <span className="badge badge-ghost badge-xs">Hidden</span>}
                  </label>
                );
              })}
            </div>
          </div>

          <div className="modal-action flex-wrap justify-between gap-2">
            <div className="flex gap-2">
              <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
              <button className="btn btn-primary" disabled={saving || !primaryId}>Save Collections</button>
            </div>
          </div>
        </form>
      </div>
      <form method="dialog" className="modal-backdrop"><button onClick={onClose}>close</button></form>
    </dialog>
  );
}

type AssignmentRow = {
  id: string;
  name: string;
  sku: string | null;
  checked: boolean;
  assigned: boolean;
  tag_ids: string[];
};

type AssignmentOptions = { products: AssignmentRow[]; tags: Pick<Category, "id" | "name">[] };

export function AssignProductsModal({ target, user, onClose, onRefresh, onNotice }: ModalCallbacks & {
  target: Category;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [options, setOptions] = useState<AssignmentOptions | null>(null);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [tag, setTag] = useState("");
  const [status, setStatus] = useState("all");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const path = `/admin/catalogue/categories/${target.id}/products`;

  useEffect(() => {
    dialog.current?.showModal();
    let active = true;
    api<AssignmentOptions>(user, path).then((data) => {
      if (!active) return;
      setChecked(new Set(data.products.filter((p) => p.checked).map((p) => p.id)));
      setOptions(data);
    }).catch((cause) => { if (active) setError(cause.message); });
    return () => { active = false; };
  }, [user, path]);

  const query = search.trim().toLowerCase();
  const matching = options?.products.filter((p) =>
    (p.name.toLowerCase().includes(query) || p.sku?.toLowerCase().includes(query)) &&
    (!tag || p.tag_ids.includes(tag)) &&
    (status === "all" || (status === "member" ? p.checked : !p.assigned))
  ) ?? [];

  function toggle(ids: string[], value: boolean) {
    setChecked((current) => {
      const next = new Set(current);
      for (const id of ids) { if (value) next.add(id); else next.delete(id); }
      return next;
    });
  }

  async function save() {
    if (!options || saving) return;
    setSaving(true);
    setError("");
    try {
      await api(user, path, { method: "PUT", body: JSON.stringify({
        product_ids: [...checked],
        previous_product_ids: options.products.filter((p) => p.checked).map((p) => p.id),
      }) });
      await onRefresh();
      onNotice(`Saved ${checked.size} products in ${target.name}.`);
      onClose();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save collection products.");
      setSaving(false);
    }
  }

  return <dialog ref={dialog} className="modal" aria-labelledby="assignment-title" onCancel={(e) => { e.preventDefault(); if (!saving) onClose(); }}>
    <div className="modal-box max-w-2xl">
      <h2 className="text-xl font-bold" id="assignment-title">Assign products to {target.name}</h2>
      {error && <p role="alert" className="alert alert-error mt-3">{error}</p>}
      {!options && !error && <p role="status">Loading products…</p>}
      {options && <fieldset disabled={saving} className="mt-4 grid gap-3">
        <label>Search by name or SKU<input type="search" className="input w-full" value={search} onChange={(e) => setSearch(e.target.value)} /></label>
        <div className="grid gap-2 sm:grid-cols-2">
          <label>WordPress tag<select className="select w-full" value={tag} onChange={(e) => setTag(e.target.value)}>
            <option value="">All tags</option>{options.tags.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select></label>
          <label>Assignment status<select className="select w-full" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="all">All products</option><option value="member">Already in this collection</option><option value="unassigned">Unassigned to any collection</option>
          </select></label>
        </div>
        <div className="flex items-center gap-2">
          <button className="btn btn-sm" onClick={() => toggle(matching.map((p) => p.id), true)}>Select all matching ({matching.length})</button>
          <span role="status">{checked.size} selected</span>
        </div>
        <div className="max-h-64 overflow-y-auto">
          {matching.map((p) => <label key={p.id} className="flex items-center gap-3 py-2">
            <input type="checkbox" className="checkbox checkbox-sm" checked={checked.has(p.id)} onChange={(e) => toggle([p.id], e.target.checked)} />
            <span>{p.name}{p.sku && <small className="block">{p.sku}</small>}</span>
          </label>)}
          {!matching.length && <p>No matching products.</p>}
        </div>
      </fieldset>}
      <div className="modal-action">
        <button className="btn" disabled={saving} onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" disabled={!options || saving} onClick={() => void save()}>Save collection products</button>
      </div>
    </div>
  </dialog>;
}
