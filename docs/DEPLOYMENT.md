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

- Supabase: `SUPABASE_DATABASE_URL` with TLS, `SUPABASE_URL`, and `SUPABASE_SERVICE_ROLE_KEY`. Create a public `enertech-public` bucket for app images; the API uses that bucket name by default, so no bucket-name variable is needed.
- Firebase server: `FIREBASE_PROJECT_ID`, runtime-only `FIREBASE_SERVICE_ACCOUNT_JSON`, and `BOOTSTRAP_SUPER_ADMIN_UIDS` for first login. The service-account JSON is not needed to build either image; API readiness remains unhealthy in production until the Firebase project ID and service credential are present at runtime. After signing in, create the same UID as an active `super_admin` in CMS → Admin access, then remove it from `BOOTSTRAP_SUPER_ADMIN_UIDS` in Coolify and redeploy the API. Keep at least one active super-admin account.
- API: `API_CORS_ORIGINS` with the exact CMS origin.
- WooCommerce is optional. If you use Import Products, set `WORDPRESS_API_BASE_URL=https://enertechups.com/wp-json` and read-only `WORDPRESS_CONSUMER_KEY` / `WORDPRESS_CONSUMER_SECRET`. The standard WooCommerce routes and field mappings are built-in defaults; add no route or mapping variables unless the store schema differs.
- Chat widget is optional. If enabled, configure `CHAT_ALLOWED_HOSTS`, `CHAT_WIDGET_SCRIPT_URL`, and `CHAT_WIDGET_PUBLIC_KEY`. Only use a provider-designated public embed key here; the app-config endpoint returns it to app clients while chat is enabled and published. Never configure a private/server API key.

The CMS image build requires `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_FIREBASE_API_KEY`, `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN`, `NEXT_PUBLIC_FIREBASE_APP_ID`, and `NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID`. Compose supplies `NEXT_PUBLIC_FIREBASE_PROJECT_ID` from `FIREBASE_PROJECT_ID`; do not create a duplicate project-ID variable. Production builds require an HTTPS API URL. For temporary Coolify `sslip.io` testing only, add `ALLOW_HTTP_TEST_API=true`; omit it in production. These public client values require rebuilding the CMS image and are not server credentials.

Use Supabase backups and verify a restore before production. Configure the CMS domain/TLS, firewall, monitoring, retention, and rollback process in Coolify before launch.

## Android package

After Firebase and the production API URL are configured in ignored `apps/mobile/.env`, run from the workspace root. Set `API_BASE_URL` to the Coolify API service's public HTTPS domain followed by `/api/v1` (for example, `https://api.example.com/api/v1`; replace the example with the real API domain). The readiness route is `/api/v1/health/ready`.

The mobile `.env` also requires `GOOGLE_SERVER_CLIENT_ID` for Google sign-in. Enable Google as a Firebase Authentication provider, then use the Web OAuth client ID configured for that Firebase project (Firebase Console → Authentication → Google provider, or the matching Web client under Google Cloud Console → APIs & Services → Credentials). Do not use the Android OAuth client ID for this value.

The APK release signing certificate SHA-1 must be registered on the Android app in Firebase Project settings → General → Your apps → SHA certificate fingerprints. Download the refreshed `google-services.json` and replace `apps/mobile/android/app/google-services.json` after registering the key. The currently built local APK has SHA-1 `78:EE:94:85:3B:3F:86:21:74:9C:51:3D:9F:02:31:E6:B1:58:09:37`; the bundled file currently has a different fingerprint, so Google sign-in is not release-ready yet.

Release builds also require the existing production upload/release keystore. Set `ANDROID_KEYSTORE_PATH`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, and `ANDROID_KEY_PASSWORD` in the build environment; keep passwords out of mobile `.env` and source control. Use the same signing identity as the app already distributed to customers. The build stops if the endpoint is local or HTTPS configuration/signing values are missing.

Run from the workspace root:

```powershell
infra\build-mobile.ps1
```

Output: `update.apk` at the workspace root (copied from `apps/mobile/build/app/outputs/flutter-apk/app-release.apk`). The script stops if required public Firebase/API values are missing, the API URL is not HTTPS, or server-only values appear in the mobile environment. Before distribution, confirm `com.enertech.enertech_customer` matches the package ID of the app already distributed to customers and use that app's existing signing key.

## Current gate

The latest observed CMS screen reports **CMS access not granted**. The API denies CMS access unless the verified Firebase UID has an active `admin_accounts` record or appears in `BOOTSTRAP_SUPER_ADMIN_UIDS`. To provision the first administrator, copy the signed-in user's UID from Firebase Console → Authentication → Users, set that UID in Coolify, and redeploy the API. Then create an active `super_admin` account in CMS → Admin access, remove the temporary bootstrap UID, and redeploy the API again. A migration-safe patch for the existing Supabase `contact_inquiries` schema was pushed as `c1c0691ba9dbef629a7ab0af89a083ceea8b437f`; production migration completion and API health still require confirmation. Verify CMS/API HTTPS, CMS publishing, product sync, media uploads, request ownership, backups, and rollback in staging before production acceptance.
