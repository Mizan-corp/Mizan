# Mizan — Engineering Quality Gates & What AI Forgets
Source: ChatGPT Main chat, messages [58–59], Nov 2026
GPT model: gpt-6

---

## The Core Problem with AI-Assisted Development

> "The biggest risk with AI-assisted development is not that the AI writes bad code. It's that it writes code that looks correct, passes a few happy-path tests, and quietly misses the engineering requirements that make a SaaS safe and maintainable in production."

**Make the AI produce a small design note before significant changes, and a test-and-risk report afterward.** This forces it to think beyond the visible feature and makes omissions detectable during review.

---

## 16 Engineering Dimensions Most AI Misses

### 1. Multi-tenancy: The Most Dangerous Omission
- Every business row must carry `tenant_id` (TenantScoped mixin)
- Three defense layers (all three required):
  1. **ORM query filter**: `with_loader_criteria` injects `tenant_id == ctx` on every SELECT/UPDATE/DELETE
  2. **Before-flush stamp**: copies ContextVar onto new TenantScoped rows in `before_flush`
  3. **PostgreSQL RLS**: `ENABLE + FORCE` with `tenant_isolation` policy; GUC `app.tenant_id` set per transaction
- After `db.commit()` under PgBouncer: re-apply `set_config('app.tenant_id', :t, true)` via `after_begin` listener
- Never bypass any layer — a single bypass leaks all tenant data
- `users` table must have RLS too (fixed in migration v33)
- Migrations must run with `app.bypass = 'on'`

### 2. Authorization Is More Than Roles
- Granular permissions per endpoint, not just role checks
- `require_perm` dependency on every sensitive endpoint
- UI must gate navigation items — don't show routes the user can't access
- Permission denied state must be designed (not a 404 or crash)

### 3. ERP Business Invariants and Transaction Integrity
- Every business operation must be **atomic**: stock deduction + invoice creation in ONE transaction
- Never split related mutations across separate commits
- Use `SERIALIZABLE` isolation for: payroll close, period close, shift close
- **Example — posting an invoice must atomically:**
  1. Deduct stock from warehouse
  2. Create invoice record
  3. Record payment(s)
  4. Update customer balance
  5. Write audit log
- If any step fails, the entire operation rolls back

### 4. Database Design, Migrations, and Data Lifecycle
- Tracked migrations ONLY — append to `scripts/migrate.py MIGRATIONS` list (never ALTER directly)
- Idempotent SQL: `CREATE TABLE IF NOT EXISTS`, `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`
- FK indexes on every FK column: `CREATE INDEX IF NOT EXISTS idx_<table>_<col> ON <table>(<col>)`
- Composite per-tenant uniques replace global ones
- Tenant deletion cascades through ALL business tables including `users`
- Never hard-delete financial records (soft-delete or archive with `is_archived = True`)
- `is_demo BOOLEAN NOT NULL DEFAULT FALSE` on all business tables for clean demo wipe via `POST /platform/wipe-demo`

### 5. API Design and Reliability
- Consistent error shape: `{"detail": "message"}` or `{"detail": [{"loc": ..., "msg": ...}]}`
- Pagination on EVERY list endpoint (`page`, `size`, `total`, `pages`)
- No N+1 queries — use `selectinload` or `joinedload`
- `/shifts/current` returns 200 + `null` when no shift open (not 404)
- `/stock/valuation` returns a totals **object**, not rows
- Print endpoints reject session tokens — use 60s `scope=print` token from `POST /auth/print-token`

### 6. Background Jobs, Events, and Integrations
- All async tasks (payroll, ZK sync, WhatsApp dispatch, shift auto-close) must be **retryable and idempotent**
- Use `python manage.py cron --run-all` for the automation worker
- Midnight shift auto-close is a background job, not a user action
- WhatsApp dispatch is queued for the worker (not blocking request flow)
- Background jobs must handle: duplicate execution, partial failure, retry with backoff

### 7. Observability: How Will You Know It Is Broken?
- Structured logging (JSON format, not print statements)
- Sentry or equivalent for error tracking with context
- `/health` endpoint: `{"status":"ok","database":"connected"}`
- Alert on error rate spike and p95 latency increase
- Log tenant ID on every request for debugging

### 8. Backups and Disaster Recovery
- Neon automated backups enabled and tested
- Point-in-time recovery configured and verified
- Tested restore procedure documented
- Recovery Time Objective (RTO) defined before production

### 9. CI/CD and Deployment Safety
- No direct push to `master` without passing CI
- Frontend deploy: **CLI-only** (`npx vercel --prod --yes --token <TOKEN>`) — intentionally NOT git-linked
- Backend deploy: **git-only** (push to `master` on Vercel project `vendora-backend`)
- `CORS_ORIGINS` is a **Vercel env var** on the backend — overrides `config.py`. New frontend origins go there + redeploy
- Migrations run before backend starts (not in application code)

### 10. Security Beyond Authentication
- CSRF double-submit: cookie `csrf_token` echoed as `X-CSRF-Token` header
- httpOnly cookies for session tokens
- Rate limiting on all auth endpoints
- `/auth/login` and `/platform/signup` are CSRF-exempt; everything else requires the token
- No secrets in code — use environment variables
- Print endpoints: 60s scoped token via `POST /auth/print-token`, accepted as `?token=` query param
- Login route flips to app only when **both** `token AND user` exist — never store token before `/auth/me`

### 11. Auditability and Business History
- `AuditLog` entry for every destructive action (cancel sale, wipe demo, approve payroll, delete product)
- Never hard-delete invoices, payments, or stock movements
- Store who did it, when, what changed, and the old value
- `is_demo` flag for clean demo data tracking

### 12. Testing the Failure Paths
- e2e tests must cover: invoice cancel, offline sync conflict, trial expiry, payment failure
- Offline POS: stock collision policy = allow negative balance + create `AuditLog(inventory_discrepancy)`
- 107 e2e tests in `e2e/` must stay green on CI
- Unit tests: 9 vitest tests in `frontend/` must pass
- Never mark a feature complete without running the e2e suite

### 13. Performance and Capacity Planning
- `stock_balances` maintained table for O(1) stock reads (not computed on-the-fly)
- FK indexes on all FK columns — no index scan for every join
- Connection pooling via PgBouncer (Neon pooled URL in Vercel env)
- PgBouncer transaction mode requires re-applying tenant GUC on every transaction
- No N+1 queries in any endpoint

### 14. SaaS Subscription and Tenant Lifecycle
- Plan gating via feature flags stored per tenant (from onboarding wizard)
- Self-serve demo wipe: `POST /platform/wipe-demo`
- Trial: 14 days after signup → trial banner → `/pricing`
- After `POST /platform/signup`: MUST fetch `/auth/me` before `setUser` — signup response lacks `permissions` array
- Plans: أساسي 499 ج.م / احترافي 999 ج.م / مؤسسي custom
- **Payment providers NOT yet wired**: Fawry, Paymob, InstaPay — currently manual activation

### 15. Internationalization, Time, and Money
- All money stored as `Numeric/Decimal` — **never float**
- All timestamps stored in UTC
- Display: `ar-EG-u-nu-latn` locale + `.num` class — Western digits always
- RTL layout: `dir="rtl"` on document, logical CSS properties throughout
- Arabic microcopy uses authentic Egyptian colloquial terminology

### 16. Maintainability and Engineering Discipline
- No business logic in routers — belongs in services
- Fat routers are technical debt: `hr.py` (1024 lines), `admoon.py` (1183 lines)
- Function-scope imports to avoid circular imports
- `AGENTS.md` is the non-negotiable contract for all agents
- No new color values outside `DESIGN_SYSTEM.md`
- No new `components/ui.tsx` usages — migrate to `components/kit/`

---

## Engineering Quality Gate Checklist

> Before marking any backend feature complete:

- [ ] Every new table: `ENABLE + FORCE` RLS with `tenant_isolation` policy
- [ ] Every mutation: inside a single DB transaction
- [ ] Every list endpoint: paginated (`page`, `size`, `total`, `pages`)
- [ ] No business logic in routers (belongs in service layer)
- [ ] Every migration: appended to `scripts/migrate.py`, idempotent, numbered `v<N>_<name>`
- [ ] `AuditLog` entry for every destructive action
- [ ] FK indexes on every FK column
- [ ] Money stored as `Numeric`, never float
- [ ] `is_demo = False` on all new seeded data
- [ ] No N+1 queries

---

## The "Agent Prompt" GPT Recommended

> **Mizan Engineering Quality Gate**
>
> Before implementing any feature:
> 1. Identify all new database tables — add RLS, tenant_id, FK indexes
> 2. Identify all mutations — wrap in a transaction with rollback
> 3. Identify all list endpoints — add pagination
> 4. Identify all business logic — move to a service, not a router
> 5. Add an AuditLog entry for any destructive or financial mutation
> 6. Write the migration as idempotent SQL in scripts/migrate.py
> 7. After implementation, run: npm test + tsc + build + e2e on affected paths
