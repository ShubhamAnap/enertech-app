# Data model

## Current tables

- `product_categories`: slug, name, description, order, optional image, published fields, pending draft payload.
- `products`: category, slug/model/name, descriptions, validated applications/features/specifications/images, WordPress source references, verification/publish state, pending draft payload.
- `admin_accounts`: Firebase UID, optional display/email, role, active flag.
- `app_config`: supported `home`, `contacts`, `chat`, and `brand` drafts, published revisions, actor and time.
- `audit_events`: actor UID, action, entity, field/status summary, timestamp.
- `customer_requests`: owner Firebase UID/email, service or quote type, status, submitted payload, optional assigned staff UID and customer-facing note, timestamps.
- `knowledge_articles`: customer-facing answer, topic/category, source reference, publication state, pending draft data.

The customer request API scopes customer reads by `customer_uid`; admin request review requires admin/super-admin. No customer records or catalogue items are seeded.

## Deliberately not yet modeled

Company/contact verification, membership and invitations, service equipment and warranty/AMC, request attachments, private manuals/documents, notifications, CRM/ERP synchronization, and comprehensive audit-log browsing. These depend on the ownership, source-of-truth, retention, and operating policies still needed from EnerTech.

All schema changes are Alembic migrations. PostgreSQL JSON fields hold validated supported data; API models bound field counts and lengths. Product and support-answer publishing requires a source reference; imported WordPress details are not trusted automatically.
