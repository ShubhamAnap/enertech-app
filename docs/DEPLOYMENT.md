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
- Chat widget server: `CHAT_ALLOWED_HOSTS`, `CHAT_WIDGET_SCRIPT_URL`, and `CHAT_WIDGET_PUBLIC_KEY`. Only use a provider-designated public embed key here; the app-config endpoint returns it to app clients while chat is enabled and published. Never configure a private/server API key.

The CMS image build requires the public build values `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_FIREBASE_API_KEY`, `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN`, `NEXT_PUBLIC_FIREBASE_PROJECT_ID`, `NEXT_PUBLIC_FIREBASE_APP_ID`, and `NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID`. Production builds require an HTTPS API URL. For temporary Coolify `sslip.io` testing only, set `ALLOW_HTTP_TEST_API=true`; this permits HTTP only when the API hostname ends in `.sslip.io`. Leave it false for production. Coolify-generated `sslip.io` URLs use HTTP, so this test deployment cannot be used for a production APK. Changing these values requires rebuilding the CMS image. They are not server credentials.

Use Supabase backups and verify a restore before production. Configure the CMS domain/TLS, firewall, monitoring, retention, and rollback process in Coolify before launch.

## Android package

After Firebase and the production API URL are configured in ignored `apps/mobile/.env`, run from the workspace root. Set `API_BASE_URL` to the Coolify API service's public HTTPS domain followed by `/api/v1` (for example, `https://api.example.com/api/v1`; replace the example with the real API domain). You can find the domain in Coolify under the EnerTech API service's Domains settings and confirm the host with `/health/ready`.

The mobile `.env` also requires `GOOGLE_SERVER_CLIENT_ID` for Google sign-in. Enable Google as a Firebase Authentication provider, then use the Web OAuth client ID configured for that Firebase project (Firebase Console → Authentication → Google provider, or the matching Web client under Google Cloud Console → APIs & Services → Credentials). Do not use the Android OAuth client ID for this value.

Release builds also require the existing production upload/release keystore. Set `ANDROID_KEYSTORE_PATH`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, and `ANDROID_KEY_PASSWORD` in the build environment; keep passwords out of mobile `.env` and source control. Use the same signing identity as the app already distributed to customers. The build stops if the endpoint is local or HTTPS configuration/signing values are missing.

Run from the workspace root:

```powershell
infra\build-mobile.ps1
```

Output: `update.apk` at the workspace root (copied from `apps/mobile/build/app/outputs/flutter-apk/app-release.apk`). The script stops if required public Firebase/API values are missing, the API URL is not HTTPS, or server-only values appear in the mobile environment. Before distribution, confirm `com.enertech.enertech_customer` matches the package ID of the app already distributed to customers and use that app's existing signing key.

## Current gate

Source code has been pushed to GitHub `main`; no Coolify deployment, production CMS image, or current APK has been produced. Configure Firebase, Supabase, the Coolify domains and secrets, and optional WooCommerce credentials before creating a staging deployment. Verify sign-in, role boundaries, CMS publishing, product sync, widget loading, customer request ownership, backup, and rollback there.

