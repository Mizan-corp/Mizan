#!/bin/sh
# Release a commit on the self-hosted server: back up, migrate, then switch the API and the apps.
#   deploy.sh <tag>   (images ghcr.io/mizan-corp/mizan-{api,web}:<tag>; pulled if not here,
#                      which needs `docker login ghcr.io`; or load them first with docker load)
# Run by hand over SSH: see docs/deploy-homie.md. No GitHub workflow runs it.
# A failed migration stops here: the running code keeps the old schema it works with.
set -eu
TAG="$1"
cd /srv/mizan
if [ -f /var/lib/mizan/fenced ]; then
  # latitude took over the database (deploy/failover): this copy is stale; never migrate or serve it.
  echo "homie is fenced ($(cat /var/lib/mizan/fenced)): not releasing. See deploy/failover/README.md." >&2
  exit 1
fi
for repo in mizan-api mizan-web; do
  docker image inspect "ghcr.io/mizan-corp/$repo:$TAG" >/dev/null 2>&1 || docker pull -q "ghcr.io/mizan-corp/$repo:$TAG"
done

echo "== backup"
/srv/mizan/backup.sh

echo "== migrate $TAG"
MIZAN_TAG="$TAG" docker compose run --rm --no-deps -T \
  -e MIZAN_PROD_DATABASE_URL="postgresql://mizan:$(sed -n 's/^POSTGRES_PASSWORD=//p' mizan.env)@postgres:5432/mizan" \
  api python manage.py db migrate --production --yes --no-backup

echo "== deploy $TAG"
PREV=$(sed -n 's/^MIZAN_TAG=//p' .env 2>/dev/null || true)
echo "MIZAN_TAG=$TAG" > .env
docker compose up -d --remove-orphans
for i in $(seq 1 60); do
  if curl -fsS -H "Host: api.allmizan.live" http://127.0.0.1:18000/api/health >/dev/null 2>&1; then
    echo "Deployed $TAG (rollback: deploy.sh ${PREV:-none})"
    # Keep this release and the previous one; the API image is ~1 GB.
    for repo in mizan-api mizan-web; do
      docker images "ghcr.io/mizan-corp/$repo" --format '{{.Tag}}' | grep -vxF -e "$TAG" -e "${PREV:-$TAG}" |
        while read -r old; do docker rmi "ghcr.io/mizan-corp/$repo:$old" >/dev/null || true; done
    done
    docker image prune -f >/dev/null
    exit 0
  fi
  sleep 5
done
echo "The API isn't healthy after the deploy; logs:" >&2
docker compose logs --tail=40 api >&2
exit 1
