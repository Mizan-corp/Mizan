# Database failover between homie and latitude (ADR-011)

Goal: `allmizan.live` keeps working when either machine is down, with two machines and nothing paid.

| Piece | homie | latitude |
|---|---|---|
| Database | primary (`mizan-postgres-1`, compose) | streaming standby (`mizan-postgres-standby`, docker) |
| App and APIs | compose (`api`, `web`) | k3s (`api`, `web`) |
| Tunnel connector | compose `tunnel`, owned by `mizan-guard` | k3s `tunnel` |
| Failover piece | `mizan-guard.service` | `mizan-db-watchdog.service` |

Replication goes through homie's k3s `pg-bridge` (`100.112.4.10:15433` → the primary on loopback):
role `replicator` (password in homie's `~/SECRETS.txt`, `PG_REPLICATOR_PASSWORD`), slot
`latitude_standby`, `pg_hba.conf` allows it from the Docker gateway `192.168.80.1`. homie keeps at most
2 GB of WAL for the slot (`max_slot_wal_keep_size`), so a long latitude outage can't fill homie's disk
(the standby then needs a fresh `pg_basebackup`).

## How it decides

Two machines can't tell "the other one died" from "the link between us broke". Cloudflare is the
witness: it sees each machine's tunnel connector and stores one flag, `primary`, in the KV namespace
`mizan-failover`.

**latitude promotes** only when, for 3 minutes in a row:
- its standby receives no WAL and homie's database can't be reached over Tailscale, **and**
- Cloudflare shows no tunnel connector from any address but latitude's own.

If Cloudflare can't be asked, it doesn't promote. Then it writes `primary=latitude` to KV, promotes
the standby (`pg_promote`), points the k3s `postgres` Service at `pg-bridge-latitude` and emails
`ALERT_TO`. The API reconnects by itself (`pool_pre_ping`); it isn't restarted, because its uploads
volume is NFS from homie.

**homie's guard** owns homie's tunnel connector (compose `restart: "no"`):
- Cloudflare unreachable for 90 s → stops the tunnel (before latitude's 3 minutes are up).
- Flag says `latitude` → fenced: tunnel and API stay stopped, `/var/lib/mizan/fenced` is written and
  `deploy.sh` refuses to release.
- After its own start (a boot) or a self-fence, the tunnel comes back only when latitude's standby
  streams from homie again, or the flag is still absent 120 s after Cloudflare answers.

| Situation | Result |
|---|---|
| latitude down | homie keeps serving; latitude's connector is just gone |
| homie down (power, crash) | about 4 minutes of errors on anything using the database, then latitude serves alone |
| homie's internet down, homie running | homie stops its tunnel at 90 s; latitude promotes at 3 min; when homie's internet returns it sees the flag and stays fenced |
| Tailscale between them broken, both online | Cloudflare still sees homie: no promotion |
| Cloudflare API unreachable | no promotion; homie stops its own connector (latitude's keeps serving on homie's database) |

Still on homie only: uploads (NFS) and mail. After a failover they're unavailable until homie is back.

## Install

On both machines, as root: `/etc/mizan-failover.env` from `mizan-failover.env.example` (chmod 600),
with that machine's token (`mizan-failover-latitude` or `mizan-failover-homie`; the values are in
homie's `~/SECRETS.txt`).

```bash
# latitude
install -m 755 mizan-db-watchdog.sh /usr/local/sbin/ && install -m 644 mizan-db-watchdog.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now mizan-db-watchdog
# homie
install -m 755 mizan-guard.sh /usr/local/sbin/ && install -m 644 mizan-guard.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now mizan-guard
```

Check without changing anything: `mizan-db-watchdog.sh --once` (latitude; `SIMULATE_GONE=1` also
prints what a failover would do) and `mizan-guard.sh --status` (homie). Logs: `journalctl -u
mizan-db-watchdog` / `-u mizan-guard`.

The standby was made with:

```bash
docker run --rm --network host -v /home/ammar/mizan-standby-data:/var/lib/postgresql/data -e PGPASSWORD=… \
  postgres:18-alpine pg_basebackup -h 100.112.4.10 -p 15433 -U replicator -D /var/lib/postgresql/data -Fp -Xs -P -R -S latitude_standby
docker run -d --name mizan-postgres-standby --restart unless-stopped -e PGDATA=/var/lib/postgresql/data \
  -v /home/ammar/mizan-standby-data:/var/lib/postgresql/data -p 127.0.0.1:15432:5432 postgres:18-alpine
```

## After a failover (manual)

latitude is the primary and homie is fenced. To make homie the primary again, during a quiet hour:

1. On homie, keep the guard stopped while you work: `systemctl stop mizan-guard`.
2. Make homie's database a copy of latitude's: stop `mizan-postgres-1`, move its data directory aside,
   `pg_basebackup` from latitude (expose latitude's database to homie over Tailscale for this, e.g.
   scale `pg-bridge-latitude` and use `100.112.4.15:15433`), add `standby.signal`, start it, and wait
   until it streams.
3. Switch: stop the k3s API's writes for a moment (`kubectl -n mizan scale deploy/api --replicas=0`),
   promote homie (`SELECT pg_promote()`), point the Service back
   (`kubectl -n mizan patch svc postgres -p '{"spec":{"selector":{"app":"pg-bridge"}}}'`, scale
   `pg-bridge` to 1 and `pg-bridge-latitude` to 0), scale the API back to 1.
4. Rebuild latitude's standby from homie (the `pg_basebackup` above, after recreating the slot
   `latitude_standby` on homie).
5. Clear the fence: delete the KV key `primary`, `rm /var/lib/mizan/fenced` on homie and
   `/var/lib/mizan/promoted` on latitude, then `systemctl start mizan-guard` on homie.

## The edge guard (latitude's link to the database)

Cloudflare spreads requests between homie's connector and latitude's. latitude's API reaches the database
on homie over Tailscale, so while that link is slow (it was seen on a relayed path at 2 to 3 seconds per
round trip) about half of all requests hang or time out, and long jobs such as `measure_storage` fail
with a Cloudflare 524. `mizan-edge-guard` (on latitude) watches the link and keeps the connector out of
the tunnel while it is bad:

- every 15 s it measures the median of three connects to homie's database bridge (`100.112.4.10:15433`);
- **out:** 4 probes in a row at 400 ms or more (or no connection), so within about a minute: `kubectl -n mizan scale deploy/tunnel --replicas=0`; homie serves everything;
- **back:** 12 probes in a row at 150 ms or less (3 minutes);
- it only restores what it removed (`/var/lib/mizan/edge-guard-down`), never overrides a manual scale, and does nothing once latitude is the primary (`/var/lib/mizan/promoted`): then latitude must serve;
- an email goes out on each change; `touch /var/lib/mizan/edge-guard-off` stands the guard down;
- a release re-applies the manifest (tunnel at 1 replica); if the link is still bad the guard removes the connector again within a minute.

If homie itself is down the probe fails too, so the guard also takes latitude out; that is harmless (the
site has no database anyway) and the watchdog's promotion puts the connector back.

Install: `install -m 755 mizan-edge-guard.sh /usr/local/sbin/ && install -m 644 mizan-edge-guard.service /etc/systemd/system/ && systemctl daemon-reload && systemctl enable --now mizan-edge-guard`.
Check: `mizan-edge-guard.sh --once`. Test the decisions: `EDGE_FAKE_MS=900 DRY_RUN=1 INTERVAL=1 SLOW_CYCLES=2 mizan-edge-guard.sh`.
