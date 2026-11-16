#!/usr/bin/env bash
# Mizan failover guard, on homie (deploy/failover/README.md, ADR-011).
#
# homie's tunnel connector is what lets homie take writes from users. The guard owns it (the compose
# service has restart: "no"; this starts and stops it):
#   - Cloudflare unreachable for SELF_FENCE_AFTER seconds (less than latitude's FAIL_AFTER): stop the
#     tunnel. latitude may be about to promote; homie must not be serving when it does.
#   - The KV flag says primary=latitude: homie is fenced for good. Tunnel and API stay stopped, deploys
#     refuse to run (deploy.sh checks $FENCED), until someone follows the runbook and removes it.
#   - After a stop, a reboot or a restart of this guard, the tunnel only comes back once it's certain
#     latitude didn't promote: latitude's standby is streaming from homie again, or the flag is still
#     absent CONFIRM_AFTER seconds after Cloudflare answered again (KV reads can lag ~60 s).
#
# Runs as root under systemd (mizan-guard.service). Settings: /etc/mizan-failover.env.
#   mizan-guard.sh --status   what the guard sees now, changes nothing
set -uo pipefail

ENV_FILE=${ENV_FILE:-/etc/mizan-failover.env}
# shellcheck disable=SC1090
[ -f "$ENV_FILE" ] && . "$ENV_FILE"
: "${CF_TOKEN:?}" "${CF_ACCOUNT:?}" "${CF_TUNNEL:?}" "${CF_KV_NAMESPACE:?}"
TUNNEL=${TUNNEL:-mizan-tunnel-1}
APP=${APP:-mizan-api-1}
PRIMARY=${PRIMARY:-mizan-postgres-1}
INTERVAL=${INTERVAL:-15}
SELF_FENCE_AFTER=${SELF_FENCE_AFTER:-90}
CONFIRM_AFTER=${CONFIRM_AFTER:-120}
STATE_DIR=${STATE_DIR:-/var/lib/mizan}
FENCED="$STATE_DIR/fenced"
API=https://api.cloudflare.com/client/v4

log() { echo "$(date -Is) $*" >&2; }
running() { [ "$(docker inspect -f '{{.State.Running}}' "$1" 2>/dev/null)" = true ]; }

# "latitude" / "none" / "unknown"
flag() {
  local out code
  out=$(curl -sS -m 15 -w '\n%{http_code}' -H "Authorization: Bearer $CF_TOKEN" \
    "$API/accounts/$CF_ACCOUNT/storage/kv/namespaces/$CF_KV_NAMESPACE/values/primary" 2>/dev/null) || { echo unknown; return; }
  code=${out##*$'\n'}
  case "$code" in
    200) grep -q '"primary":"latitude"' <<<"${out%$'\n'*}" && echo latitude || echo none ;;
    404) echo none ;;
    *) echo unknown ;;
  esac
}

latitude_streaming() {
  [ "$(docker exec "$PRIMARY" psql -U mizan -d mizan -tAX -c \
    "SELECT count(*) FROM pg_stat_replication WHERE application_name='latitude_standby' AND state='streaming'" 2>/dev/null)" = 1 ]
}

fence_for_good() {
  [ -f "$FENCED" ] || { mkdir -p "$STATE_DIR"; echo "$(date -Is) $1" > "$FENCED"; log "FENCED: $1"; }
  running "$TUNNEL" && docker stop "$TUNNEL" >/dev/null && log "tunnel stopped"
  running "$APP" && docker stop "$APP" >/dev/null && log "API stopped"
}

if [ "${1:-}" = --status ]; then
  echo "flag: $(flag); latitude streaming: $(latitude_streaming && echo yes || echo no); tunnel running: $(running "$TUNNEL" && echo yes || echo no); fenced: $([ -f "$FENCED" ] && cat "$FENCED" || echo no)"
  exit 0
fi

LOST_SINCE=; CONFIRM_SINCE=; NEED_CONFIRM=1   # a fresh start (boot) proves nothing yet
log "guard started"
while true; do
  f=$(flag)
  if [ "$f" = latitude ]; then
    fence_for_good "Cloudflare flag: latitude is the primary"
  elif [ -f "$FENCED" ]; then
    fence_for_good "still fenced (runbook: deploy/failover/README.md)"
  elif [ "$f" = unknown ]; then
    CONFIRM_SINCE=
    [ -n "$LOST_SINCE" ] || { LOST_SINCE=$(date +%s); log "Cloudflare unreachable"; }
    if [ $(( $(date +%s) - LOST_SINCE )) -ge "$SELF_FENCE_AFTER" ] && running "$TUNNEL"; then
      docker stop "$TUNNEL" >/dev/null && log "self-fence: Cloudflare unreachable for ${SELF_FENCE_AFTER}s, tunnel stopped"
    fi
    [ $(( $(date +%s) - LOST_SINCE )) -ge "$SELF_FENCE_AFTER" ] && NEED_CONFIRM=1
  else  # none: Cloudflare answers and latitude hasn't claimed the primary
    [ -n "$LOST_SINCE" ] && log "Cloudflare reachable again"
    LOST_SINCE=
    if [ "$NEED_CONFIRM" = 1 ]; then
      if latitude_streaming; then
        NEED_CONFIRM=0; log "latitude's standby streams from homie: homie is the primary"
      else
        [ -n "$CONFIRM_SINCE" ] || { CONFIRM_SINCE=$(date +%s); log "waiting ${CONFIRM_AFTER}s for the flag to settle"; }
        if [ $(( $(date +%s) - CONFIRM_SINCE )) -ge "$CONFIRM_AFTER" ]; then
          NEED_CONFIRM=0; log "no primary flag after ${CONFIRM_AFTER}s: homie is the primary"
        fi
      fi
    fi
    if [ "$NEED_CONFIRM" = 0 ]; then
      CONFIRM_SINCE=
      running "$APP" || { docker start "$APP" >/dev/null && log "API started"; }
      running "$TUNNEL" || { { docker start "$TUNNEL" >/dev/null 2>&1 ||
        (cd /srv/mizan && docker compose --profile tunnel up -d tunnel >/dev/null 2>&1); } && log "tunnel started"; }
    fi
  fi
  sleep "$INTERVAL"
done
