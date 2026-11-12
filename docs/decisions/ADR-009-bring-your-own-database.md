# ADR-009: Bring your own database (cloud workspace, customer's PostgreSQL)

## Status

Proposed (2026-11-12). Design only, at the owner's request; nothing is built. Tracks #91 and
ADR-005 phase 4.

## Context

A cloud workspace's data lives in Mizan's database (Neon) with every other workspace's,
isolated by `tenant_id`, row-level security and the `mizan_app` role (#112). Some customers
want the data in a PostgreSQL they control (their VPS, Supabase, Neon, RDS, Cloud SQL) while
still using Mizan Cloud's app and APIs. Firestore and other non-PostgreSQL stores can't hold
Mizan data.

How a request reaches the database today:

- `get_db` opens a session on the **one** engine (`app/db/base.py`).
- `get_current_user` reads the token's `tid` and calls `bind_tenant`: the context variable
  (ORM scoping and stamping), `app.tenant_id` (RLS) and `SET LOCAL ROLE mizan_app`.
- Platform rows (tenants, owner accounts, billing, licences, the platform audit log) and
  workspace rows share that database; some flows write both in one transaction (signup,
  activating an invoice, creating a workspace).
- Raw SQL (`text()`) is common and has no mapper.
- Scheduled jobs and the admin panel's figures read across every workspace.
- `manage.py db migrate --production` migrates one database.

## Decision

### D1. What lives where

- **Mizan's database keeps everything platform-wide**: `tenants`, `owner_accounts`, billing,
  licences and installations, the platform audit log, `workspace_databases`, files' metadata.
- **The customer's database holds the workspace**: every `TenantScoped` table, its users and
  roles, and its own copy of its `tenants` row (the foreign keys point at it). This is the same
  schema an on-site install builds (`app.onprem.setup.build_schema`), so there's one
  "workspace in its own database" path to maintain.
- **One external database per workspace.** An owner with two workspaces brings two databases
  (or two schemas in one server; see D6). This keeps RLS a second line of defence rather than
  the only one between two businesses.
- Uploaded files stay in Mizan's storage (`app/framework/files.py`); only rows move.

### D2. Routing: a session picks its connection by table

`get_db` yields a **routing session** (a SQLAlchemy `Session` subclass with `get_bind`):

- mapped classes from the platform list → Mizan's engine;
- `TenantScoped` classes → the bound workspace's engine (Mizan's when it has none);
- raw SQL → the workspace engine when one is bound, else Mizan's. Platform raw SQL must use
  an explicit platform session (`platform_session()`); a test fails if a platform table name
  appears in `text()` outside it.

The workspace is known before the first query: the token's `tid` (ERP), the slug (sign-in
pages, storefront), or the owner panel's workspace id. `bind_tenant` resolves the engine from a
small cache (`workspace_engines`, keyed by tenant id, LRU of ~50; `NullPool` on Vercel, a small
pool on long-running servers) and applies the same three settings on that connection.

Writes that touch both databases (creating a workspace, applying a paid invoice's limits) are
done as two transactions in a fixed order (platform first, then workspace) with an idempotent
retry; there is no two-phase commit. Each such flow is listed in the implementation PR.

### D3. Setting up a database

Owner panel → workspace → "use my own database" (and the same for the admin panel):

1. The owner pastes a connection string. It's **encrypted at rest** (Fernet, key in the
   `WORKSPACE_DB_KEY` env var on the APIs that need it) and never returned to any browser.
2. Checks, with plain-language results: reachable from Mizan Cloud (and TLS); PostgreSQL ≥ 14;
   the role is **not a superuser and has no BYPASSRLS**, so RLS applies; it can create tables;
   `pgcrypto` is available; latency (warn above ~80 ms round trip, since every page makes
   several queries); for serverless providers, the pooled endpoint is used.
3. The schema is built (`build_schema` + migrations) and the role `mizan_app` is created if the
   login role may create roles; otherwise `MIZAN_DB_APP_ROLE` is skipped for that database and
   the login role (non-superuser, FORCE RLS on every table) is what RLS restricts.
4. The workspace's data is copied in (D6), then the workspace switches over.

`workspace_databases`: tenant id, encrypted URL, status (`checking`, `ready`, `migrating`,
`failed`, `unreachable`), schema version, last check, last error, latency.

### D4. Migrations on every deploy

`manage.py db migrate --production` migrates Mizan's database, then each `ready` external
database, **before** the APIs are deployed (deploy.yml already runs migrations first). A
database that fails or can't be reached is marked `failed` and its workspace becomes
**read-only with a notice** (the existing `ensure_workspace_writable` gate) until a migration
succeeds; it never blocks the deploy for everyone else. The admin panel can retry ("migrate
now"). Migrations stay backward-compatible for one release (add, then use, then drop), as
they must already be for zero-downtime deploys.

### D5. What reads across workspaces

- **Admin figures** (sales counts, last sale, storage) read only Mizan's database. External
  workspaces show figures from their last measurement (the storage job and a small "usage"
  summary written by the workspace engine into Mizan's database), labelled with its time.
- **Scheduled jobs** that walk every workspace (`app/platform/automation_worker`) run per
  database with a time limit each; an unreachable one is skipped and reported.
- **Backups**: Mizan doesn't back up external databases. The owner panel says so when the
  option is chosen, and the checks recommend the provider's point-in-time recovery.

### D6. Moving a workspace in and out

Moving is an export of the workspace's `TenantScoped` rows (in foreign-key order, `COPY` per
table filtered by `tenant_id`) into the other database, run as a background job with the
workspace read-only meanwhile, then counts compared per table before switching
`workspace_databases.status` to `ready` (or deleting it, to move back). The same export later
gives owners a full data download. Two workspaces in one external server use separate
schemas (`search_path` per engine), never shared tables.

### D7. Security

- The connection string is a secret: encrypted at rest, decrypted only inside the APIs, never
  logged (the URL's password is masked in errors), rotated by the owner from the panel.
- Mizan Cloud's outgoing addresses are published so owners can allow-list them.
- The external role is checked on every connect: if it became a superuser or gained
  BYPASSRLS, the workspace stops with an error rather than running without RLS.

## Plan (each step shipped and tested before the next)

1. Routing session, `platform_session()`, the raw-SQL guard test, the engine cache; every
   existing test runs with a second local database as an "external" workspace.
2. `workspace_databases`, the checks and the schema build; admin panel: list, check, migrate now.
3. Migrations over external databases in `db migrate --production`; read-only on failure.
4. Move in/out (D6); owner panel "use my own database".
5. Admin figures and scheduled jobs per D5.

## Consequences

- Every query path gains a routing decision; the raw-SQL guard and the two-database test run
  keep that honest. Platform-wide reports become "as of the last measurement" for these
  workspaces.
- Performance depends on the customer's database and its distance from Vercel's region; the
  checks make that visible before switching.
- Support gets harder (we can't see their database's state); the admin panel shows health and
  the last error, and the owner remains responsible for backups.

## Open questions

- Pricing: a separate add-on, or Enterprise only?
- Do we allow the owner's database to be read by their own tools (BI) while Mizan writes to it?
  Recommended: yes, read-only roles they create themselves.
