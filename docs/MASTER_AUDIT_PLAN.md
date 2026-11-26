# EnerTech App, CMS and API Audit Plan

Audit snapshot: 2026-11-25
Scope: Flutter Android app, Next.js CMS, FastAPI service, database/migrations, WooCommerce integration and Coolify deployment.

## Executive audit result

The project has a working source-level foundation and most of the core catalogue/content/request flows are implemented. It is **not production-verified end to end**. At audit time, requests to `api.enertechups.cloud` and `cms.enertechups.cloud` time out from this workstation. The connected Android device is visible to ADB, but source and screenshots do not prove a fresh live API request or CMS publish reached that device.

The product screenshot provided on 25 November shows a product with published catalogue data (title/specifications/price/stock) and an empty product `documents` collection. The app’s “No product brochure or datasheet…” state is therefore consistent with the payload it received. It does not establish that the CMS connection is broken. A PDF can only appear when its public HTTPS URL is present in that product’s API `documents` field. A fresh production API record and the corresponding WordPress product response could not be inspected because both hosts time out from this workstation.

## Current evidence and limits

| Area | Evidence observed | What it proves / does not prove |
|---|---|---|
| Source checkout | Branch `main`, local `HEAD` `417c97c`; GitHub `main` `44a2d0c`; 103 commits between recorded `origin/main` and GitHub head; many local changes | Local and remote source have diverged substantially. Do not push the local tree wholesale; reconcile targeted changes against current GitHub files. `git fetch` cannot authenticate in this workstation. |
| Phone | ADB device `Y5XCTWHIBEE6VKFM` is connected; signed app version `0.1.2` (code 3) reinstalled; label `ENERTECH`; launch intent delivered | Package install and launch work. It does not prove sign-in or live API flows. |
| API/CMS domains | HTTPS API readiness/catalogue and CMS requests timed out from this workstation | Live checks are currently unavailable from here; this is not proof the services are down globally. |
| Screenshot product | Product has price, stock, and structured specs; document state is empty | Catalogue data is present in the app’s current view. This product record lacks a PDF link. It does not identify whether the PDF is missing in WordPress or was dropped during sync. |
| CMS/API code | The API has authenticated admin, catalogue, content, request, contact inquiry, knowledge, upload, audit, and WordPress routes | These workflows exist in source. They need live authorization, database, and end-to-end confirmation. |
| WordPress document importer | Local source now checks downloads, configured custom fields, named Woo meta fields, PDF links in descriptions, and attached PDF media; sync reports `documents_linked`. Local source also uses Store API when REST keys are absent. | Python syntax compiles, but backend tests could not run because the available Python environment lacks FastAPI and pytest. Production source data and sync are still unverified. |

## User-visible data flow

```text
WordPress / WooCommerce
       │ product, category, price, stock, image, documents
       ▼
FastAPI sync ──► Supabase/PostgreSQL catalogue
       │                        │
       │ CMS reads/writes       ├── published product/category API ──► Mobile app
       │                        └── published app-config/FAQ API ─────► Mobile app
       ▼
Next.js CMS
```

WordPress-owned products and categories are intentionally read-only in the CMS; they must be corrected in WordPress and synced. CMS-authored products/categories can be edited and published in the CMS. This ownership split must be explained in the product editor so staff know where a missing PDF has to be added.

## Coverage audit

### Mobile app

| Capability | Source status | Outstanding work |
|---|---|---|
| Login, email/password, Google sign-in, profile onboarding | Implemented in source | Verify release Firebase providers, OAuth client and sign-in on the connected phone. |
| Five primary tabs: Home, Products, Requests, Support, Account | Implemented | Device QA at normal text size, landscape, smaller screens and large accessibility text. |
| Home hero, search text, intent copy, announcements, featured products/collections, section order/visibility | CMS config fields are consumed | Verify publish-to-phone refresh and stale/error handling; ensure featured selectors cannot select hidden/unpublished records. |
| Product catalogue, category/collection filtering, search, compare | Implemented against published catalogue API | Verify category memberships after live sync and correct behavior with >500 products, pagination, empty and offline states. |
| Product details, price/stock, specifications, product documents | Implemented against API product payload | Current screenshot product has no documents. Validate PDF source path, sync, CMS card/editor, app detail and document library with a known product. Product detail toolbar now displays the product name in the local source; phone verification is pending. |
| Quote/RFQ via Solution Finder and product/compare paths | Request submission/list API is implemented | Attachments are absent; there is no quotation issue/revision/view/acceptance model or customer quotation document screen. |
| Service request and tracking | API submit and customer request list/status text implemented | Photo upload is explicitly disabled; request detail/timeline, appointment and resolution activity model are absent. |
| Company contact details, support contacts, FAQ, brand logo, support icon, chat config | Published CMS fields are consumed in source | The Home screen now uses the supplied transparent EnerTech wordmark and Android launcher uses the same mark with the requested `ENERTECH` label. Verify each setting on live app; external chat script/provider contract and direct-contact configuration need real credentials/URLs. |
| Information library | Reads HTTPS documents from published products | Library only contains documents that were imported. No separate CMS-managed manuals/document library or private-file access exists. |
| Registered equipment, warranty/AMC, notifications, addresses, privacy/settings | Not implemented | Add only after company policy/source-of-truth decisions; remove/avoid UI claims that imply availability. |

### CMS and administration

| Module | Source status | Outstanding work |
|---|---|---|
| Overview | Real catalogue/customer/request counts; explicit notice that sales/order/time-series analytics are not connected | Do not present unsupported metrics as operational analytics; add actionable queues only when backed by APIs. |
| Products and collections | Search, pagination, table/grid, draft/publish, media, documents; WooCommerce records are read-only | Improve product image/name/price/PDF scanability and collection badge wrapping. Add a direct, clear route to WordPress for source-owned records. |
| WordPress import/sync | Status, preview, import as drafts, sync and counters exist | Live API base URL, credentials, routes, field mappings, sync result, deletions/withdrawals and document count require production verification. |
| Home screen | Hero, CTA, featured items, announcement, ordering and visibility are editable | Preview should represent the customer app; verify every field and empty/default behavior after publish. |
| Contact details / brand / Solution Finder / chat / FAQ | Draft/publish editors exist and corresponding app consumers exist | Verify field-by-field on device. Confirm business-approved contact values, hosting/chat allowlist, sources and FAQ correctness. |
| Quote enquiries and service requests | Search/filter, customer profile fields, assignment, status transitions, notes, pagination | This is enquiry/ticket triage, not quotation management. Add request detail/activity/attachments and separate quote creation/publishing only after workflow approval. |
| Contact enquiries | Customer form and CMS queue exist | Verify end-to-end delivery, PII policy, validation and handling of unverified/anonymous submissions. |
| Customers, admin access, audit history | APIs and CMS modules exist | Verify least-privilege roles, admin provisioning, audit coverage, pagination/export semantics and PII access. |
| Quotation documents, equipment, manuals, notifications, settings | Not implemented as complete modules | Define system of record, owner, permissions, statuses, retention and delivery before adding real UI. |

### Backend, database and platform

- Current API routes cover health/readiness, public catalogue/config/knowledge, CMS-authenticated content/catalogue/operations, customer profiles/requests, media upload and WordPress import/sync.
- Product categories support a primary category and a many-to-many membership list. The sync maps every source category matched to an imported category. Live source IDs and category slugs must be checked to ensure the intended mappings exist; categories in the database alone do not prove the products belong to them.
- Request creation requires a verified customer identity and uses a per-user database-backed rate limit. Admin authorization is API-enforced. These source controls require security and ownership tests against the deployed database.
- Migration files include contact inquiry compatibility/index, request indexes, and product category memberships. Production migration state is unknown while the API is unreachable. Take a backup and test upgrade/rollback before applying pending migrations to production.
- Media upload uses Supabase Storage and an API service key; file privacy, public bucket policy and retention need production validation. Product document URLs are public HTTPS links, not private downloads.
- No verified load-test, database restore test, alerting, crash monitoring, or 10k-customer concurrency test is in current evidence. Do not infer 10k-user readiness from a successful APK build or a 178-product catalogue.

## Master work plan, in order

### P0 — Establish a safe, observable production baseline

- [ ] Restore workstation-to-production connectivity and capture API `/health/ready`, CMS `/`, TLS/certificate chain, Coolify deployed commit, container health, and redacted runtime startup errors.
- [ ] Verify the signed-in Firebase UID has an active least-privilege CMS account; verify Firebase project ID/service account and exact CMS origin CORS configuration.
- [ ] Verify Supabase connection, migration head, existing schema compatibility, backup freshness, and restore procedure before changing production data.
- [ ] Reconcile local branch against the actual GitHub `main` head and preserve local user changes; publish only reviewed, targeted changes.
- [ ] Rotate any previously exposed service-role or chat secrets and check that browser/app builds contain only public client configuration.

Acceptance: API readiness and CMS role check succeed over HTTPS; database migration state is known; no server-only credentials exist in client artifacts; rollback/backup checkpoint recorded.

### P1 — Resolve product/category/document sync and prove it on one named product

- [ ] In CMS WordPress status, verify site URL, REST routes, auth state and configured document mapping. Use `https://enertechups.com/wp-json` plus valid read-only WooCommerce credentials if the source is WooCommerce REST.
- [ ] Inspect the exact WordPress product JSON for the product in the user screenshot. Check `downloads`, PDF attachment media, and custom ACF/meta field path; confirm the source URL is HTTPS and publicly reachable.
- [ ] Set `WORDPRESS_SOURCE_DOCUMENTS_FIELD` to the real nested field path if the PDF is stored outside standard `downloads`; if the source product has no PDF, upload/attach the approved PDF in WordPress first.
- [ ] Run one sync; record created/updated/withdrawn/category counts and `documents_linked`; verify the product row keeps all intended category memberships, image, price, stock, specs, and document title/URL.
- [ ] Verify the CMS product card exposes the PDF action and the published mobile product detail/library exposes and opens the same PDF. Test query-string PDF URLs and non-PDF links.
- [ ] Add clear CMS copy explaining WordPress-owned items are edited in WordPress; add a missing-document diagnostic to distinguish “source has no PDF” from “sync field mapping did not match.”

Acceptance: one source product can be traced by source ID through WordPress → sync result → DB/API product → CMS card → app detail/PDF open, with matching category and document data.

### P2 — Complete CMS-to-app content management and fix CMS usability

- [ ] Verify contact details can be drafted, published, and reflected in call/WhatsApp/email/address/hours in the app.
- [ ] Verify branding assets/name, Home hero/CTA/featured products/collections/announcements/order/visibility, Solution Finder steps/options, chat/handoff, and published FAQ each reflect in the app after refresh.
- [ ] Improve desktop CMS navigation so the entire module hierarchy is understandable at 100% browser zoom without relying on 50% zoom; keep 100%-width work area, predictable scroll, keyboard access, readable body/table text and clear focused controls.
- [ ] Fix products/collections list density and wrap: readable images/names/price, non-overlapping long category badges, obvious source ownership, and per-product PDF/document action.
- [ ] Improve service/request layout so customer identity and submitted details remain together, controls do not float across excessive empty space, and Save provides success/error/loading feedback.
- [ ] Add preview/validation/unsaved-change feedback consistently to app-content forms; do not allow unpublished or missing-source data to look published.

Acceptance: CMS passes 100% zoom visual review at wide and narrow widths; all editable app-content fields have verified app consumers; no overlap/clipping in realistic long product/category/customer content.

### P3 — Complete customer app core journeys and expose missing work honestly

- [ ] Fix the generic product detail app-bar title; verify image/price/stock/spec formatting and missing-document states with long WooCommerce HTML descriptions.
- [ ] Verify catalogue collections use all imported category memberships, filters/search/pagination work, and selected Home items are published and visible.
- [ ] Run quote, service, contact inquiry, profile update, request refresh/status, compare-to-quote and PDF open journeys against staging/production without creating accidental live data.
- [ ] Implement secure request attachments after accepted file types/count/size, private-storage policy, access/retention and malware controls are specified. The current service-photo control is knowingly disabled.
- [ ] Define and implement quotation revision/document access, request detail/timeline, notifications, registered equipment, verified warranty/AMC, saved addresses and privacy/settings only against approved business workflows and data sources.
- [ ] Keep app labels and Support content explicit for features not configured; no dead controls, fake successes or unsupported “AI verified”/coverage claims.

Acceptance: each customer action has API success/error/loading/empty states, request ownership checks, durable IDs, and a visible confirmation; no unimplemented screen is represented as operational.

### P4 — Security, scale and release verification

- [ ] Run backend unit/API tests for authentication, role/ownership/IDOR boundaries, status transitions, pagination/search, WooCommerce mapping, categories/documents, migrations and uploads.
- [ ] Run Flutter analyze/widget tests and CMS lint/typecheck/build after app/CMS changes. Review accessibility, text scaling, keyboard/focus and 44px touch targets on devices/browsers.
- [ ] Validate API/database connection pool, indexes and request rate limits under an agreed 10k-account growth profile; add monitoring and load tests before claiming capacity.
- [ ] Test empty install, update install, poor network, expired auth, no cache, stale cache, Android back/keyboard, narrow viewport, large font, and signed release on the connected phone.
- [ ] Increment Android version name/code for every distributable update; verify signing key, Firebase SHA-1, package ID, API URL, artifact hash and install result.
- [ ] Reconcile and push the reviewed CMS/API changes, verify the exact deployed commit in Coolify, then build/install the APK from the corresponding app source revision.

Acceptance: source, deployed services and APK commit/config/signature are linked by recorded revision and hash; core workflows pass on the live/staging system; operational rollback and data recovery are demonstrated.

## Immediate diagnosis for the missing PDF

1. The app reads `ProductPublic.documents` from `/api/v1/catalogue/products/{slug}`. Its missing-document message means that array was empty for the product data shown (or the view is displaying an old cached catalogue record until detail fetch completes).
2. The CMS product card can show a PDF only if that same product record contains a valid HTTPS document URL. WordPress-owned products are not editable in the CMS product form by design.
3. The local importer supports WooCommerce `downloads`, matching PDF-related Woo metadata, PDF URLs in descriptions, attached PDF media, and the optional `WORDPRESS_SOURCE_DOCUMENTS_FIELD`. The field path must match the actual REST JSON. `SUPABASE_DATABASE_URL` does not control this integration.
4. Production answer still requires inspecting this product’s WordPress JSON and running a fresh sync. Both production hostnames timed out during this audit, so the source-side cause cannot yet be distinguished from an unset/wrong field mapping.

## Audit boundaries

- Current local code and user screenshots are evidence for source/UI state, not proof of the live deployment.
- The exact WordPress document field path, source PDF, Coolify env values, production migration head, and current remote GitHub head are not available from this machine at audit time.
- Do not run a write operation against production (sync, publish, request submission, migration or secret rotation) until the endpoint is reachable, the intended record is identified, and backup/rollback state is clear.
- This plan is a current audit and execution checklist, not a claim that all listed work is complete.
