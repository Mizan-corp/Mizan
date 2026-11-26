# Self-hosted production (`homie`)

Mizan production runs on Mizan's own server with Docker Compose, replacing Vercel and Neon.
`homie` is a Core 2 Duo with 2 GB of RAM, so everything is sized for it; it becomes a worker
of a k3s cluster when a stronger server joins as the control plane.

```
internet ─ Cloudflare (DNS, TLS, *.allmizan.live) ─ tunnel ─┬─ api   (the four APIs, one process)
                                                           ├─ web   (nginx: the four apps)
                                                           └─ postgres (on /srv)
```

| File | What |
|---|---|
| `compose.yaml` | The services. On the server in `/srv/mizan`, next to `mizan.env` (secrets) and `.env` (`MIZAN_TAG`, the running commit). Only `127.0.0.1` ports; the tunnel is the way in. |
| `asgi.py` | The four APIs in one process: picks the app by host (`api.`, `owner-api.`, `web-api.`, `admin-api.`) and drops the `/api` prefix, as Vercel's rewrites did. |
| `Dockerfile.api`, `Dockerfile.web` | The images. Dependencies sit in layers that change only with `pyproject.toml`/`package-lock.json`, so a release moves a few MB. |
| `nginx.conf`, `mizan-*.conf` | The apps by host: `allmizan.live` and `dev.` the website, `/owner/` and `/admin/` the panels, any other host the ERP. |
| `deploy.sh` | A release: pull, back up, migrate (`manage.py db migrate --production`), switch; keeps the previous release for rollback (`deploy.sh <previous tag>`). |
| `backup.sh`, `mizan-backup.{service,timer}` | Nightly `pg_dump` to `/mnt/media/backups/mizan` (another partition), 14 kept. |
| `backup-offsite.sh` | Run by `mizan-backup.service` after the nightly `backup.sh` (not on releases): encrypts the newest dump (gpg, AES-256, passphrase in `/srv/mizan/backup.passphrase`) and uploads it to the R2 bucket `mizan-backups` (credentials in `/srv/mizan/r2.env`, scoped to that bucket). Each object is locked for 30 days and deleted after 35. See *Restoring from the off-site copy* below. |
| `mizan-cron.sh`, `mizan-cron@.service`, `mizan-cron-{hourly,six-hourly,nightly,weekly,daily}.timer` | The scheduled platform jobs (Paymob reconcile hourly, subscription expiry every 6 h, nightly clean-up, storage and the ledger reconciliation, weekly stale data, daily owner emails). Each is a POST to the API on loopback with `CRON_SECRET`; results in `journalctl -t mizan-cron`; a failure emails the owner (once per 6 h per group). Replaces GitHub's scheduler, which fired only 4 to 10 times a day. The release copies `mizan-cron.sh`; the units are installed once: `sudo cp mizan-cron@.service mizan-cron-*.timer /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now mizan-cron-{hourly,six-hourly,nightly,weekly,daily}.timer`. Run a group by hand: `sudo systemctl start mizan-cron@nightly`, or one job: `/srv/mizan/mizan-cron.sh measure_storage`. |

## Releasing

Releases are manual, from a person's machine over SSH: see [`docs/deploy-homie.md`](../../docs/deploy-homie.md).
There is no GitHub runner on homie and no workflow that deploys (`deploy-server.yml` is only a notice).
On the server, `/srv/mizan/deploy.sh <commit>` releases images already present on it.

## Secrets (`/srv/mizan/mizan.env`, mode 600, not in git)

`SECRET_KEY`, `LICENSE_SIGNING_KEY`, `POSTGRES_PASSWORD`, `DATABASE_URL`
(`postgresql+asyncpg://mizan:<password>@postgres:5432/mizan`), `CRON_SECRET` (also the GitHub
secret the scheduled jobs use), `PAYMOB_*`, `MIZAN_INSTALLERS`, `TUNNEL_TOKEN`.

## Notes

- Uploads: `/srv/data/mizan/uploads` (`UPLOAD_DIR`), served by the system API at `/uploads`.
  Private files (clinical images, consent signatures): `/srv/data/mizan/private_uploads`
  (`PRIVATE_UPLOAD_DIR`), never served by URL; only authenticated routes read them.
- The rate limiter trusts `CF-Connecting-IP` only with `MIZAN_BEHIND_CLOUDFLARE=1`.
- Memory (measured): API ~190 MB, PostgreSQL ~60 MB, nginx ~5 MB.

## Restoring from the off-site copy

Works from any machine with `curl`, `gpg` and Docker, without homie. The passphrase and the bucket's
credentials are in `SECRETS.txt` (`MIZAN_BACKUP_PASSPHRASE`, `R2_*`) on homie and latitude; without the
passphrase the copies cannot be read.

```sh
sed -n 's/^MIZAN_BACKUP_PASSPHRASE=//p' ~/SECRETS.txt > pass; grep '^R2_' ~/SECRETS.txt > r2.env
export R2_ENV=./r2.env PASSFILE=./pass
backup-offsite.sh --list                                     # objects, newest last
backup-offsite.sh --get mizan-YYYYMMDD-HHMMSS.dump.gpg mizan.dump
# into an empty PostgreSQL 18: the dump grants to these roles (three are left over from Neon)
psql -U postgres -c "CREATE ROLE mizan LOGIN" -c "CREATE ROLE mizan_app LOGIN" \
     -c "CREATE ROLE neondb_owner NOLOGIN" -c "CREATE ROLE cloud_admin NOLOGIN" -c "CREATE ROLE neon_superuser NOLOGIN" \
     -c "CREATE DATABASE mizan OWNER mizan"
pg_restore -U postgres -d mizan --exit-on-error mizan.dump
```
Set the two roles' passwords to the ones in `mizan.env` before pointing the API at it. Tested on
2026-11-17 on latitude: the decrypted file matched homie's local dump byte for byte, `pg_restore` exited 0,
and tables, tenants, users and migrations matched production. A `DELETE` with homie's key is refused (409,
bucket lock).
