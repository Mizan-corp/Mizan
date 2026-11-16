# ADR-011: Self-hosted production (Vercel and Neon replaced by Mizan's own server)

## Status
Accepted and done (2026-11-13). Production moved at 15:48 UTC; the Vercel projects, their Blob
store, the domain on Vercel and the Vercel secrets and workflows were removed the same day. Neon
is kept read-only for a few days as a fallback.

A power cut on homie (2026-11-13, 16:34 UTC) sent production back to Vercel + Neon for a few
hours; it returned to the server the same evening (Neon copied back and kept read-only, DNS on
the tunnel again, the temporary Vercel files removed). The Vercel projects stay unlinked as a
fallback; how to use it is in the operations notes. A UPS and off-site backups are the next
safeguards. Replaces the hosting parts of ADR-003 and ADR-008 (the domains
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
  **Done (2026-11-14):** `latitude-e6530` (4 cores, 7.6 GB, SSD, on all the time) runs the k3s
  control plane (v1.37, Traefik, ServiceLB and metrics-server disabled; Cloudflare Tunnel stays the
  way in) and `homie` joined as a worker. Cluster traffic goes over Tailscale (`--flannel-iface
  tailscale0`; API `https://100.112.4.15:6443`). Labels `mizan/role=control|worker`. The join token
  is in `~/SECRETS.txt` on homie. Production still runs on Docker Compose on homie; moving it onto
  the cluster is the next step, piece by piece (apps and APIs first, the database last).
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
- The database copied from Neon kept Neon's default privileges (for `neondb_owner`), so tables the
  server's login role `mizan` created afterwards (v74, v75, `whatsapp_message_log`) had no grants
  for `mizan_app` and workspace requests touching them failed with "permission denied" until
  2026-11-13. Every migrate path now grants `mizan_app` on all tables and sets default privileges
  for the current login role (`APP_ROLE_GRANTS` in `app/db/migrations.py`).
- **CI and scheduled jobs run on Mizan's own machines** (2026-11-14), after GitHub's free hosted
  minutes ran out: CI on latitude-e6530 (runner `latitude-ci`), the release and the scheduled jobs
  on homie. See `.github/RUNNERS.md`.
- Details and operations: `deploy/server/README.md`.

### Database failover (2026-11-16)
homie's database streams to a standby on latitude. latitude promotes it only when homie's database is
unreachable over Tailscale **and** Cloudflare (the witness) shows no tunnel connector from homie, for
3 minutes; it writes `primary=latitude` to a KV flag first. homie's guard owns homie's tunnel: it stops
it after 90 s without Cloudflare, and keeps homie fenced (no tunnel, no API, no releases) while the flag
says latitude. Switching back is manual. Details and runbook: `deploy/failover/README.md`.

### Scheduled jobs run from the server (2026-11-16)
GitHub's scheduler is best effort: it fired the five schedules (about 30 runs a day) only 4 to 10 times a
day, with gaps of 4 to 5 hours, and a wrong runner label (`[self-hosted, homie]`, while homie's runner has
only `homie`) left every run queued from 14 to 16 Nov. The schedules now run from systemd timers on homie
(`deploy/server/mizan-cron.sh`), calling the API on loopback: reliable, free, independent of GitHub and of
the tunnel. `.github/workflows/jobs.yml` keeps only a manual run.
