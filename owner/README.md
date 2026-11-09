# Mizan owner panel

Where a business owner manages their Mizan account: every workspace they own, trials,
subscriptions, payments and invoices. Arabic, right-to-left.

| | Folder | Local | Production |
|---|---|---|---|
| Frontend | `frontend/` | `python manage.py dev owner` → http://localhost:5176 | https://mizan-co-owner.vercel.app |
| API | `backend/` | `docker compose up owner-api` → :8003 | https://mizan-co-owner-api.vercel.app |

## Who signs in where

- **Owners** sign in on the app's `/login` (https://mizan-co-app.vercel.app/login; the
  website's "Sign in" goes there), which hands them to this panel. The panel has no sign-in
  page: opening it signed out redirects to that `/login`, and `?next=` brings the owner back
  to the page they wanted.
- The website knows when an owner is signed in and then shows "Back to your panel" and
  "Sign out" instead of "Sign in" and "Get started". It keeps its own copy of the session
  (the apps are on separate domains): saved at signup, and by the app's `/login`, which
  passes through the website's `/session` on the way here. Signing out on either side
  signs out of both: the panel's button goes through the website's `/signout?to=login`,
  the website's goes through this panel's `/signout`.
- After signup the website hands the new owner over already signed in, and a short
  interactive tour introduces the panel.
- **Staff** sign in on their workspace's own page, `/c/<workspace>/login` in the app. Each
  workspace card shows that link. If an employee signs in on `/login` instead, they're sent
  to their workspace's page with their username filled in.
- "Open workspace" signs the owner in to the app as their admin user in that workspace.

Locally, `ammar` / `changeme` (from the bootstrap) is an owner account too.

## Pages

| Page | What it's for |
|---|---|
| **Workspaces** (`/`) | Every workspace: plan or trial days left, paid-until date, people, last sale, staff login link, open, subscribe; create another workspace |
| **Workspace** (`/workspaces/:id`) | Current plan, usage against limits, choose a plan (monthly/yearly) and pay, invoices. `?plan=pro&cycle=annual` preselects a plan; the ERP's pricing page links here |
| **Invoices** (`/invoices`) | All invoices across workspaces |
| **Account** (`/account`) | Name, phone, email, password (also updates the workspace logins); replay the tour |
| **Payment** (`/payment/:ref`) | Where Paymob returns the owner; waits for the verified callback |

## Paymob

Set these on the `mizan-owner-api` Vercel project (Paymob dashboard → Settings → API keys):

| Variable | Value |
|---|---|
| `PAYMOB_SECRET_KEY` | Secret key (`egy_sk_…`) |
| `PAYMOB_PUBLIC_KEY` | Public key (`egy_pk_…`) |
| `PAYMOB_HMAC_SECRET` | HMAC secret |
| `PAYMOB_INTEGRATION_IDS` | Comma-separated integration ids to offer (card, wallet, …) |
| `PAYMOB_BASE_URL` | Optional; defaults to `https://accept.paymob.com` |
| `OWNER_API_URL` / `OWNER_APP_URL` | Public URLs used for the callback and the return page (already set) |

In the Paymob dashboard, the integrations' **transaction processed callback** can stay empty:
each checkout passes `notification_url` = `OWNER_API_URL/account/paymob/callback` and
`redirection_url` = `OWNER_APP_URL/payment/<invoice>`.

How a payment goes: the owner picks a plan → `POST /account/workspaces/{id}/checkout`
creates a pending invoice and a Paymob intention → Unified Checkout → Paymob POSTs the
transaction with `?hmac=` → the callback verifies the HMAC, stores the transaction once,
checks the amount and calls `activate_invoice` → the return page sees the invoice paid.
Starting a new checkout abandons the previous unpaid one. Without the keys, checkout
answers 503 and the panel says online payment isn't available.

## Code

- `backend/owner_api/routers/`: `account` (profile, password, tour), `workspaces`
  (list, create, details, open), `billing` (plans, checkout, invoices, Paymob callback).
- Owner sign-in: `app.api.routers.owner_login` (`POST /account/login`), served by the
  system API for the app's `/login`.
- Shared services: `app.services.owners` (owner auth and lookups), `app.services.paymob`
  (intention + HMAC), `app.services.subscriptions` (invoices, activation),
  `app.services.workspaces` (creating a workspace).
- `frontend/src/`: `Shell.tsx`, `SignIn.tsx`, `Tour.tsx`, `pages/`, `ui.tsx`,
  `lib/data.ts` (typed API + queries), `lib/format.ts` (Arabic labels, money, dates),
  `lib/open.ts` (open a workspace).
- Tests: `backend/tests/` (sign-in scopes, isolation between owners, checkout, every
  callback case). `python manage.py test backend` runs them.
