# Deploying to homie (allmizan.live)

Production runs on `homie` (see `deploy/server/README.md`). There is **no GitHub runner on homie**.
A release is a manual GitHub Actions run on a hosted runner that builds the images and then
connects to homie over SSH with a restricted key. Nothing else deploys: no push, pull request
or schedule trigger. Vercel hosts only the isolated test site (`deploy/studio-test`), never production.

## How a release works

Actions > **Deploy (homie)** > Run workflow (`.github/workflows/deploy-server.yml`, `workflow_dispatch` only).

1. `build` (hosted runner): builds `mizan-api` and `mizan-web`, pushes them to GHCR tagged with the commit.
2. `deploy` (hosted runner): waits until a **required reviewer** approves the `production` Environment,
   then runs `ssh mizan-deploy@<homie> "deploy <commit sha>"`, sending the job's short-lived
   `GITHUB_TOKEN` on stdin.
3. On homie the forced command logs in to GHCR with that token, then runs `/srv/mizan/deploy.sh <sha>`:
   back up, migrate, switch, health check. A failed migration leaves the running version untouched.

Run CI on the commit first; the workflow does not wait for it.

## The deploy identity (on homie)

| Thing | Value |
|---|---|
| User | `mizan-deploy`: no password (locked), not in `sudo` or `docker`. Password logins are impossible for it. |
| Key | ed25519, `authorized_keys` entry starts with `restrict,command="/usr/local/sbin/mizan-deploy-entry"`: no shell, no pty, no port or agent forwarding. |
| Forced command | `/usr/local/sbin/mizan-deploy-entry` (root-owned) accepts only `deploy <40 hex chars>`; anything else is refused. |
| Privilege | `/etc/sudoers.d/mizan-deploy` allows exactly one thing: run `/usr/local/sbin/mizan-deploy-run <sha>` as user `ammar` (who owns `/srv/mizan` and can use Docker). |
| Network | The existing public SSH port 22 (DuckDNS). Nothing new is exposed. Global `sshd` settings are unchanged. The host key is pinned in the workflow. |

Copies of the two scripts are in `deploy/server/mizan-deploy-entry` and `mizan-deploy-run`.

## GitHub settings

- Environment `production`: required reviewer (the owner), administrator bypass off, no wait timer.
- Environment secret `DEPLOY_SSH_KEY` (the private key). Only the `deploy` job, after approval, can read it.
- Environment variables `DEPLOY_HOST` and `DEPLOY_KNOWN_HOSTS` (the host's public key, not secret).
- Fork pull request workflows are disabled for the repository, and the deploy workflow has no PR trigger.
- Third-party actions are pinned to commit SHAs.

## Rotate or revoke the key

- Revoke now: on homie `sudo rm /home/mizan-deploy/.ssh/authorized_keys` (or `sudo passwd -l`/`userdel mizan-deploy`).
- Rotate: `ssh-keygen -t ed25519 -N '' -f key`, put `restrict,command="/usr/local/sbin/mizan-deploy-entry" <key.pub>` in
  `/home/mizan-deploy/.ssh/authorized_keys`, and replace the `DEPLOY_SSH_KEY` environment secret.

## Updating the scripts on homie

The release does not copy `compose.yaml` or `deploy.sh` to homie. When they change, copy by hand
as the owner: `scp deploy/server/{compose.yaml,deploy.sh,backup.sh,backup-offsite.sh,mizan-cron.sh} homie:/srv/mizan/`.
The two `mizan-deploy-*` scripts are installed once into `/usr/local/sbin` (root-owned, mode 755).

## Roll back

Manual run on homie as the owner: `/srv/mizan/deploy.sh <previous commit sha>` (the previous release's
images are kept; the script prints the tag). The database is not rolled back.

## Known limits

- A public SSH port that also accepts passwords for other users is the weak point of this setup; the deploy
  key cannot do anything but the forced command, but the port itself is exposed. Moving the deploy path
  to Tailscale is the documented alternative if that changes.
- Not yet run end to end for a real release; the first run needs the owner's approval in the Actions UI.
