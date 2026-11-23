# API Contract

Prefix `/api/v1`; JSON; UUID identifiers; UTC timestamps. Errors use FastAPI's `detail` field. List endpoints are bounded and paginated.

## Public app routes

| Method/path | Purpose |
|---|---|
| `GET /health` | Process liveness |
| `GET /api/v1/health/ready` | Database readiness |
| `GET /api/v1/app/config` | Published CMS app sections only |
| `GET /api/v1/catalogue/categories` | Published categories |
| `GET /api/v1/catalogue/products` | Published product page; `q`, `category`, `limit`, `offset` |
| `GET /api/v1/catalogue/products/{slug}` | Published product details |

## Firebase-authenticated customer routes

All require a valid Firebase ID token in `Authorization: Bearer ...`. Submissions require an email-verified account. Reads are filtered by the token UID.

| Method/path | Purpose |
|---|---|
| `POST /api/v1/requests/service` | Submit a service request |
| `POST /api/v1/requests/quote` | Submit a quote enquiry |
| `GET /api/v1/requests` | List the signed-in customer's own requests |

## Firebase-authenticated CMS routes

All require a valid Firebase ID token and an active backend admin role. Product/app content mutations create drafts until published. Customer-request routes are limited to admin/super-admin roles.

| Method/path | Purpose |
|---|---|
| `GET/POST /api/v1/admin/catalogue/categories` | List/create category drafts |
| `PATCH /api/v1/admin/catalogue/categories/{id}` | Save category draft |
| `POST /api/v1/admin/catalogue/categories/{id}/publish` | Publish category |
| `POST /api/v1/admin/catalogue/categories/{id}/unpublish` | Unpublish category |
| `GET/POST /api/v1/admin/catalogue/products` | List/create product drafts |
| `PATCH /api/v1/admin/catalogue/products/{id}` | Save product draft |
| `POST /api/v1/admin/catalogue/products/{id}/publish` | Publish verified product |
| `POST /api/v1/admin/catalogue/products/{id}/unpublish` | Unpublish product |
| `GET/PUT /api/v1/admin/app-config/{home\|contacts\|chat\|brand}` | Read/save supported app-content draft |
| `POST /api/v1/admin/app-config/{key}/publish` | Publish app-content revision |
| `POST /api/v1/admin/app-config/{key}/unpublish` | Remove published app-content revision |
| `GET /api/v1/knowledge` | Published support answers |
| `GET/POST /api/v1/admin/knowledge` | List or create answer drafts |
| `PATCH /api/v1/admin/knowledge/{id}` | Save answer draft |
| `POST /api/v1/admin/knowledge/{id}/publish` | Publish source-referenced answer |
| `POST /api/v1/admin/knowledge/{id}/unpublish` | Remove answer from customer app |
| `GET /api/v1/admin/integrations/wordpress/status` | Read server-side integration configuration status |
| `GET /api/v1/admin/integrations/wordpress/products` | Preview source products |
| `POST /api/v1/admin/integrations/wordpress/import` | Import source item as an unpublished draft |
| `GET /api/v1/admin/requests` | List service or quote customer requests |
| `PATCH /api/v1/admin/requests/{id}` | Update status, assigned staff UID, and customer note |

Admin access is granted through server-only `BOOTSTRAP_SUPER_ADMIN_UIDS` or an active `admin_accounts` row. Never place service credentials in a client request or browser variable.
