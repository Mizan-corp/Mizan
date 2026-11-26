#!/usr/bin/env bash
# Inside the runner container (called by runner.sh register / unregister on the host):
#   register.sh add      RUNNER_TOKEN=<registration token> RUNNER_NAME=... RUNNER_LABELS=a,b
#   register.sh remove   RUNNER_TOKEN=<remove token>
# The token is passed only to this one `docker exec`; it is never stored.
set -euo pipefail
cd /actions-runner
STATE=/runner-state
: "${RUNNER_TOKEN:?RUNNER_TOKEN is required}"
REPO_URL="${REPO_URL:-https://github.com/mizan-corp/Mizan}"

case "${1:-}" in
  add)
    ./config.sh --unattended --replace --url "$REPO_URL" --token "$RUNNER_TOKEN" \
      --name "${RUNNER_NAME:?}" --labels "${RUNNER_LABELS:?}" --work /runner-work
    cp -a .runner .credentials .credentials_rsaparams "$STATE/"
    echo "registered; the entrypoint starts the runner"
    ;;
  remove)
    cp -a "$STATE/.runner" "$STATE/.credentials" "$STATE/.credentials_rsaparams" . 2>/dev/null || :
    ./config.sh remove --token "$RUNNER_TOKEN"
    rm -f "$STATE/.runner" "$STATE/.credentials" "$STATE/.credentials_rsaparams"
    echo "removed from GitHub"
    ;;
  *) echo "usage: register.sh add|remove" >&2; exit 2 ;;
esac
