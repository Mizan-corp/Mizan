#!/usr/bin/env bash
# Mizan edge guard, on latitude (deploy/failover/README.md, ADR-011).
#
# latitude's API copy reaches the database on homie over Tailscale. Cloudflare spreads requests
# between homie's connector and latitude's, so while that link is slow (a relayed path can take 2 to 3
# seconds per round trip) roughly half of all requests hang or time out. This guard watches the link and
# takes latitude's tunnel connector out while it is degraded, so homie serves everything; it puts it
# back after the link has been healthy for a few minutes.
#
#   slow  = median connect time to homie's database bridge >= SLOW_MS (or no connection), SLOW_CYCLES in a row
#   good  = median connect time <= FAST_MS, FAST_CYCLES in a row (hysteresis: 4 x 15 s out, 12 x 15 s back)
#
# It only restores what it removed itself (state file), never overrides a manual `kubectl scale`, does
# nothing once latitude has been promoted to primary (then latitude must serve), and stands down while
# /var/lib/mizan/edge-guard-off exists.
#   mizan-edge-guard.sh --once      one probe and what it would do; changes nothing
#   EDGE_FAKE_MS=900 DRY_RUN=1 ...  pretend the link takes 900 ms (tests the decisions)
set -uo pipefail

ENV_FILE=${ENV_FILE:-/etc/mizan-failover.env}
# shellcheck disable=SC1090
[ -f "$ENV_FILE" ] && . "$ENV_FILE"
TARGET=${EDGE_TARGET:-100.112.4.10:15433}      # homie's pg-bridge over Tailscale (what the API connects to)
INTERVAL=${INTERVAL:-15}
SLOW_MS=${SLOW_MS:-400}
FAST_MS=${FAST_MS:-150}
SLOW_CYCLES=${SLOW_CYCLES:-4}
FAST_CYCLES=${FAST_CYCLES:-12}
STATE_DIR=${STATE_DIR:-/var/lib/mizan}
OFF="$STATE_DIR/edge-guard-off"
PROMOTED="$STATE_DIR/promoted"
DOWN="$STATE_DIR/edge-guard-down"              # present while the guard has the connector out
DRY_RUN=${DRY_RUN:-0}
export KUBECONFIG=${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}
ALERT_TO=${ALERT_TO:-ammar0xf@gmail.com}
export ALERT_TO

log() { echo "$(date -Is) $*" >&2; }
run() { if [ "$DRY_RUN" = 1 ]; then log "DRY RUN: $*"; else "$@"; fi; }

alert() {  # subject, body (Brevo; best effort)
  [ "$DRY_RUN" = 1 ] && { log "DRY RUN: email \"$1\""; return 0; }
  [ -n "${BREVO_API_KEY:-}" ] || return 0
  python3 - "$1" "$2" <<'PY' | curl -fsS -m 20 -o /dev/null -H "api-key: $BREVO_API_KEY" -H "content-type: application/json" \
    -d @- https://api.brevo.com/v3/smtp/email || log "alert email failed"
import json, os, sys
print(json.dumps({"sender": {"name": "Mizan edge guard", "email": "no-reply@allmizan.live"},
                  "to": [{"email": os.environ.get("ALERT_TO", "ammar0xf@gmail.com")}],
                  "subject": sys.argv[1], "textContent": sys.argv[2]}))
PY
}

# Median of three connection times in ms; 3000 for a connection that did not open within 3 s.
probe() {
  if [ -n "${EDGE_FAKE_MS:-}" ]; then echo "$EDGE_FAKE_MS"; return; fi
  local host=${TARGET%:*} port=${TARGET#*:} t=() s e
  for _ in 1 2 3; do
    s=$(date +%s%N)
    if timeout 3 bash -c "exec 3<>/dev/tcp/$host/$port" 2>/dev/null; then e=$(date +%s%N); t+=($(( (e - s) / 1000000 ))); else t+=(3000); fi
  done
  printf '%s\n' "${t[@]}" | sort -n | sed -n 2p
}

replicas() { kubectl -n mizan get deploy tunnel -o jsonpath='{.spec.replicas}' 2>/dev/null; }

take_out() {
  log "TAKING OUT latitude's tunnel connector: database link slow ($1 ms median)"
  if run kubectl -n mizan scale deploy/tunnel --replicas=0 >/dev/null; then
    [ "$DRY_RUN" = 1 ] || { mkdir -p "$STATE_DIR"; date -Is > "$DOWN"; }
    alert "Mizan: latitude taken out of the tunnel (slow link to the database)" \
"The link from latitude to homie's database answered in $1 ms (median of 3) for $((SLOW_CYCLES * INTERVAL)) seconds, so requests served by latitude would hang.
latitude's tunnel connector is scaled to 0; homie serves everything. It returns by itself after the link has been under ${FAST_MS} ms for $((FAST_CYCLES * INTERVAL)) seconds.
To keep it out: touch $OFF   To bring it back now: kubectl -n mizan scale deploy/tunnel --replicas=1 && rm $DOWN"
  fi
}

put_back() {
  log "PUTTING BACK latitude's tunnel connector: database link healthy ($1 ms median)"
  if run kubectl -n mizan scale deploy/tunnel --replicas=1 >/dev/null; then
    [ "$DRY_RUN" = 1 ] || rm -f "$DOWN"
    alert "Mizan: latitude is back in the tunnel" "The link to homie's database has answered in under ${FAST_MS} ms for $((FAST_CYCLES * INTERVAL)) seconds. latitude's tunnel connector is scaled back to 1."
  fi
}

if [ "${1:-}" = --once ]; then
  ms=$(probe); cur=$(replicas)
  verdict="healthy"; [ "$ms" -ge "$SLOW_MS" ] && verdict="SLOW"
  log "link to $TARGET: ${ms} ms ($verdict; slow >= ${SLOW_MS}, good <= ${FAST_MS}); tunnel replicas: ${cur:-?}; guard has it out: $([ -f "$DOWN" ] && echo yes || echo no); promoted: $([ -f "$PROMOTED" ] && echo yes || echo no); off switch: $([ -f "$OFF" ] && echo on || echo off)"
  exit 0
fi

log "guarding latitude's tunnel (every ${INTERVAL}s: out after ${SLOW_CYCLES} slow probes >= ${SLOW_MS} ms, back after ${FAST_CYCLES} good ones <= ${FAST_MS} ms)"
slow=0; fast=0
while true; do
  if [ -f "$OFF" ]; then slow=0; fast=0; sleep "$INTERVAL"; continue; fi
  if [ -f "$PROMOTED" ]; then   # latitude is the primary: its connector must serve
    [ -f "$DOWN" ] && [ "$(replicas)" = 0 ] && put_back "promoted"
    slow=0; fast=0; sleep "$INTERVAL"; continue
  fi
  ms=$(probe); cur=$(replicas)
  if [ -z "$cur" ]; then log "cannot read the tunnel deployment (cluster API?)"; sleep "$INTERVAL"; continue; fi
  [ "$cur" != 0 ] && [ -f "$DOWN" ] && [ "$DRY_RUN" != 1 ] && rm -f "$DOWN"   # someone (a release, a person) already put it back
  if [ "$ms" -ge "$SLOW_MS" ]; then slow=$((slow + 1)); fast=0
  elif [ "$ms" -le "$FAST_MS" ]; then fast=$((fast + 1)); slow=0
  else slow=0; fast=0; fi
  if [ "$cur" != 0 ] && [ "$slow" -ge "$SLOW_CYCLES" ]; then take_out "$ms"; slow=0; fi
  if [ "$cur" = 0 ] && [ -f "$DOWN" ] && [ "$fast" -ge "$FAST_CYCLES" ]; then put_back "$ms"; fast=0; fi
  sleep "$INTERVAL"
done
