#!/usr/bin/env bash
# Inside the runner container: start its own Docker daemon, then the GitHub runner (once it is
# registered: runner.sh register). Stops both cleanly on `docker stop`.
set -euo pipefail

RUNNER_DIR=/actions-runner
STATE=/runner-state   # the registration (.runner, .credentials*), kept across re-creations
log() { echo "[entrypoint] $*"; }

# cgroup v2: move this container's processes into a child group so the inner daemon can create
# its own groups (as docker:dind does). Everything stays under this container's limits.
if [ -f /sys/fs/cgroup/cgroup.controllers ]; then
  mkdir -p /sys/fs/cgroup/init
  xargs -rn1 < /sys/fs/cgroup/cgroup.procs > /sys/fs/cgroup/init/cgroup.procs 2>/dev/null || :
  sed -e 's/ / +/g' -e 's/^/+/' < /sys/fs/cgroup/cgroup.controllers \
    > /sys/fs/cgroup/cgroup.subtree_control 2>/dev/null || :
fi

# Leftovers from the previous start of this same container.
rm -rf /run/docker.pid /run/docker.sock /run/docker /run/containerd

log "starting dockerd"
dockerd > >(sed -u 's/^/[dockerd] /') 2>&1 &
DOCKERD_PID=$!
for _ in $(seq 1 60); do docker info >/dev/null 2>&1 && break; sleep 1; done
docker info >/dev/null 2>&1 || { log "dockerd did not start"; exit 1; }
log "dockerd up ($(docker version --format '{{.Server.Version}}'))"

RUNNER_PID=""
stop() {
  log "stopping"
  if [ -n "$RUNNER_PID" ] && kill -0 "$RUNNER_PID" 2>/dev/null; then
    # run.sh (RUNNER_MANUALLY_TRAP_SIG) passes it on to the listener as SIGINT: it ends its
    # session and exits; a running job is cancelled.
    kill -TERM "$RUNNER_PID" 2>/dev/null || :
    wait "$RUNNER_PID" 2>/dev/null || :
  fi
  kill -TERM "$DOCKERD_PID" 2>/dev/null || :
  wait "$DOCKERD_PID" 2>/dev/null || :
  exit 0
}
trap stop TERM INT

# Runner diagnostics grow with every job; keep a week.
find "$RUNNER_DIR/_diag" -type f -mtime +7 -delete 2>/dev/null || :

n=0
until [ -f "$STATE/.runner" ]; do
  [ $((n % 60)) -eq 0 ] && log "not registered yet: on the host, run .github/runner-image/runner.sh register"
  n=$((n + 1)); sleep 1 & wait $! || :
done
cp -a "$STATE/.runner" "$STATE/.credentials" "$STATE/.credentials_rsaparams" "$RUNNER_DIR/"

log "starting the runner"
cd "$RUNNER_DIR"
set -m   # job control: the runner must not inherit "ignore SIGINT" (see stop)
./run.sh &
RUNNER_PID=$!
set +m
wait "$RUNNER_PID" || :
log "runner exited"
stop
