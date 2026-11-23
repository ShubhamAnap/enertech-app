# Deployment and local runtime

## Local development

Local API/admin scripts are under `infra/local/`; PostgreSQL runs on `127.0.0.1:55432`. Keep API runtime secrets in the ignored `backend/.env`. CMS public Firebase/API values belong in `apps/admin/.env.local`. The Android emulator API URL is `http://10.0.2.2:8000/api/v1`.

Apply schema updates from `backend/`:

```powershell
..\.venv\Scripts\python.exe -m alembic upgrade head
```

The Android build reads `apps/mobile/.env`; it may contain public Firebase client configuration and the public API URL only. Do not place database URLs, Firebase Admin service-account data, Supabase service keys, WooCommerce credentials, or private provider secrets in the mobile or CMS browser environment.

## Coolify on Hostinger

`infra/coolify/compose.yaml` builds the API and CMS. PostgreSQL/Supabase is external; API startup applies Alembic migrations.

Configure server runtime secrets in Coolify:

- Supabase: `SUPABASE_DATABASE_URL` with TLS, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_PUBLIC_MEDIA_BUCKET` (create a public `enertech-public` bucket for app images).
- Firebase server: `FIREBASE_PROJECT_ID`, `FIREBASE_SERVICE_ACCOUNT_JSON`, and `BOOTSTRAP_SUPER_ADMIN_UIDS` for the first super-admin.
- API: `API_CORS_ORIGINS` with the exact CMS origin.
- WooCommerce server: `WORDPRESS_API_BASE_URL=https://enertechups.com/wp-json`, read-only `WORDPRESS_CONSUMER_KEY` and `WORDPRESS_CONSUMER_SECRET`, and the routes/mappings in `infra/coolify/.env.example`.
- Chat widget server: `CHAT_ALLOWED_HOSTS`, `CHAT_WIDGET_SCRIPT_URL`, and `CHAT_PROVIDER_API_KEY`. The hosted widget key is returned by the published app-config endpoint only while chat is enabled and published.

The CMS image build requires the public build values `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_FIREBASE_API_KEY`, `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN`, `NEXT_PUBLIC_FIREBASE_PROJECT_ID`, `NEXT_PUBLIC_FIREBASE_APP_ID`, and `NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID`. Changing these values requires rebuilding the CMS image. They are not server credentials.

Use Supabase backups and verify a restore before production. Configure the CMS domain/TLS, firewall, monitoring, retention, and rollback process in Coolify before launch.

## Android package

After Firebase and the production API URL are configured in ignored `apps/mobile/.env`, run from the workspace root:

```powershell
infra\build-mobile.ps1
```

Output: `apps/mobile/build/app/outputs/flutter-apk/app-debug.apk`. The script stops if required public Firebase/API values are missing or server-only values appear in the mobile environment. The debug build is for testing; production release signing and package identity still need EnerTech-owned decisions.

## Current gate

Firebase and Supabase projects and WooCommerce credentials are not ready, so no live sync, production CMS image, or current APK has been produced. No code has been pushed to GitHub and no Coolify deployment has been made. Configure the values above before creating a staging deployment and verify sign-in, role boundaries, CMS publishing, product sync, widget loading, customer request ownership, backup, and rollback there.
