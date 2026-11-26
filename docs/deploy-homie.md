# Deploying to homie (allmizan.live), by hand

Production runs on `homie` (see `deploy/server/README.md`). Deploys are **manual**. There is no
GitHub runner on homie, the repository is public, and no GitHub workflow deploys anything:
`.github/workflows/deploy-server.yml` is only a notice that fails if someone runs it. Hosted GitHub
runners and Vercel are never used for the real deploy (Vercel hosts the isolated test site only,
`deploy/studio-test`).

Only a person with SSH access to homie can release. Credentials stay in your password manager and
never go in this repository.

## Release a commit

Run from a machine with Docker, a checkout of the commit, and SSH access to homie (`ssh homie`).

```sh
SHA=$(git rev-parse HEAD)          # the commit to release; CI should be green on it first

# 1. Build the two images (any machine with Docker; homie is too small to build on).
docker build -f deploy/server/Dockerfile.api -t ghcr.io/mizan-corp/mizan-api:$SHA .
docker build -f deploy/server/Dockerfile.web -t ghcr.io/mizan-corp/mizan-web:$SHA .

# 2. Copy the images to homie (no registry login needed; deploy.sh uses images already present).
docker save ghcr.io/mizan-corp/mizan-api:$SHA ghcr.io/mizan-corp/mizan-web:$SHA | gzip | ssh homie 'gunzip | docker load'

# 3. Update the server's compose file and scripts.
scp deploy/server/{compose.yaml,deploy.sh,backup.sh,backup-offsite.sh,mizan-cron.sh} homie:/srv/mizan/

# 4. Release: back up, migrate, switch, wait for health.
ssh homie "/srv/mizan/deploy.sh $SHA"
```

`deploy.sh` stops if homie is fenced (`/var/lib/mizan/fenced`), takes a backup, runs the
migrations, switches `MIZAN_TAG` in `/srv/mizan/.env`, and checks the API health. A failed
migration leaves the running version untouched.

## Check

- `curl -s -o /dev/null -w '%{http_code}\n' https://allmizan.live/` returns 200.
- `ssh homie 'cat /srv/mizan/.env'` shows `MIZAN_TAG=<the commit>`.
- `ssh homie 'cd /srv/mizan && docker compose ps'` shows `api` as healthy.

## Roll back

`ssh homie '/srv/mizan/deploy.sh <previous commit>'`. The previous release's images are kept on
the server (the script prints the tag). The database is not rolled back; migrations must stay
compatible with the previous release.

## Status of these steps

The build, copy and release commands are the manual path that replaces the removed runner. The
`deploy.sh` part is the script production has used; the `docker save | ssh docker load` transfer
has not yet been run end to end for a full release. Try it with a non-production tag first.
