# EnerTech Customer Platform

The workspace contains a Flutter customer app, a Next.js CMS, and one FastAPI service. Both clients use the API; only the API connects to PostgreSQL/Supabase. Product and app-content updates are staged in the CMS and become visible in the app after publication.

## Built in this workspace

- `apps/mobile/`: Android customer app with published catalogue and product detail reads, Firebase email/password registration/sign-in/reset, quote enquiry submission, service request submission, request tracking, CMS-managed home/contact/brand/chat settings, and an allowlisted hosted-chat web view.
- `apps/admin/`: responsive Firebase-authenticated CMS with product and category draft/publish workflows, homepage/contact/brand/chat editors, WordPress product preview/import as drafts, and administrator request triage/status updates.
- `backend/`: FastAPI, SQLAlchemy, Alembic, Firebase Admin token and role checks, published-only app/catalogue reads, CMS CRUD, audit events, WordPress REST integration, and customer-owned request APIs.
- `infra/coolify/compose.yaml`: deployment-ready API and CMS services for Coolify, using Supabase as the external database.
- Supplied reference screenshots are saved in the adjacent source/reference pack. Screenshots are design references only, not EnerTech product or company data.

## Local development

1. Copy `backend/.env.example` to `backend/.env` and keep secrets there. The existing local `.env` is ignored.
2. Copy `apps/admin/.env.example` to `apps/admin/.env.local`; the local API URL is already present. Firebase client values are blank until a Firebase project is created.
3. `apps/mobile/.env.example` documents public Firebase values. The ignored local `apps/mobile/.env` is present for the Android build; fill it after creating Firebase. Do not put service-account JSON or database credentials in a client env file.
4. Start the local PostgreSQL service with `infra/local/start-postgres.ps1`, then run `..\.venv\Scripts\python.exe -m alembic upgrade head` from `backend/`.
5. Run `infra/local/run-backend.ps1` and `infra/local/run-admin.ps1` in separate terminals. The mobile launcher uses `http://10.0.2.2:8000/api/v1` for the Android emulator.

With no Firebase project, the CMS sign-in page and customer account screen explain what is missing. No product/customer seed data is created.

## Build and verification

- Backend from `backend/`: `..\.venv\Scripts\python.exe -m pytest`.
- Admin from `apps/admin/`: `npm run lint`; `npm run build` verifies public Firebase/API values and stops if they are missing.
- Mobile: run `infra/build-mobile.ps1`; it verifies Firebase/API values and rejects server-only keys before building the debug APK. Flutter `analyze` can run without project credentials.

## External setup still required

- Create Supabase and Firebase projects, set production secrets, and authorize at least one admin Firebase UID.
- Supply the exact WordPress URL, whether products are WooCommerce or a custom post type, REST route, field mappings, and read-only credentials.
- Supply the chatbot embed snippet or hosted-widget URL and its trusted host. The API accepts only an HTTPS embed URL from `CHAT_ALLOWED_HOSTS`; it never stores or runs raw script text.
- Supply an approved EnerTech logo asset/URL. No standalone logo file was present in the supplied workspace.
- Confirm company service/quote policies, data retention/privacy text, release signing, domain/TLS, and backup/restore ownership before a production launch.

See `docs/STATUS.md` and `docs/MASTER_AUDIT_PLAN.md` for implemented scope and remaining work. The source has been published to GitHub `main`; a live Coolify deployment and production APK still require the external Firebase, Supabase, domain, and signing configuration described in `docs/DEPLOYMENT.md`.
