#!/usr/bin/env bash
# The workstation CI runner (.github/RUNNERS.md), run on the host from a checkout of this repo:
#
#   runner.sh build        build the image (mizan-ci-runner:latest) from this directory
#   runner.sh start        create the container (first time) or start it again
#   runner.sh register     register with GitHub (once; needs `gh` with admin on the repo)
#   runner.sh stop         stop it (a running job is cancelled; it stays stopped across reboots)
#   runner.sh status       container state, limits and GitHub's view of the runner
#   runner.sh logs         follow the runner's and its Docker daemon's output
#   runner.sh upgrade      rebuild the image and re-create the container (volumes kept)
#   runner.sh prune        free disk in the runner's own Docker (images, build cache)
#   runner.sh unregister   remove it from GitHub (then `register` again to re-register)
#   runner.sh shell        a shell inside it
#
# It never touches other containers: everything is addressed by the names below.
set -euo pipefail

NAME="${RUNNER_CONTAINER:-ci-runner-workstation}"   # container, network and volume prefix
IMAGE="${RUNNER_IMAGE:-mizan-ci-runner:latest}"
REPO="${RUNNER_REPO:-mizan-corp/Mizan}"
RUNNER_NAME="${RUNNER_NAME:-workstation-ci}"
RUNNER_LABELS="${RUNNER_LABELS:-ci,workstation}"     # plus the defaults self-hosted, Linux, X64
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Limits: never starve the workstation. CPU: at most 4 of 6 cores, and half the default weight
# when the machine is busy. Memory: 7 GB (+2 GB swap); the kernel's OOM killer picks it first.
LIMITS=(--cpus 4 --cpu-shares 512 --memory 7g --memory-swap 9g --oom-score-adj 500
        --pids-limit 8192 --shm-size 1g)

exists() { docker container inspect "$NAME" >/dev/null 2>&1; }

create() {
  docker network inspect "$NAME" >/dev/null 2>&1 || docker network create "$NAME" >/dev/null
  # --privileged: needed for its own Docker daemon. No published ports: CI's 8000-8003, 5433 and
  # 5173-5176 exist only in this container's network namespace.
  docker run -d --name "$NAME" --hostname "$NAME" --privileged \
    --network "$NAME" \
    --restart unless-stopped --stop-timeout 120 \
    "${LIMITS[@]}" \
    --log-driver json-file --log-opt max-size=10m --log-opt max-file=3 \
    -v "$NAME-docker:/var/lib/docker" \
    -v "$NAME-work:/runner-work" \
    -v "$NAME-cache:/runner-cache" \
    -v "$NAME-state:/runner-state" \
    "$IMAGE" >/dev/null
  echo "created $NAME"
}

case "${1:-}" in
  build)   docker build --pull -t "$IMAGE" "$HERE" ;;
  start)   if exists; then docker start "$NAME" >/dev/null && echo "started $NAME"; else create; fi ;;
  stop)    docker stop "$NAME" >/dev/null && echo "stopped $NAME" ;;
  logs)    docker logs -f --tail 200 "$NAME" ;;
  shell)   docker exec -it "$NAME" bash ;;
  prune)   docker exec "$NAME" docker system prune -af ;;
  register)
    token=$(gh api -X POST "repos/$REPO/actions/runners/registration-token" --jq .token)
    docker exec -e RUNNER_TOKEN="$token" -e RUNNER_NAME="$RUNNER_NAME" -e RUNNER_LABELS="$RUNNER_LABELS" \
      -e REPO_URL="https://github.com/$REPO" "$NAME" register.sh add
    ;;
  unregister)
    token=$(gh api -X POST "repos/$REPO/actions/runners/remove-token" --jq .token)
    docker exec -e RUNNER_TOKEN="$token" -e REPO_URL="https://github.com/$REPO" "$NAME" register.sh remove
    docker restart "$NAME" >/dev/null   # back to waiting for a registration
    ;;
  upgrade)
    docker build --pull -t "$IMAGE" "$HERE"
    if exists; then docker stop "$NAME" >/dev/null; docker rm "$NAME" >/dev/null; fi
    create
    ;;
  status)
    docker ps -a --filter "name=^${NAME}$" --format 'container: {{.Names}} {{.Status}}'
    docker inspect "$NAME" --format 'limits: cpus={{.HostConfig.NanoCpus}} shares={{.HostConfig.CpuShares}} mem={{.HostConfig.Memory}} swap={{.HostConfig.MemorySwap}} pids={{.HostConfig.PidsLimit}} restart={{.HostConfig.RestartPolicy.Name}}'
    docker stats --no-stream --format 'usage: cpu={{.CPUPerc}} mem={{.MemUsage}} pids={{.PIDs}}' "$NAME"
    gh api "repos/$REPO/actions/runners" --jq ".runners[] | select(.name==\"$RUNNER_NAME\") | \"github: \(.name) \(.status) busy=\(.busy) labels=\([.labels[].name] | join(\",\"))\""
    ;;
  *) sed -n '2,16p' "$0"; exit 2 ;;
esac
