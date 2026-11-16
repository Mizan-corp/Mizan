#!/usr/bin/env bash
# Mizan database failover, on latitude (deploy/failover/README.md, ADR-011).
#
# homie runs the primary; latitude runs a streaming standby (docker container mizan-postgres-standby).
# This watchdog promotes the standby only when BOTH say homie is gone:
#   1. latitude's standby isn't receiving WAL and homie's database can't be reached over Tailscale;
#   2. Cloudflare (the witness) shows no tunnel connector from any address other than latitude's own.
# for FAIL_AFTER seconds in a row. If Cloudflare can't be asked, nothing happens: no witness, no
# promotion. Before promoting it writes primary=latitude to the KV namespace, which homie's guard
# (mizan-guard.sh) reads to keep homie's app and tunnel off.
#
# Runs as root under systemd (mizan-db-watchdog.service). Settings: /etc/mizan-failover.env.
#   DRY_RUN=1 mizan-db-watchdog.sh --once   one check, prints what it would do, changes nothing
set -uo pipefail

ENV_FILE=${ENV_FILE:-/etc/mizan-failover.env}
# shellcheck disable=SC1090
[ -f "$ENV_FILE" ] && . "$ENV_FILE"
: "${CF_TOKEN:?}" "${CF_ACCOUNT:?}" "${CF_TUNNEL:?}" "${CF_KV_NAMESPACE:?}"
STANDBY=${STANDBY:-mizan-postgres-standby}
HOMIE_DB=${HOMIE_DB:-100.112.4.10:15433}     # homie's pg-bridge (Tailscale)
INTERVAL=${INTERVAL:-30}
FAIL_AFTER=${FAIL_AFTER:-180}                # seconds of "homie gone" before promoting
MIN_UPTIME=${MIN_UPTIME:-300}                # never promote right after latitude itself booted
STATE_DIR=${STATE_DIR:-/var/lib/mizan}
PROMOTED="$STATE_DIR/promoted"
ALERT_TO=${ALERT_TO:-ammar0xf@gmail.com}
DRY_RUN=${DRY_RUN:-0}
export KUBECONFIG=${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}
API=https://api.cloudflare.com/client/v4

log() { echo "$(date -Is) $*" >&2; }
cf() { curl -fsS -m 15 -H "Authorization: Bearer $CF_TOKEN" "$@"; }
psql_standby() { docker exec "$STANDBY" psql -U mizan -d mizan -tAX -c "$1" 2>/dev/null; }
run() { if [ "$DRY_RUN" = 1 ]; then log "DRY RUN: $*"; else "$@"; fi; }

alert() {  # subject, body (Brevo; best effort)
  [ "$DRY_RUN" = 1 ] && { log "DRY RUN: email \"$1\""; return 0; }
  [ -n "${BREVO_API_KEY:-}" ] || return 0
  python3 - "$1" "$2" <<'PY' | curl -fsS -m 20 -o /dev/null -H "api-key: $BREVO_API_KEY" -H "content-type: application/json" \
    -d @- https://api.brevo.com/v3/smtp/email || log "alert email failed"
import json, os, sys
print(json.dumps({"sender": {"name": "Mizan failover", "email": "no-reply@allmizan.live"},
                  "to": [{"email": os.environ.get("ALERT_TO", "ammar0xf@gmail.com")}],
                  "subject": sys.argv[1], "textContent": sys.argv[2]}))
PY
}
export ALERT_TO

# "online" / "offline" / "unknown": does Cloudflare see a connector from an address other than ours?
homie_on_cloudflare() {
  local mine conns
  mine=$(curl -fsS -m 10 https://1.1.1.1/cdn-cgi/trace 2>/dev/null | sed -n 's/^ip=//p')
  [ -n "$mine" ] || { echo unknown; return; }
  conns=$(cf "$API/accounts/$CF_ACCOUNT/cfd_tunnel/$CF_TUNNEL/connections") || { echo unknown; return; }
  python3 -c '
import json, sys
mine, data = sys.argv[1], json.loads(sys.stdin.read())
if not data.get("success"): print("unknown"); sys.exit()
ips = {c.get("origin_ip") for cl in data["result"] for c in cl.get("conns", [])}
print("online" if ips - {mine, None} else "offline")' "$mine" <<<"$conns"
}

# "up" / "down": is homie's database alive, seen from here?
homie_db() {
  [ "$(psql_standby "SELECT status FROM pg_stat_wal_receiver")" = streaming ] && { echo up; return; }
  timeout 5 bash -c "exec 3<>/dev/tcp/${HOMIE_DB%:*}/${HOMIE_DB#*:}" 2>/dev/null && { echo up; return; }
  echo down
}

promote() {
  local reason=$1 now
  now=$(date -Is)
  log "FAILOVER: $reason"
  # 1. The flag first: homie's guard keeps homie's app and tunnel off once it can see it.
  run cf -X PUT "$API/accounts/$CF_ACCOUNT/storage/kv/namespaces/$CF_KV_NAMESPACE/values/primary" \
    --data "{\"primary\":\"latitude\",\"at\":\"$now\",\"reason\":\"$reason\"}" >/dev/null || {
    log "could not write the primary flag to Cloudflare: not promoting"; return 1; }
  # 2. The standby becomes the primary.
  if [ "$DRY_RUN" = 1 ]; then log "DRY RUN: SELECT pg_promote(true, 60)"
  elif [ "$(psql_standby "SELECT pg_promote(true, 60)")" != t ]; then
    log "pg_promote failed"; alert "Mizan failover FAILED" "Promotion failed at $now ($reason). See journalctl -u mizan-db-watchdog on latitude."; return 1
  fi
  # 3. The cluster's database Service follows (the API reconnects: pool_pre_ping).
  run kubectl -n mizan scale deploy/pg-bridge --replicas=0
  run kubectl -n mizan scale deploy/pg-bridge-latitude --replicas=1
  run kubectl -n mizan patch svc postgres -p '{"spec":{"selector":{"app":"pg-bridge-latitude"}}}'
  [ "$DRY_RUN" = 1 ] || { mkdir -p "$STATE_DIR"; echo "$now $reason" > "$PROMOTED"; }
  alert "Mizan failover: latitude is now the primary database" \
"homie's database and tunnel were gone for $FAIL_AFTER seconds ($reason), so latitude promoted its standby at $now.
allmizan.live is served from latitude. homie's guard keeps homie's app and tunnel off while the flag says latitude.
Uploads and mail live on homie and stay unavailable until it is back.
Switching back is manual: deploy/failover/README.md, \"After a failover\"."
  log "failover done"
}

check() {
  if [ -f "$PROMOTED" ]; then return 0; fi
  if [ "$(psql_standby "SELECT pg_is_in_recovery()")" != t ]; then
    log "standby isn't in recovery (not running, or already a primary): nothing to watch"; DOWN_SINCE=; return 0
  fi
  local db cfstate up
  db=$(homie_db)
  if [ "$db" = up ]; then DOWN_SINCE=; return 0; fi
  cfstate=$(homie_on_cloudflare)
  if [ "$cfstate" != offline ]; then
    [ -n "${DOWN_SINCE:-}" ] || log "homie's database unreachable but Cloudflare says homie is $cfstate: not counting"
    DOWN_SINCE=; return 0
  fi
  [ -n "${DOWN_SINCE:-}" ] || { DOWN_SINCE=$(date +%s); log "homie looks gone (database unreachable, no tunnel connector)"; }
  up=$(cut -d. -f1 /proc/uptime)
  if [ $(( $(date +%s) - DOWN_SINCE )) -ge "$FAIL_AFTER" ] && [ "$up" -ge "$MIN_UPTIME" ]; then
    promote "homie unreachable over Tailscale and absent from Cloudflare for ${FAIL_AFTER}s" && return 0
  fi
}

DOWN_SINCE=
if [ "${1:-}" = --once ]; then
  log "standby in recovery: $(psql_standby 'SELECT pg_is_in_recovery()'), receiver: $(psql_standby 'SELECT status FROM pg_stat_wal_receiver'), homie db: $(homie_db), homie on cloudflare: $(homie_on_cloudflare), promoted: $([ -f "$PROMOTED" ] && cat "$PROMOTED" || echo no)"
  [ -n "${SIMULATE_GONE:-}" ] && { DRY_RUN=1; promote "simulated"; }
  exit 0
fi
log "watching homie (every ${INTERVAL}s, promote after ${FAIL_AFTER}s)"
while true; do check; sleep "$INTERVAL"; done
