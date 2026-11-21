# ADR-005: Deployment Modes (Single Device, LAN, Bring Your Own Database)

## Status
Accepted (2026-11-09). Phases 1 (foundation) and 2 (installers and updates, #89) implemented; phases 3–4 tracked in GitHub issues.

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
- One **Mizan Setup** program per OS (Windows `.exe`, Linux single file), a Tauri app with a
  guided interface: welcome slides, licence, admin account, options, live progress, done
  (LAN: addresses, a QR code and the certificate for tills). The licence decides the mode,
  so the same setup installs single-device and LAN workspaces.
- The same file runs headless for servers (`MizanSetup install --licence <key> …`) and is the
  single-device desktop app (`--app`). `mizan-server` manages the installed server: status,
  start/stop/restart, licence show|set|check-in, backup/backups/restore, uninstall.
- Payload: the packaged system API (PyInstaller), a private PostgreSQL 16 (127.0.0.1 only,
  its own cluster), the built ERP. Runs as a Windows service (WinSW) or a systemd unit.
  Daily backups, the newest 14 kept.
- **Per client**: setup finds the licence by itself: stamped into the installer
  (`installer/stamp.py` appends it to the binary), a `.mzn` file next to the installer or in
  Downloads (the owner panel's Download offers "Mizan - <workspace>.mzn"), or the clipboard.
  Stamping happens offline or on a build host, not in the owner API: Vercel functions can't
  return a 140 MB file.
- Single device listens on `127.0.0.1` and opens in a Mizan app window. LAN serves HTTPS on
  every interface with a certificate from the install's own authority (`mizan.local`, the
  computer's name and addresses); tills install `mizan-ca.crt` once from
  `/api/onprem/ca.crt` (browsers only allow the offline POS queue on HTTPS).
- Built and smoke-tested on Linux and Windows by `.github/workflows/installers.yml`;
  `v*` tags publish a release. See `installer/README.md`.

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
- `app.platform.licensing.keys` (sign/verify; then `app.core.licensing`), `app.platform.licensing.services.licences` (create, extend, issue),
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

## Phase 2 — what's built

Released as **Mizan Setup v1.0.0** for Windows and Linux
([mizan-releases](https://github.com/mizan-corp/mizan-releases)); details in
[`installer/README.md`](../../installer/README.md).

- `installer/server/mizan_server/`: **mizan-server**: the install engine (JSON progress for
  the wizard; re-running it repairs or updates), the service runner (PostgreSQL, the API and
  app on one address, daily backups, `mizan.local` over mDNS on a LAN), the CLI, and the
  service (systemd system/user unit, or a Windows service through WinSW, plus a firewall rule
  for the local subnet on a LAN).
- `installer/setup/`: **Mizan Setup** (Tauri 2): the wizard, the single-device app window
  (`--app`) and headless installs, in one file with the payload appended
  (`[program][payload.zip][licence stamp][MZNSETUP footer]`).
- `installer/build.py` (payload: the app's on-site build, PostgreSQL 16.15 from theseus-rs with
  the Visual C++ runtime on Windows, mizan-server via PyInstaller; then the installers),
  `installer/stamp.py` (per-client installers), `installer/ci_smoke.py` and
  `.github/workflows/installers.yml` (built and smoke-tested on ubuntu-22.04 and
  windows-latest; `v*` tags publish).
- Owner panel: Download offers the installer and a "Mizan - <workspace>.mzn" licence file.
  System app: on a LAN, the sign-in page offers the certificate with per-device steps.

Decisions made while building it:

- **Licence finding, not typing.** Setup looks for a stamped licence, then a `.mzn` next to the
  installer, then one in Downloads (≤ 30 days old), then the clipboard. Stamping per client
  happens offline or on a build host: Vercel functions can't return a ~150 MB file.
- **PostgreSQL only.** The bundled database is PostgreSQL 16 (row-level security and JSONB are
  used throughout); no SQLite variant.
- **Windows permissions.** Run as an administrator, PostgreSQL restarts itself without the
  Administrators group, so setup grants Users read/execute on `pgsql/` and the installing
  account and SYSTEM full control of the data folder. `config.json` (database password,
  secret key) is limited to SYSTEM, Administrators and the installing account; the app window
  reads the non-secret `app.json`.
- **Windows-safe names.** A module folder named `prn` (a reserved device name) broke checkouts
  on Windows; folders must be valid on Windows (`AGENTS.md`).

Updates for installed servers (#89) are built: signed release offers in check-ins, `mizan-server update` with backup and roll-back (installer/README.md, "Updating"). Bring your own database: designed in ADR-009 (#91), not built. Also built (2026-11-12): one computer per licence, copies not renewed (#92);
backup copies to a USB drive or network share and stale-backup flags (#90); the in-app
network page for tills (#88). Not yet: encrypted cloud backup (#117, deferred), Windows code
signing and a manual Windows GUI pass (#93, deferred), checks on real LAN tills (#88).
