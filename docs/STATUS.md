# Build status

Updated 2026-11-25. The project contains the customer app, CMS, API, and Coolify deployment configuration. Production acceptance is not complete. After the database URL was updated and the duplicate-table migration was fixed, the current CMS page reports **CMS access not granted**. The signed-in Firebase account still needs an active `admin_accounts` role or temporary inclusion in Coolify's `BOOTSTRAP_SUPER_ADMIN_UIDS`.

## Implemented in the workspace

- Firebase-first app onboarding with email/password or Google sign-in, email verification, End User/Reseller/EPC/Distributor selection, and profile fields saved to the API.
- Shared CMS/API/app content for home, contact details, app branding, hosted chat, FAQs, products, categories, and quote/service requests. Published changes are read by the mobile app.
- Firebase-authorized CMS roles, customer directory, request triage, super-admin account administration, audit history, and draft/publish flows.
- Supabase Storage upload route for public PNG/JPEG/WebP app assets; images are validated, limited to 10 MB, and uploaded with the API-only service key.
- WooCommerce pull sync for products, categories, Store API prices/stock, images, specifications, and public PDF links. WooCommerce-owned records are read-only in CMS and publish to the app during sync.
- Chat widget assembly from the supplied hosted script: the CMS stores the enabled app URL/config; the API reads the widget script URL and key from its server environment and only returns the widget configuration with enabled, published chat settings.
- Coolify Compose configuration for API and CMS, with local and deployment environment templates. The customer-facing clients contain no database or service-role credentials.

## Verification status — 2026-11-25

- Alembic previously upgraded local PostgreSQL through `e21a7c0d9f43`; offline SQL compiles through `c42e17b3d906`. New migrations have not been applied to staging/production.
- Backend: earlier pytest checks passed before this audit. Current Python syntax compilation passes for the WordPress importer and affected tests, but the workstation has no FastAPI/pytest modules so the latest backend tests remain unrun. The production schema migration completion and API readiness still need live confirmation.
- CMS: ESLint (zero warnings/errors) and TypeScript `--noEmit` passed in the current workspace. A production build passed earlier with placeholder public Firebase/API values; that does not verify live services.
- Mobile: Flutter analysis and tests passed in the current workspace. Device `Y5XCTWHIBEE6VKFM` is connected; sign-in and live API workflows are not device-verified.
- Android: root `update.apk` is 65,080,051 bytes, signed, version `0.1.2` code 3, package `com.enertech.enertech_customer`, app label `ENERTECH`. It was reinstalled on the connected device and Android accepted its launch intent. This was the existing artifact; no new APK was built during the latest CMS-only changes.
- Coolify/CMS: the latest observed page returns an authorization denial, not the earlier connection-verification error. Bootstrap the exact Firebase UID used to sign in, create an active `super_admin` record in CMS, then remove the temporary bootstrap UID. Verify explicit HTTPS access and certificate trust for CMS and API before launch.

## Required before live acceptance

- Confirm that Coolify's Firebase project ID and service-account JSON match `enertech-ups` used by the APK and CMS; confirm Email/Password and Google providers are enabled and `cms.enertechups.cloud` is an authorized domain. Exercise sign-in on a device.
- Verify Supabase's session-pooler connection string, project URL, server-only service-role key, SSL requirement, and public `enertech-public` media bucket in Coolify.
- Add the read-only WooCommerce consumer key and secret in the API environment. Then verify the WooCommerce REST, Store API, categories, and PDF media responses with the live site.
- Enter and publish the hosted-chat app URL in CMS. The local API environment has the widget source/host configuration; Coolify also needs the widget key as a server variable.
- Upload the approved EnerTech logo through CMS after Supabase Storage is configured.
- Configure domain/TLS, backups and restore, data privacy/retention, request handling policies, release signing, and staging acceptance.

## Still to build or decide

- Registered equipment, warranty/AMC, service-history workflows, customer file attachments, a CMS-managed manual/document library, and app notifications.
- WordPress media that is linked by category rather than attached to a product needs the site's exact media metadata/mapping to validate.
- Full role/invitation lifecycle, account deletion/retention workflows, and audit export.
- Verify the completed Supabase migration and API readiness; bootstrap the first CMS super-admin as described above, then verify CMS role access and a successful deployment.
- Install and exercise the current APK on a device against that live API, then publish the tested source revision and distribute the matching artifact.

The local CMS catalogue screen surfaces collection-fetch failures, ignores stale responses, and pages through products/collections for Home featured selectors. GitHub `main` is at `44a2d0c6ec31b611993f47283260e6cd47f1b8e6`; local `main` is at `417c97c` with substantial uncommitted edits. The GitHub connector reports 103 commits from local `origin/main` `a190971` to GitHub `main`; normal `git fetch` cannot authenticate on this workstation. Reconcile targeted changes against current remote files before publishing. Production database migration completion, first CMS super-admin provisioning, device workflows, and live WooCommerce mappings remain unverified.
