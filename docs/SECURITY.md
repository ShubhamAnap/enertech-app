# Security and privacy

## Implemented

- Supabase/PostgreSQL, Firebase Admin, WooCommerce, chat widget, and Supabase Storage credentials are API-server environment values. CMS and mobile clients do not receive database/service-role credentials.
- Firebase ID tokens are verified on protected routes with revocation checks. CMS roles are active server-side records or bootstrap super-admin UIDs; there is no public CMS signup.
- Admin account provisioning is super-admin-only. Customer profile/request directory access is admin/super-admin-only; customer request reads are scoped by Firebase UID.
- Customer onboarding and service/quote submissions require verified Firebase email. The submitted profile email must match the token identity.
- Product, category, FAQ, and app content changes are audited. User-facing app configuration is published-only.
- WooCommerce records are pulled with server-only read-only credentials. WooCommerce-owned products/categories cannot be edited or unpublished from CMS; update them in WordPress and sync.
- Chat is published only when the app URL and widget script use HTTPS hosts in `CHAT_ALLOWED_HOSTS`. The WebView navigates only to those allowlisted hosts. The widget key is kept in the API environment and sent only to the enabled, published widget integration.
- CMS asset uploads accept PNG, JPEG, and WebP signatures, cap file size at 10 MB, and write to Supabase Storage with the server-only service key.

## Production work still required

- Create and configure production Firebase/Supabase projects, API/CMS origins, authorized admin UID, and Coolify secrets.
- Configure WooCommerce read-only credentials and verify source routes, media relationships, and product mappings before syncing production data.
- Confirm customer privacy notice, retention/deletion, account lifecycle, service/quote status policy, and staff assignment policy.
- Add malware scanning and private file storage/authorized download flows before allowing customer uploads or private manuals. Current asset uploads are for public images; product PDF links are public WordPress URLs.
- Add rate limits, abuse controls, secure response headers, monitoring, dependency/secret scanning, offsite backup, and restore/rollback evidence.
- Complete staging acceptance and release review before publishing a production domain or signed APK.
