# Architecture

```text
Flutter customer app ───────┐
                           ├── FastAPI /api/v1 ─── Supabase PostgreSQL (external)
Next.js admin CMS ─────────┘       │
                                   ├── Firebase Admin token verification
                                   ├── WordPress REST (server-side, optional)
                                   └── allowlisted hosted chatbot URL config
```

Clients never receive database/service keys. Firebase client configuration in the app/browser is public client configuration; privileged Firebase service-account JSON and WordPress Application Password stay on the API server. All CMS mutations and customer writes pass through the API.

Admin content is staged separately from currently published catalogue/app content. Public app routes only return published records. Customer requests include the verified Firebase UID and are filtered by that UID for customer reads. CMS request access is admin/super-admin only; content editors can maintain catalogue/app content but cannot inspect customer submissions.

## Current boundaries

- Product and category technical fields are flexible JSON but validated and must retain source references before publishing.
- WordPress imports create drafts and do not fabricate missing technical facts.
- Chat is configured as an HTTPS hosted URL on a server-side hostname allowlist. Raw HTML/JavaScript snippets are not stored or executed.
- Customer request attachments, media storage, private manuals, customer/company profiles, equipment/warranty, notification delivery, and external CRM/ERP are not implemented.
- Coolify deployment uses the external Supabase database; local development PostgreSQL is separate.
