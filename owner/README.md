# Mizan owner panel

Where a business owner manages their Mizan account: every workspace they own, trials,
subscriptions, payments and invoices. Arabic, right-to-left.

| | Folder | Local | Production |
|---|---|---|---|
| Frontend | `frontend/` | `python manage.py dev owner` → http://localhost:5176 | https://allmizan.live/owner |
| API | `backend/` | `docker compose up owner-api` → :8003 | https://owner-api.allmizan.live/api |

## Who signs in where

- **Owners** sign in at https://allmizan.live/login (the website's "Sign in"), which forwards to
  this panel's sign-in (`/owner/login`, ADR-008); `?next=` brings the owner back to the page
  they wanted.
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

## How a workspace runs

Owners choose when they create a workspace (ADR-005):

| Mode | What it is | In the panel |
|---|---|---|
| **على السحابة** (cloud) | In the browser; we host it | "Open workspace" |
| **جهاز واحد** (single device) | An app on one Windows or Linux computer, works offline | "Download" (تنزيل) |
| **شبكة محلية** (LAN) | A server on the shop's network; tills and offices connect to it | "Download" (تنزيل) |

Single-device and LAN workspaces are only registered in the cloud (with a licence); the
installer creates the workspace on site. Paying extends the licence to the end of the paid
period; installs pick up the new key when they're online, or the owner copies it from
Download. The workspace page lists the installed devices and when they last checked in.

**Download** (`DownloadDialog.tsx`, `GET /account/workspaces/{id}/download`) gives:
- **Mizan Setup** for Windows and Linux, listed from `MIZAN_INSTALLERS` on the owner API
  (links to the public [mizan-releases](https://github.com/ammar0xff/mizan-releases); see
  `shared/backend/app/core/releases.py` and `installer/README.md`). Unset, the dialog says
  the installer is being prepared.
- **The licence file** "Mizan - <workspace>.mzn" (made in the browser from the key). Saved
  in Downloads, Mizan Setup finds it by itself.
- The steps for the mode, and the licence key to copy (for installs that never go online).

Installs check in at `POST /installations/check-in` (this API) and receive the renewed key.

## Pages

| Page | What it's for |
|---|---|
| **Workspaces** (`/`) | Every workspace: plan or trial days left, paid-until date, people, last sale, staff login link, open, subscribe; create another workspace |
| **Workspace** (`/workspaces/:id`) | Current plan, usage against limits, choose a plan (monthly/yearly) and pay, invoices. `?plan=pro&cycle=annual` preselects a plan; the ERP's pricing page links here |
| **Invoices** (`/invoices`) | All invoices across workspaces |
| **Account** (`/account`) | Name, phone, email, password (also updates the workspace logins); replay the tour |
| **Payment** (`/payment/:ref`) | Where Paymob returns the owner; waits for the verified callback |

## Paymob

Two flows, chosen with `PAYMOB_FLOW` on the `mizan-owner-api` Vercel project:

- **`intention`** (default): an Intention API payment, paid on Paymob's Unified Checkout,
  which offers every integration in `PAYMOB_INTEGRATION_IDS` on one page.
- **`accept`**: the Accept API (an order and a payment key). The owner picks **card** or
  **wallet** in the pay dialog: a card opens **Mizan's own card page** (a Paymob-hosted
  iframe, [`paymob/`](paymob/README.md)), a wallet goes to Paymob's wallet page for the
  number entered. Card is offered only once `PAYMOB_IFRAME_ID` is set.

| Variable | Flow | Value |
|---|---|---|
| `PAYMOB_HMAC_SECRET` | both | HMAC secret (Settings → API keys) |
| `PAYMOB_SECRET_KEY`, `PAYMOB_PUBLIC_KEY` | intention | `egy_sk_…`, `egy_pk_…` (test or live) |
| `PAYMOB_INTEGRATION_IDS` | intention | Comma-separated integration ids |
| `PAYMOB_FLOW` | — | `intention` or `accept` |
| `PAYMOB_API_KEY` | both | The dashboard's API key (same for test and live): the accept flow, and checking pending invoices with Paymob (also on `mizan-admin-api`) |
| `PAYMOB_CARD_INTEGRATION_ID`, `PAYMOB_WALLET_INTEGRATION_ID` | accept | One integration per method |
| `PAYMOB_IFRAME_ID` | accept | Mizan's card page, from `python owner/paymob/upload.py` |
| `PAYMOB_TEST_OWNERS` | both | While set (comma-separated logins), only these owners may pay: for running production against Paymob's test mode. The panel shows a test-mode note to them |
| `PAYMOB_BASE_URL` | both | Optional; defaults to `https://accept.paymob.com` |
| `CRON_SECRET` | both | Shared with the scheduler (`.github/workflows/jobs.yml`, GitHub secret of the same name) and `mizan-system-api` |
| `MIZAN_COMPANY_DETAILS` | both | Optional: Mizan's legal details on receipts, lines separated by `\|` |
| `OWNER_API_URL` / `OWNER_APP_URL` | both | Public URLs for the callback and the return page (already set) |

Callbacks: the intention flow passes `notification_url` = `OWNER_API_URL/account/paymob/callback`
and `redirection_url` = `OWNER_APP_URL/payment/<invoice>` with each payment. The accept flow
uses the integrations' settings instead: **processed callback** =
`https://owner-api.allmizan.live/api/account/paymob/callback`, **response callback** =
`https://allmizan.live/owner/payment` (the panel forwards to the invoice from
`merchant_order_id`).

How a payment goes: the owner picks a plan → `POST /account/workspaces/{id}/checkout`
creates a pending invoice and the Paymob payment → the owner pays on Paymob's page (or
ours) → Paymob POSTs the transaction with `?hmac=` → the callback verifies the HMAC, stores
the transaction once, checks the amount and calls `activate_invoice` → the return page sees
the invoice paid. Starting a new checkout abandons the previous unpaid one. Without the
keys, or for owners outside `PAYMOB_TEST_OWNERS`, checkout answers 503 and the panel says
online payment isn't available.

**Changing activity (#107)**: workspace settings → «تغيير النشاط». The owner sees what leaves,
joins and works differently, chooses whether leaving modules' data is kept hidden 30 days or
deleted, and asks; the Mizan team approves (applied at once) or rejects with a reason in the admin
panel. Routes in `owner_api/routers/activity.py`; logic in `app.platform.tenancy.activity_change`.

**Changing plan (#68)**, in `app.platform.billing.services.subscriptions` (`checkout_quote`,
`new_invoice`, `activate_invoice`, `apply_due_plan_changes`). The panel shows the quote
(`GET /account/workspaces/{id}/checkout/quote?plan=&cycle=`) before sending the owner to Paymob.

| Choice | Starts | Price | Unused paid time |
|---|---|---|---|
| No paid time left (trial, lapsed) | now | the plan's | — |
| Same plan (renewal) | when the paid time ends | the plan's | kept (the new period follows it) |
| Dearer plan (upgrade) | now | the plan's, in full | becomes extra days on the new plan at its daily rate; the old periods end at payment |
| Cheaper plan (downgrade) | when the paid time ends | the plan's | kept: the workspace stays on the dearer plan until then |

A plan paid ahead switches when its period starts: the subscriptions job
(`enforce_subscription_expiry`, every 6 hours) runs `apply_due_plan_changes` first.

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

### When the callback doesn't come (#67)

Every Paymob transaction goes through `app/integrations/paymob/reconcile.py:apply_transaction`,
recorded once per transaction and state. Each hour the scheduler calls
`POST /account/cron/paymob-reconcile` (header `X-Cron-Secret`): Paymob invoices pending for
15 minutes to 48 hours are looked up with Paymob's inquiry API (`PAYMOB_API_KEY`) and applied
the same way. In the admin panel, **Check with Paymob** on a pending invoice does the same for
one invoice. A late callback after that is a duplicate and changes nothing.
