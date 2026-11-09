# ADR-005: Deployment Modes (Single Device, LAN, Bring Your Own Database)

## Status
Accepted (2026-11-09). Phase 1 (foundation) implemented; phases 2–4 tracked in GitHub issues.

## Context
The website promised offline desktop and LAN versions, but every workspace ran in our
cloud. Owners asked for three more ways to run Mizan:

1. **Single device**: one PC, no other devices, works without internet.
2. **LAN**: one server on the shop's network, cashiers and offices connect to it.
3. **Bring your own database (BYODB)**: a normal cloud workspace whose data lives in a
   PostgreSQL the owner provides (their VPS, Supabase, Neon, RDS, Cloud SQL…).

Mizan's data layer is PostgreSQL-specific (row-level security, JSONB, `set_config`), so
"SQLite on the desktop" isn't an option and Firebase/Firestore can't hold Mizan data.
Every mode runs on PostgreSQL.

## Decision

### A workspace is created in a mode
`tenants.deployment_mode` is `cloud_saas` (default), `desktop` or `lan`, chosen when the
owner creates the workspace in the owner panel. Desktop and LAN workspaces are not exported
from the cloud: the cloud keeps only their registration (the tenant row, owner, licence,
installations, invoices); the workspace itself, with all its data, is created on the
customer's machine by the installer. In the owner panel, "Open workspace" is replaced by
**Download** for these workspaces.

### Licences
- One licence per desktop/LAN workspace (`licences`): mode, plan, `valid_until`, revocation.
- A **licence key** is a signed token: `MZN1.<payload>.<signature>`, base64url, signed with
  the platform's **Ed25519** private key (`LICENSE_SIGNING_KEY`, only on the owner and admin APIs). The
  public key ships with every install, so keys verify **offline**.
- The payload names the workspace (id, name, slug, sector, modules), the owner, the mode, the
  plan's limits, `valid_until` and when it was issued.
- **Paying extends the licence**: `activate_invoice` moves `valid_until` to the end of the
  paid period. A trial licence runs to the end of the trial.
- **Renewal**: an install that can reach the internet checks in
  (`POST /installations/check-in`) and receives a fresh key with the new `valid_until`.
  An install that's always offline gets a new key typed in from the owner panel.
- When the licence has expired the install becomes **read-only** (like an expired trial);
  data is never locked away.
- The admin panel lists licences and installations, extends or revokes licences and
  issues keys.

### Installations
Every on-premise install has an id generated on first run. Check-ins (when online) record
host name, OS, version, mode, last seen and the last backup, shown to the owner and to the
admin panel. Cloud contact is optional: an install that never checks in keeps working
until its key expires.

### Server mode (what the installer runs)
The system API runs in **server mode** when `MIZAN_MODE=desktop|lan`:
- it serves the built ERP from the same address (`/` → the app, `/api` → the API), so one
  process and one port serve everything;
- it is single-workspace: on first start it creates the workspace described by the licence
  (same id, name, sector and modules as in the cloud) and its admin user;
- it enforces the licence on every write (expired → read-only, revoked → read-only).

### Installers (phase 2)
- One **Mizan Setup** app per OS (Windows `.exe`, Linux AppImage/`.deb`), a Tauri app with
  a modern guided interface: welcome slides, licence, install location, admin password,
  (LAN) network and server address, progress, done.
- The same setup runs headless for servers: `mizan-setup install --licence <key> …`, and a
  `mizan` CLI manages the installed server (status, backup, restore, update, licence).
- Payload: the packaged system API (PyInstaller), a private PostgreSQL 16, the built ERP.
  Runs as a Windows service / systemd unit.
- **Per client**: the owner panel's Download stamps the client's licence into the installer
  (a signed block appended to the binary, read by setup), so setup needs no typing.
- Single device opens in a Mizan app window bound to `localhost`. LAN serves
  `https://<server>.local` with a locally-generated certificate (browsers only allow the
  offline POS queue on HTTPS), advertised over mDNS.
- Updates use the existing `/updater` endpoints (Tauri updater format).

### Cloud backup (phase 3, optional)
Encrypted scheduled backups uploaded to Mizan, opt-in per workspace, visible and
restorable from the admin panel.

### Bring your own database (phase 4)
A cloud workspace whose business data lives in a PostgreSQL the owner provides. Platform
data (tenants, owners, billing, licences) stays in Mizan's database; the workspace's schema
and data live in theirs. The API routes each request to the workspace's database (engine per
external database, connection string encrypted at rest), runs migrations on it, and checks
compatibility (PostgreSQL ≥ 14, a non-superuser role so row-level security applies,
latency). Managed from the admin panel; set up from the owner panel.

## Consequences
- One code base for every mode: the same API and ERP, with server mode switched on by
  environment.
- Licences work without internet; copying a key to another machine can't be prevented
  offline. Installations are visible when they check in.
- The licence signing key is the most sensitive secret on the platform: losing it means
  issuing a new public key in an update; leaking it means anyone can mint licences.
  Outside production, keys are signed with a development key derived from `SECRET_KEY`,
  which production installs don't accept.

## Phase 1 — what's built
- `app.core.licensing` (sign/verify), `app.services.licences` (create, extend, issue),
  migration `v48_licences_and_installations`, the hook in `activate_invoice`.
- Owner API: workspaces have a mode; `GET /account/workspaces/{id}/download` (fresh key and
  published installers from `MIZAN_INSTALLERS`); `POST /installations/check-in`.
- Admin API and panel: mode on workspaces, a Licence tab (extend, revoke/restore, offline key,
  installations); every action in the activity log.
- Owner panel: choose how a new workspace runs; Download (installers, steps, licence key)
  instead of Open; licence and devices on the workspace page.
- Server mode: `app.onprem` (`setup`, `server`, `licence`, `checkin`, `state`), wired in
  `system/backend/main.py`; the app's on-premise build (`VITE_DEPLOYMENT=onprem`) with the
  workspace's own `/login` and a licence banner (enter a key, check now).

Try it locally:

```bash
# 1. Owner panel → New workspace → "شبكة محلية" → Download → copy the licence key
# 2. An empty PostgreSQL database, then:
cd system/frontend && VITE_DEPLOYMENT=onprem VITE_API_URL=/api npx vite build --outDir /tmp/mizan-web
cd system/backend
export DATABASE_URL=postgresql+asyncpg://…/empty_db SECRET_KEY=<same as the local stack> \
       MIZAN_DATA_DIR=/tmp/mizan-data PYTHONPATH=.:../../shared/backend
python -m app.onprem.setup --licence "<key>" --admin-password "<8+ chars>" --demo
MIZAN_MODE=lan MIZAN_WEB_DIR=/tmp/mizan-web MIZAN_CLOUD_URL=http://localhost:8003 \
  uvicorn main:app --host 0.0.0.0 --port 8100     # → http://localhost:8100
```
