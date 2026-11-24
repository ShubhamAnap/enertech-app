# Build status

Updated 2026-11-24. The project contains the customer app, CMS, API, and Coolify deployment configuration. Source is published to GitHub `main`; live Firebase, Supabase, and WooCommerce behavior is not yet verified.

## Implemented in the workspace

- Firebase-first app onboarding with email/password or Google sign-in, email verification, End User/Reseller/EPC/Distributor selection, and profile fields saved to the API.
- Shared CMS/API/app content for home, contact details, app branding, hosted chat, FAQs, products, categories, and quote/service requests. Published changes are read by the mobile app.
- Firebase-authorized CMS roles, customer directory, request triage, super-admin account administration, audit history, and draft/publish flows.
- Supabase Storage upload route for public PNG/JPEG/WebP app assets; images are validated, limited to 10 MB, and uploaded with the API-only service key.
- WooCommerce pull sync for products, categories, Store API prices/stock, images, specifications, and public PDF links. WooCommerce-owned records are read-only in CMS and publish to the app during sync.
- Chat widget assembly from the supplied hosted script: the CMS stores the enabled app URL/config; the API reads the widget script URL and key from its server environment and only returns the widget configuration with enabled, published chat settings.
- Coolify Compose configuration for API and CMS, with local and deployment environment templates. The customer-facing clients contain no database or service-role credentials.

## Verification completed

- Alembic upgraded the local PostgreSQL schema to `e21a7c0d9f43`.
- Backend: 23 pytest checks pass, including bootstrap-admin revocation, database-error redaction, async upload/size checks, request ownership, authorization, contact-inquiry and quote/service rate limits by stable Firebase UID, selected-product ID filtering, WooCommerce defaults/read-only safeguards, delete-reference safeguards, and state-transition checks; Python compilation passes. Alembic offline SQL compiles through `c42e17b3d906`.
- CMS: ESLint reports zero errors or warnings; TypeScript `--noEmit` and a Next.js production-mode build pass with test values.
- Mobile: Flutter analysis reports no issues and all 6 widget/unit tests pass.
- No live-configured CMS image or production APK was produced because the deployment Firebase/API values and production signing key are not configured.

## Required before live acceptance

- Create Firebase and Supabase projects. Configure the Firebase web/client values, Firebase Admin service account, first super-admin UID, Supabase PostgreSQL URL, Supabase project URL/service-role key, and public asset bucket in local ignored `.env` files or Coolify secrets.
- Add the read-only WooCommerce consumer key and secret in the API environment. Then verify the WooCommerce REST, Store API, categories, and PDF media responses with the live site.
- Enter and publish the hosted-chat app URL in CMS. The local API environment has the widget source/host configuration; Coolify also needs the widget key as a server variable.
- Upload the approved EnerTech logo through CMS after Supabase Storage is configured.
- Configure domain/TLS, backups and restore, data privacy/retention, request handling policies, release signing, and staging acceptance.

## Still to build or decide

- Registered equipment, warranty/AMC, service-history workflows, customer file attachments, a CMS-managed manual/document library, and app notifications.
- WordPress media that is linked by category rather than attached to a product needs the site's exact media metadata/mapping to validate.
- Full role/invitation lifecycle, account deletion/retention workflows, and audit export.
- Live end-to-end verification, Coolify deployment, and Android APK rebuild.

No live Coolify deployment or production APK has been verified. The workspace has no access to the production Supabase data or live WooCommerce sync credentials, so these external workflows still need staging validation.
