# EnerTech App + CMS Master Audit Plan

Audit date: 2026-11-25

Scope: Flutter customer app, Next.js CMS, FastAPI API, database/migrations, and WooCommerce synchronization.
Status: Source-level audit and fixes are ongoing. Production acceptance is not complete. The latest CMS screen proves Firebase sign-in and API role verification are now responding, but the signed-in UID is not authorized as a CMS administrator. The database URL is no longer the current visible failure; provision the first super-admin UID as described below.

## Current delivery snapshot — 2026-11-25

- The local CMS now reports catalogue-load failures instead of treating them as an empty collection list, ignores stale catalogue responses, and can page through every product/collection from the Home featured selectors. Catalogue request size matches the API's 500-item maximum.
- Current local verification (2026-11-25): CMS ESLint and TypeScript `--noEmit` pass; Flutter `analyze` and all six Flutter tests pass. A Next.js production build passed earlier using placeholder public Firebase/API values, not live services.
- Backend verification: 23 pytest checks passed in this turn; Alembic offline SQL compiled through `c42e17b3d906`. Live database migration completion is not visible from the local workspace.
- The workspace `update.apk` is 63,615,191 bytes, matches `apps/mobile/build/app/outputs/flutter-apk/app-release.apk`, and was built at 2026-11-25 10:58 local time. Its v2 signature verifies; signer SHA-1 is `78:EE:94:85:3B:3F:86:21:74:9C:51:3D:9F:02:31:E6:B1:58:09:37` and SHA-256 is `dff76233c8810fc2b05a6c80688223abf2ab4f2f395356f7ece2dca080696080`.
- The current bundled `google-services.json` targets Firebase project `enertech-ups`, package `com.enertech.enertech_customer`, and includes the same Android SHA-1 as the APK signer. This closes the fingerprint/config mismatch at source level, but live Google sign-in and device installation remain unverified.
- The local mobile source reads the Flutter `--dart-define` Firebase values passed by `infra/build-mobile.ps1`, fixing the setup-incomplete path when the `.env` asset is absent. The current APK includes the updated source as of the 10:58 build; GitHub `main` does not yet include the uncommitted worktree edits.
- The user updated `SUPABASE_DATABASE_URL`. The first subsequent API startup failure was a duplicate `contact_inquiries` table because the supplied Supabase schema already contained it. A migration-safe fix was pushed as `c1c0691ba9dbef629a7ab0af89a083ceea8b437f`; the subsequent CMS screen now shows **CMS access not granted**, which is an authorization denial rather than an API/database connectivity error.
- Current CMS gate: the API only grants CMS access to an active `admin_accounts` record or a UID in `BOOTSTRAP_SUPER_ADMIN_UIDS`. The project owner must bootstrap the exact Firebase UID used to sign in, deploy the API, create an active super-admin record in CMS, then remove the temporary bootstrap UID and redeploy.
- The latest browser certificate screenshot shows a Let's Encrypt certificate issued to `cms.enertechups.cloud`, with a validity period of 2026-11-25 through 2027-02-23. Chrome still labels the page `Not secure`; the screenshot alone does not prove the browser used HTTPS or trusted the full certificate chain. Open `https://cms.enertechups.cloud` explicitly and inspect the browser's certificate/connection details; verify the API hostname too.
- GitHub `main` is at `c1c0691ba9dbef629a7ab0af89a083ceea8b437f`. The local checkout has two local commits and uncommitted edits based on its previous remote ref; reconcile it selectively before publishing local work.

## Account-owner actions required

These steps require access to the user's Firebase, Supabase, or Coolify accounts; do not share secrets in chat.

1. **Bootstrap CMS access:** in Firebase Console → EnerTech Ups → Authentication → Users, copy the UID for the exact account used at `cms.enertechups.cloud`. In Coolify, set `BOOTSTRAP_SUPER_ADMIN_UIDS` to that UID (comma-separated only if needed), save, and redeploy the API. In CMS → Admin access, create/verify that UID as an active `super_admin`, then remove the temporary UID from Coolify and redeploy the API. Never share service-account or database secrets in chat.
2. **Verify Google sign-in live:** the current bundled Firebase configuration contains the current APK's release SHA-1, but the project owner must confirm Google and Email/Password providers are enabled, the web client ID is configured, and the release APK can complete sign-in on a real device.
3. **Confirm secure domain access:** open `https://cms.enertechups.cloud` and `https://api.enertechups.cloud` directly. If either still shows a browser security warning, inspect its certificate details and Coolify domain mapping before accepting production traffic.

## Priority 0 — Security and data correctness

- [x] Remove browser-side Supabase service-role access and route CMS operations only through the authenticated API.
- [x] Require the API to verify an active admin role before showing the CMS; never infer admin access from Firebase sign-in alone.
- [ ] Rotate/revoke the service-role key that was committed in the former CMS bundle. Removing it from source does not invalidate copies in existing builds, browser caches, or Git history.
- [ ] Rotate/revoke the previously committed chat-widget key as well. Treat any key sent to the app as public and replace a private provider key with a provider-designated embed key.
- [x] Make the catalogue response schema accept the same maximum page size as the API and CMS (`limit=500`).
- [x] Treat a successful empty catalogue response as authoritative so an old on-device cache cannot resurrect unpublished/deleted catalogue items.
- [x] Scope customer profile caches by Firebase UID, clear stale cached profiles after an authoritative empty response, and require API confirmation before marking onboarding/profile edits saved.
- [x] Stop treating failed quote/service POSTs as successful local submissions; only API-confirmed requests appear in My Requests, preventing cross-account offline-request leakage.
- [x] Preserve deliberately cleared values and empty arrays when CMS product drafts are returned.
- [x] Avoid returning exception details and internal configuration in generic API 500 responses.
- [x] Avoid returning database connection exception details in API 503 responses; return a retryable generic message while retaining server-side logs.
- [x] Keep Supabase Storage uploads asynchronous so a slow media request does not block the API event loop.
- [x] Ignore stale CMS role-verification responses after a Firebase account changes; abort the previous check before accepting another account's role.
- [x] Treat bootstrap-super-admin UIDs as initial access only; once an admin record exists, stored roles and deactivation control access.
- [x] Keep the CMS container port internal so public requests enter through Coolify's HTTPS proxy instead of bypassing it on port 3000.
- [x] Validate featured collection/product references when publishing Home content.
- [x] Keep featured-product publishing consistent across catalogue pagination: limit CMS selections to the API's 12-item schema and let the app fetch selected, published IDs directly, even when those products fall beyond the first catalogue page.
- [x] Remove the fixed demo customer credentials and offline-auth bypass from the app entry screen.
- [x] Remove the duplicate account-tab sign-in/sign-up form so all customer authentication goes through the verified-email entry flow.
- [x] Remove embedded Firebase defaults from app and CMS clients and remove the app's emulator API fallback; missing configuration now blocks account access instead of silently using fallback settings.
- [x] Require a verified customer email before onboarding and add resend/check-verification actions.
- [x] Put common profile fields before business-only company/GST fields, improve sign-in autofill/keyboard actions, and validate phone/GST data in both the app and API.
- [x] Keep sign-in and onboarding forms within readable widths, give each input a visible label and purpose-specific keyboard, and place business fields after role selection only for reseller/EPC/distributor accounts; apply the same role-dependent order in profile editing and hide business data rows from end-user account summaries.
- [x] Remove the hard-coded Google OAuth client ID fallback; Google sign-in now requires the app build's configured client ID.
- [x] Reject local or non-HTTPS API endpoints when building a release APK.
- [x] Replace fabricated dashboard totals, fake time-series charts, and hard-coded "connected" integration badges with explicit live snapshot counts and setup guidance.
- [x] Make product stock status honest when the source has not provided availability; both CMS views distinguish unknown, out-of-stock, in-stock, and backorder.
- [x] Remove an invented 22% MRP calculation and a static "Default Sales Channel" label from product listings; show source, published price, and reported stock instead.
- [x] Add product/collection image upload, product gallery URLs, multiple document editing, and stock quantity input to the CMS.
- [x] Use sized Next.js image components for CMS product previews and replace decorative emoji with accessible SVG icons.
- [x] Test customer-request owner scoping, content-editor restrictions, closed-request transitions, media size limits, and contact-inquiry limits keyed by Firebase UID against isolated SQLite.
- [x] Rate-limit quote and service submissions together to ten per verified Firebase account per hour; index customer UID plus request creation time and test the cross-endpoint cap.
- [ ] Verify Firebase token revocation and execute/rollback schema migrations against staging Supabase; verify live storage policies and role boundaries there.
- [x] Register the current APK signer SHA-1 in Firebase and refresh the bundled Google services configuration; the current config fingerprint matches the verified APK signer. Live Google sign-in still needs device verification.

## Priority 1 — Core CMS content workflows

- [x] Replace manual UUID entry for featured collections/products with published-item selectors.
- [x] Add the approved source reference, category, and sort order fields to the knowledge editor; publishing otherwise always failed for new answers.
- [x] Add image upload and preview controls to product and collection editors, plus gallery and multiple-document editing.
- [x] Add contact-inquiry triage to the CMS with search, status updates, internal notes, and audit history.
- [x] Build a customer contact form and connect it to the CMS queue; require verified sign-in, use the verified account email, validate phone/type, and cap submissions at five per hour per Firebase UID. Migration backfills older rows from their audit events; a case-insensitive email fallback covers unmatched legacy rows.
- [x] Add Alembic migrations for contact inquiry storage and its customer UID lookup index; keep old records nullable and rate-limit new inquiries by stable Firebase UID.
- [x] Add collection-aware Home navigation so choosing a featured collection opens that collection in the catalogue.
- [x] Add explicit publish/unpublish actions to app content, products, collections, and support articles where the role/API permits.
- [x] Add a readable per-field draft-versus-published comparison to app-content, product, and collection editors; catalogue APIs expose current published columns alongside the editable draft.
- [x] Add server-side catalogue search and load-more pagination for products and collections, including the CMS selectors.
- [x] Add pagination for customer, quote/service request, knowledge, and audit queues; customer, request, knowledge, audit, and contact enquiry views now expose load-more controls backed by offset APIs.
- [x] Add audit search, entity-type filtering, stable ordering, and CSV export for loaded filtered rows.
- [ ] Confirm WooCommerce field mappings against the live store; the implementation is configurable, but this workspace has no live credentials or verified field mapping.

## Priority 1 — CMS-to-app content parity

- [x] Load the CMS-approved HTTPS chat embed URL inside the customer app, preserve direct contacts when enabled, consume welcome/fallback/handoff settings, and restrict embed/handoff links to server-allowlisted HTTPS hosts. The provider script/key protocol still needs its exact integration contract.
- [x] Remove hard-coded company phone/email values from app screens; contact data comes from the published CMS configuration.
- [x] Connect published product document links to a searchable mobile information library; private media/manual access control is still open.
- [ ] Decide and implement notification behavior; the former home bell now opens My Requests, and there is no notification backend.
- [x] Remove the unimplemented equipment-registration entry point and the incorrectly categorized warranty/AMC link; the current document model cannot verify coverage type.
- [ ] Implement registered-equipment ownership, warranty/AMC coverage, and service-history workflows after the business rules and source of truth are confirmed.
- [x] Wire the contact-inquiry API to the customer support form and admin queue with verified-account and database-backed rate limits; quote and service requests also share a database-backed ten-per-hour account cap.
- [x] Confirm every editable Home/Solution Finder/Contact/Brand/FAQ field is visible in the app and document unsupported fields; Home search/intent copy and Brand support icon are now connected, while provider-specific chat scripting remains external.
- [x] Trace the current CMS app-content fields against their mobile consumers; the concrete gaps are listed below.

## Priority 2 — Operational and product completeness

- [ ] Define account invitation/deactivation, customer deletion/retention, data export, privacy, and audit-retention policies.
- [ ] Implement secure customer attachments for service requests: the app's “Add photos or video” control is currently disabled and disclosed as unavailable. Agree accepted types, size/count limits, privacy, retention, and CMS access; upload through an authenticated API to private storage and expose attachments only to the request owner and authorized staff.
- [ ] Model registered equipment, ownership verification, warranty/AMC, service history, and notification delivery after the business rules and source of truth are confirmed.
- [ ] Add a CMS-managed public/private manual library with authorization rules for private files.
- [x] Add request text/status filters, assignment options limited to active CMS administrators, and backend-enforced status transitions.
- [ ] Build complete RFQ-to-quotation workflow including quote creation, revisions, documents, customer review, and acceptance.
- [ ] Review mobile accessibility, 375px/landscape/tablet layouts, dynamic type, offline/error states, and keyboard/screen-reader flows.
- [ ] Review CMS responsive behavior, keyboard navigation, focus handling, and form validation at narrow and wide viewports.

## Priority 3 — Release readiness

- [x] Keep the Coolify variable template lean: require only API/CMS runtime and public build configuration, put standard WooCommerce routes/field mappings and the public media bucket in code defaults, and document WordPress/chat variables as feature-optional.
- [ ] Replace temporary Coolify `sslip.io` HTTP domains with HTTPS domains before production; rebuild the CMS with `ALLOW_HTTP_TEST_API=false` and configure the production API URL in the customer app.
- [ ] Resolve the browser's `Not secure` warning for `cms.enertechups.cloud` and verify the API domain certificate as well.
- [ ] Configure real Firebase/Supabase/WordPress environments and validate secrets only in server-side deployment settings.
- [x] Run CMS lint/typecheck, Flutter analyze, and Python syntax compilation for the source changes.
- [ ] Execute/rollback migrations against staging Supabase, rerun the CMS production build after the final deployment configuration, and verify Flutter widgets on a configured device. Current local backend tests (23), CMS lint/typecheck, earlier Flutter analysis/tests, and APK signature verification pass.
- [ ] Complete live staging journeys: admin draft/publish → mobile update; quote/service submission → CMS assignment/status → customer tracking; upload → display; WooCommerce sync → published collection/product.
- [ ] Configure domain/TLS, backups/restore, monitoring, release signing, privacy/support policies, and rollback ownership.
- [ ] Install the current signed APK on a device, exercise Firebase sign-in and all app workflows against the production HTTPS API, then publish the matching source revision and artifact. The signature and Android Firebase fingerprint now match, but the APK is not device- or live-API-verified.

## Confirmed implementation defects

1. CMS used a committed Supabase service-role key in browser code and silently bypassed the API/RBAC when the API failed.
2. CMS auth granted the `admin` UI role when the API session check failed or was skipped for localhost.
3. CMS requested 300 products while the shared response schema rejected `limit > 100`; fallback behavior masked the API failure.
4. Successful empty catalogue fetches fell back to cached products/categories, so unpublished content could remain visible on devices.
5. CMS could save FAQ drafts but could not enter the source reference required by the publish API.
6. Home featured-item configuration was a free-text UUID list; category/product selectors are now implemented.
7. Draft API responses used truthy fallback logic, making cleared product fields appear unchanged in the CMS.
8. Generic API errors returned raw exception messages to clients.
9. Registered-equipment and warranty/AMC entry points implied unsupported workflows and, for warranty, showed generic product documents; those links have been removed until records and document types are modeled. The CMS chat URL now opens in-app, but provider-specific scripting and human handoff are not configured.
10. The app's demo sign-in used fixed credentials and enabled an offline bypass when Firebase failed; the duplicate account-tab auth path also skipped email verification. These paths have been removed.
11. CMS analytics and integration status presented fabricated historical counts and connectivity; these have been removed and replaced with accurate snapshots/setup notes.
12. The former chat key in the Coolify environment example was non-empty and was sent to public clients. The template now uses a blank public-embed-key name; revoke the previous value.
13. Missing app configuration previously fell back to embedded Firebase details and an emulator API URL; those defaults have been removed and release builds reject local/non-HTTPS API URLs.
14. Sign-up did not gate onboarding on verified email, and profile edit accepted weak phone/GST values; these checks now align across account setup, profile edit, and API validation.
15. Google sign-in fell back to a hard-coded OAuth client ID when build configuration was missing; it now reports an explicit configuration error.
16. The CMS Docker/build configuration silently substituted a fixed Firebase project and localhost API URL; it now requires deployment values, requires HTTPS for production, and permits HTTP only for an explicitly enabled `.sslip.io` CMS test build. The CMS blocks sign-in when Firebase web configuration is absent.
17. The public contact-inquiry endpoint accepted unauthenticated submissions without a rate limit and had no customer form or CMS triage; it now requires a verified Firebase account, rate-limits by stable Firebase UID, and provides an audited admin queue.
18. CMS product views treated every non-`instock` value as out of stock and fabricated an MRP by multiplying the source price; they now show the four actual stock states, source quantity, and only the published price.
19. The Support shortcut said service tracking was unavailable even though My Requests existed, and the manual library search was disabled despite published product documents being available; both now route to working app data/screens.
20. CMS product/collection/knowledge/app-content APIs supported unpublishing but most editors exposed no action; role-appropriate unpublish controls are now present.
21. Profile and quote/service request repositories marked local-only data as saved/submitted after API errors, and request fallbacks were shared across accounts; profile saves now wait for API confirmation and failed requests surface retryable errors without entering another account's request list.
22. Contact inquiries had a SQLAlchemy model and API routes but no Alembic migration, so a clean deployment would fail on submission; migrations now create the table/indexes and add an optional Firebase UID. Existing UIDs are backfilled from audit events where possible. Rate limiting follows the stable account UID, so changing the account email cannot bypass the per-account cap; unmatched legacy rows still use a case-insensitive email fallback.
23. CMS catalogue pages loaded only the first fixed-size batch and collections were not searched server-side; product/collection search and load-more controls now use the existing API pagination.
24. Customer, quote/service, knowledge, and audit CMS views stopped at the first API page; load-more controls now expose subsequent results without hiding already loaded rows during requests.
25. Customer table displayed selection checkboxes with no bulk actions; those inert controls are removed so the table no longer implies unsupported operations.
26. App-content editors showed publication revisions but no field-level view of what was pending; they now compare draft and published values before publish.
27. Request triage lacked filtering and active-staff assignment controls, and the API accepted out-of-sequence statuses or arbitrary assignee UIDs; triage now filters by search/status, assigns only active administrators, and validates transitions server-side.
28. Audit history had pagination but no search/entity filters or export; it now supports those filters and exports only the currently loaded rows with CSV formula-injection escaping.
29. A deliberately cleared nullable product price was replaced by the previous published price in CMS API responses; draft response mapping now honors an explicit `null` and product/collection editors compare draft values to the published snapshot.
30. Offline catalogue filtering compared a category slug to each product's category UUID, so a cached category could appear empty; the repository now resolves the cached slug to its ID before filtering.
31. Rapid catalogue searches could complete out of order and overwrite newer results, and leaving a featured category could preserve that filter; product loads now ignore stale responses and generic catalogue navigation clears the prior category.
32. Google sign-in surfaced Firebase's raw package-certificate-hash failure text. The app now gives a recovery message and explicit Firebase Console steps; the release SHA still must be added by a Firebase administrator.

## Customer app specification parity

The supplied UI/UX blueprint lists these customer journeys. Current source status:

| Journey | Source status |
|---|---|
| Home, product browse/search, collection filter, product details | Implemented; homepage collection taps now apply the correct filter |
| Solution Finder, quote submit, request list, service request | Implemented with API-backed quote/service request records |
| Account profile and Firebase onboarding | Implemented; fixed demo bypass removed |
| Support contacts, FAQs, hosted support URL, contact enquiry | Contact/FAQ CMS content is consumed; verified customers can submit a contact message; admins can search, update status, and add internal notes |
| Product comparison and requirement basket | Source implementation now supports a session-scoped list of up to four products, side-by-side published specifications, removal, and prefilled quote enquiries; persistence and device QA remain open |
| Quotation document/detail and customer acceptance | Not implemented; quote records stop at inquiry/status |
| Service request detail timeline and confirmed appointment | Partial; status/note tracking exists, no timeline/appointment model |
| Human agent handoff | CMS allowlisted HTTPS handoff action is wired; live provider script/key and agent availability still need staging validation |
| Registered equipment, warranty/AMC, service history | Not available in the app until verified record models and workflows exist; misleading entry points removed |
| Manual/document library search | Searchable published product documents are connected; no CMS-managed private manuals/coverage records exist |
| Addresses, notifications, settings/consent/privacy | Not implemented |

The supplied CMS specification also calls for enquiry/quote/service queues, assignment, activity history, manuals, notifications, audit filtering/export, and paginated search. Current CMS has searchable, filterable request triage with active-staff assignment, inquiry intake, searchable/entity-filtered audit history with CSV export for loaded rows, and paginated lists, but lacks full quote issue/revision, request activity timelines, document management, and notification delivery.

CMS app-content parity checked from source:

- Home search prompt, intent-card copy, hero copy/CTA, announcement fields, section visibility/order, featured products, and featured collections are consumed. The CMS limits featured selectors to the 12 IDs accepted by the API; the app resolves selected product IDs directly, and the CMS Home selector now loads additional catalogue pages when needed.
- Contact phone, WhatsApp, emails, address, support hours, and availability text are consumed by the support/contact screens.
- Solution Finder options, step titles, and both helper prompts are consumed.
- Brand display name and logo are consumed; `support_icon_url` is now displayed in the support header.
- Chat enablement, embed URL, welcome/fallback messages, and allowlisted human handoff are consumed. The hosted widget provider script/key contract remains unverified.
- Knowledge answers are consumed from the public knowledge endpoint. Product document URLs are searchable in the information library, but are public HTTPS links without private-file authorization.

## Verification notes

- This document records source-level findings. No live service behavior can be confirmed without the external project credentials and source mappings.
- Visual/device QA remains open. The UI/UX Pro Max search returned guidance for visible labels, correct input types, password-manager support, and confirmation feedback; small-screen, landscape, dynamic-text, contrast, touch-target, and keyboard-focus checks still need rendered device/browser review.
- Latest local checks: CMS ESLint, TypeScript `--noEmit`, and production build pass after the catalogue selector and icon/touch-target fixes. All 23 backend tests pass. Python compilation and Alembic offline SQL were previously verified through `c42e17b3d906`; no production/staging database migration was executed. Flutter analysis and six widget/unit tests passed in the earlier configured environment, but could not be repeated in this shell because the Flutter SDK is unavailable. No Android device is connected. The local APK signature and embedded build configuration were verified, but end-to-end Firebase/API behavior is not verified.

