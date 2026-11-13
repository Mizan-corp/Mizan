# ADR-011: Self-hosted production (Vercel and Neon replaced by Mizan's own server)

## Status
Accepted and done (2026-11-13). Production moved at 15:48 UTC; the Vercel projects, their Blob
store, the domain on Vercel and the Vercel secrets and workflows were removed the same day. Neon
is kept read-only for a few days as a fallback.

**Temporarily back on Vercel (2026-11-13, 16:34 UTC onward):** `homie` went offline (power or
connection) 40 minutes after the move. Production was restored on Vercel + Neon: 8 projects
recreated (same names, linked to GitHub, deploying `master`; each builds only when its folder or
`shared/` changes), Cloudflare DNS pointing `allmizan.live` and `*.allmizan.live` at Vercel
(DNS-only; `_acme-challenge` delegated to Vercel for the wildcard certificate), Neon writable, and
`migrate-neon.yml` migrating it on each push. "Deploy (server)" is disabled. Writes made on the
server between 15:52 and 16:34 UTC are only in its database. To return: copy Neon to the server,
point DNS back at the tunnel, re-enable the server workflow, remove the Vercel bits again. Replaces the hosting parts of ADR-003 and ADR-008 (the domains
and the four products stay as they were).

## Context
Production ran on Vercel (8 projects: 4 apps, 4 serverless APIs) with Neon for the database.
The free plan is for non-commercial use, allows 100 deployments a day (8 per release), runs
nothing between requests (jobs needed GitHub's scheduler), keeps no disk (files needed Vercel
Blob) and needed Vercel's nameservers for the workspace wildcard. The owner decided to stop
deploying on Vercel and run production on Mizan's own server, `homie` (Core 2 Duo, 2 GB RAM,
HDD, home connection with a changing IP), the first node of a future cluster.

## Decision
- **Docker Compose on the server**, not Kubernetes yet. k3s was installed and measured: its
  control plane alone took ~830 MB of the 2 GB and kept the disk saturated. When a stronger server
  arrives it becomes the k3s control plane and `homie` joins as a worker (an agent is ~200 MB).
- **The four APIs in one process** (`deploy/server/asgi.py`): each API stays its own FastAPI app,
  picked by host; one interpreter and one copy of the kernel (~190 MB for all four).
- **The four apps from one nginx** (`deploy/server/nginx.conf`), routed by host exactly as the
  Vercel rewrites did: `allmizan.live` and `dev.` the website, `/owner/`, `/admin/` the panels,
  every other `*.allmizan.live` the ERP (`app.allmizan.live` when no workspace is involved).
- **PostgreSQL on the server** (Neon abroad would add ~60–150 ms per query); nightly `pg_dump`
  to another partition and before every release. Uploaded files on disk (`UPLOAD_DIR`).
- **Cloudflare** for DNS (nameservers moved from Vercel; Hostinger stays the registrar), TLS
  for `allmizan.live` and `*.allmizan.live`, and a **Cloudflare Tunnel** as the only way in: no
  open ports, the changing home IP doesn't matter. The rate limiter trusts `CF-Connecting-IP`
  only when `MIZAN_BEHIND_CLOUDFLARE` is set.
- **Releases stay push-to-deploy** (`.github/workflows/deploy-server.yml`): images build on
  GitHub while CI runs and go to GHCR (private); when CI passes, a GitHub runner on the server
  (label `homie`, only this job) pulls the changed layers, backs up, migrates, switches, and keeps
  the previous release for rollback. Images are layered so a release moves only the code.

## Consequences
- One machine: its disk, power and connection are production's. Backups must also leave the
  machine (to do: encrypted copies off-site, e.g. Cloudflare R2).
- 2 GB is tight; the API is one worker. RAM is the first upgrade.
- No more deployment quota, Blob or Neon; scheduled jobs could move onto the server.
- On-site installs released before this check in at the old Vercel owner API address until they
  update (new builds use `owner-api.allmizan.live`).
- Details and operations: `deploy/server/README.md`.
