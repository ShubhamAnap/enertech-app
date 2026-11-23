# EnerTech CMS

Responsive CMS for product/category drafts and publication, customer-app home/contact/chat/branding content, WordPress product preview/import, and admin quote/service request triage.

## Local setup

Copy `.env.example` to `.env.local`. Set `NEXT_PUBLIC_API_BASE_URL` and the public Firebase Web App fields. These client values are embedded in the browser build; never add service-account credentials here. Admin access is verified and authorized by the FastAPI backend. There is no CMS-side public admin signup.

Start the API and database first, then run `npm run dev`. Changes save as drafts. Publish actions make supported data available to the customer app through the shared API.

See `../../docs/DEPLOYMENT.md` for Coolify build arguments and server-only secrets.
