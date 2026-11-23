# Mizan Admin

The Mizan team's control panel: every workspace on the platform, their plans and
invoices, and everything the team changes. English, super-admins only.

| | Folder | Local | Production |
|---|---|---|---|
| Frontend | `frontend/` | `python manage.py dev admin` → http://localhost:5175 | https://allmizan.live/admin |
| API | `backend/` | `docker compose up admin-api` → :8002 | https://admin-api.allmizan.live/api |

Sign in with a platform account. On a fresh database `python manage.py db migrate`
creates `platform` / `changeme` (override with `MIZAN_PLATFORM_USERNAME` /
`MIZAN_PLATFORM_PASSWORD`). Give teammates access from the Team page.

## Pages

| Page | What it's for |
|---|---|
| **Overview** | Counts, revenue from paid invoices, weekly signups, and **Needs you**: ended trials, unpaid invoices, upgrade requests and trials ending within 7 days, each with its action |
| **Workspaces** | Search and filter every company; last-sale activity per workspace. A workspace page has its summary, plan & billing (change plan, extend trial, invoices), modules, people, activity and settings (rename, URL name, delete) |
| **Billing** | Invoices (mark paid with a transfer reference) and upgrade requests |
| **Activity** | The audit log of every change made here, as sentences |
| **Website** | allmizan.live's own visit counters (ADR-016): page views per day, pages, languages, referring sites, WhatsApp/phone clicks, demo requests and signups. Cookieless counts, no visitor data |
| **Team** | Who can use this panel; give or remove access |
| **System** | Live database health, migration status and stored records |

Every number comes from the database. Every change is written to the activity log,
including "Open as owner" (signing in to a workspace as its owner).

## Behaviour worth knowing

- **Single-device and LAN workspaces** (ADR-005) have a **Licence** tab: its end date,
  extend it, revoke or restore it, issue an offline key (for installs that never go online),
  and the installations that have checked in (computer, OS, version, last seen, last backup).
  "Open as owner" doesn't apply to them (their data lives on site). Revoking makes the
  install read-only at its next check-in; a key already handed out keeps working offline
  until it expires. Licence keys need `LICENSE_SIGNING_KEY` on this API.

- **Suspend** closes a workspace to its own people: they can't sign in or use the API
  until it's reactivated. Platform staff keep access. Nothing is deleted.
- **Mark paid** moves the workspace to the invoiced plan, applies its limits and ends
  the trial, through `app.services.subscriptions.activate_invoice` (the same code that
  payment webhooks use).
- **Monthly revenue** counts each paying workspace's latest paid invoice (yearly ÷ 12).
  Workspaces on a paid plan without a paid invoice are shown as complimentary.
- **Delete** requires typing the workspace's URL name and removes all of its data.

## Code

- `backend/admin_api/routers/`: `overview`, `workspaces`, `billing`, `activity`,
  `team`, `system` (all under `/admoon`, all `require_superadmin`).
- `backend/admin_api/common.py`: audit logging and lookups.
- `frontend/src/`: `Shell.tsx` (navigation), `pages/`, `ui.tsx` (buttons, tables,
  dialogs, states), `lib/data.ts` (typed API + queries), `lib/format.ts` (labels,
  money, dates), `lib/activity.ts` (log entries as sentences).
