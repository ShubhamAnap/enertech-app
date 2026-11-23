# Test Plan and Current Evidence

## Current backend coverage

- Liveness and readiness endpoints.
- Empty catalogue response.
- Published-only category/product behavior, including suppression under an unpublished category.
- Search and pagination behavior.
- Invalid `limit`, `offset`, and search input rejection.

Run from `backend`: `..\\.venv\\Scripts\\python.exe -m pytest -q`.

## Current app checks

- Admin: ESLint and production compilation/build.
- Flutter: static analysis and widget checks for the home journeys and empty request state.
- Android debug package: local Gradle build; a signed release package needs the owner's release keystore and application signing configuration.

## Remaining required coverage

- DB migration from empty DB and upgrade path; PostgreSQL constraints and rollback in disposable DB.
- Auth expiry/revocation, RBAC, customer ownership/IDOR, privilege escalation, rate limiting.
- Admin forms, workflow transitions, publish/unpublish preview, table filtering and permission states.
- Upload validation, private download authorization, audit and retention.
- Additional Flutter repository/state tests, accessibility/text scaling checks, and end-to-end customer journeys.
- Customer RFQ → admin assignment/status → quotation publish → customer access; service request → admin update → customer tracking.
- Accessibility, responsive viewports, text scaling, offline/slow network, error recovery.
- Staging smoke, backups/restore, monitoring, rollback, and Android release signing.

No production data or credentials are present. Test fixtures are in-memory and isolated.
