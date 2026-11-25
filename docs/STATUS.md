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
- Backend: 23 pytest checks passed in an earlier configured environment. A migration-safe fix for the pre-existing Supabase `contact_inquiries` table was pushed as `c1c0691ba9dbef629a7ab0af89a083ceea8b437f`; production schema migration completion and API readiness still need live confirmation.
- CMS: ESLint (zero warnings/errors) and TypeScript `--noEmit` passed in the current workspace. A production build passed earlier with placeholder public Firebase/API values; that does not verify live services.
- Mobile: Flutter analysis and all six Flutter tests passed in the current workspace. No Android device is connected, so sign-in and API workflows are not device-verified.
- Android: the current root `update.apk` is 63,615,191 bytes, matches `apps/mobile/build/app/outputs/flutter-apk/app-release.apk`, and was built at 2026-11-25 10:58 local time. `apksigner` verifies its v2 signature; signer SHA-1 is `78:EE:94:85:3B:3F:86:21:74:9C:51:3D:9F:02:31:E6:B1:58:09:37`. The bundled Firebase config targets `enertech-ups`, package `com.enertech.enertech_customer`, and contains the same Android SHA-1. Device installation, live API calls, and actual Google sign-in are still unverified.
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

The local CMS catalogue screen surfaces collection-fetch failures, ignores stale responses, and pages through products/collections for Home featured selectors. GitHub `main` is at `c1c0691ba9dbef629a7ab0af89a083ceea8b437f`; the local checkout has two local commits and uncommitted edits based on its previous remote ref, so reconcile it selectively before pushing. Production database migration completion, first CMS super-admin provisioning, device workflows, and live WooCommerce mappings remain unverified.

