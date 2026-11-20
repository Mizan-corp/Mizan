# Mizan ERP — API Standards

## 1. The APIs

| API | Address (production) | Who calls it |
|---|---|---|
| System | `https://api.allmizan.live/api` | The ERP app, storefronts, installed modules' servers (`/ext/v1`) |
| Owner | `https://owner-api.allmizan.live/api` | The owner panel, Paymob callbacks, on-site installs' check-ins |
| Website | `https://web-api.allmizan.live/api` | The website (signup) and the developer platform (`/developers`) |
| Admin | `https://admin-api.allmizan.live/api` | The admin panel |

On Vercel every route is under `/api` (rewritten to the app's root); locally and on site the
system API also serves its routes at `/api`. Interactive docs: `/api/docs` on each API.

## 2. Protocol & format

- **JSON over HTTPS**, UTF-8; Arabic is fine in payloads and query strings.
- **Responses return the data directly** (an object or a list), no envelope. Newer list
  endpoints return `{"items": [...], "total": n}` (with `page`/`pages`, or `limit`/`offset` on
  `/ext/v1`); a few older ones return a bare list.
- **Money** is a decimal string or number with two places, never a float computed on the client;
  **times** are ISO 8601 with a time zone; ids are UUIDs.
- **Typed parameters**: ids are `uuid.UUID`, dates `date`, choices `Literal` or an enum, lengths and
  limits bounded, in the route's signature, never a `str` parsed inside; bad input is a 422 (or an
  Arabic 400 for a rule, such as a range that ends before it starts), never a 500.
- **Days are the workspace's**: a date (a filter, a report's range, a document's date) is a day in
  the workspace's time zone, Africa/Cairo for now (`app/platform/tenancy/clock.py`); a range
  `from`..`to` covers both days fully. The current month (closed periods) is the workspace's too.
- New endpoints take and return Pydantic schemas (`schemas.py`), never ORM models.

## 3. Errors

FastAPI's shape: `{"detail": "<message>"}` with the right status (400, 401, 403, 404, 409, 422,
429). Messages in the ERP, owner and admin APIs are written for the user, in Arabic (the admin
panel's in English). Validation errors (422) carry FastAPI's list of field problems. Public
contracts for developers (`/ext/v1`, `/developers`) answer in English; the developer API answers
in Arabic when asked (`Accept-Language: ar`).

A route checks its references and lengths itself (an unknown or another workspace's id is a 404).
As a safety net, what the database refuses because of the input (an unknown reference, a duplicate,
a text too long, a number out of range) is a 400 or 409 with an Arabic message, never a 500
(`factory.database_refused_input`); the route sweep fails when a general module relies on it.

## 4. Authentication

| Who | How |
|---|---|
| Workspace users | `Authorization: Bearer <JWT>`; the token's `tid` is the workspace, bound for the request (RLS). Sessions can be revoked (`revoked_tokens`) and end on password change (#77). |
| Owners | JWT with `scope: owner` (the ERP refuses it, the owner API refuses ERP tokens) |
| Developers | JWT with `scope: developer`, or a CLI token `mzd_…` (`/developers` only) |
| Installed modules' servers | Installation token `mzx_…` (`/ext/v1` only; one workspace, its approved scopes) |
| Scheduler | `CRON_SECRET` in a header (`/…/cron/` routes) |
| Paymob | HMAC over its fields (the callback) |

- **CSRF:** a cookie session must echo the `csrf_token` cookie in `X-CSRF-Token` on `POST`,
  `PUT`, `PATCH`, `DELETE`. Requests with an `Authorization` header are exempt, as are sign-in
  and signup endpoints (they issue the session) and machine routes (`/ext/v1`, cron, Paymob,
  check-ins).
- **Permissions:** `require_perm("<permission>")` on every route that changes or reveals data;
  the permission is declared in a module's manifest. No role-name checks.
- **Rate limits:** sign-in 10 a minute, password changes 3 per 5 minutes, developer signup 5 an
  hour, `/ext/v1` 240 a minute per client; over the limit is 429.

## 5. Routes and versions

- Modules mount their routes through the loader; new modules use `/modules/<module_id>/…`
  (the core ERP keeps its historical paths: `/sales`, `/stock`, `/hr`…).
- **Public contracts are versioned and documented**: `/ext/v1` (the extension API for modules'
  servers) and its webhooks are documented at `dev.allmizan.live/docs` and change only with
  deprecation (ADR-007). Internal app APIs aren't versioned; the app and API ship together.
- Webhooks to developers' servers: `POST` JSON with `Mizan-Event`, `Mizan-Delivery`,
  `Mizan-Timestamp`, `Mizan-Signature: sha256=<HMAC-SHA256 of "<timestamp>.<body>">`.
