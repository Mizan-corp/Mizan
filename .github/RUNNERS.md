# Where GitHub Actions run

GitHub's hosted minutes for this private repository are limited (2,000 a month on the free plan,
with a $0 spending limit: past them, jobs don't start until the month resets; that happened on
2026-11-14). So the regular work runs on Mizan's own machines, which cost nothing:

| Runner | Labels | Runs | Where |
|---|---|---|---|
| `latitude-ci` | `self-hosted, ci, latitude` | CI (`ci.yml`), the release's image builds | latitude-e6530 (Tailscale), `~/mizan-runner`: the runner in an Ubuntu 22.04 container with its own Docker (dind), so CI's ports never touch the laptop's containers |
| `workstation-ci` | `self-hosted, ci, workstation` | The same jobs as `latitude-ci`: whichever is free takes the next one | Ammar's workstation (i5-8400): the runner and its own Docker daemon in one container, built from `.github/runner-image/` (below) |
| `homie` | `homie` only | The release (`deploy-server.yml`), scheduled jobs (`jobs.yml`) | The production server, `/srv/actions-runner` |

GitHub-hosted runners remain only for the installers (`installers.yml`: Windows and macOS builds,
on tags).

**The CI runner** (`latitude-e6530:~/mizan-runner/compose.yaml`): `docker compose up -d` starts it,
`docker compose logs -f runner` follows it. It registered once with a token from
`gh api -X POST repos/mizan-corp/Mizan/actions/runners/registration-token` (kept in `runner.env`);
the registration is kept in a volume across restarts. If the laptop is off, CI waits until it is
back, and so does the release. Free disk now and then:
`docker compose exec dind docker system prune -af`.

**Dependencies are cached on the runner.** Each CI job starts with `.github/ci-deps.sh`, which
checks what the job needs and installs only what's missing or out of date, into the runner's
`ci-cache` volume (`/runner-cache`): Python (uv-managed), a virtualenv per dependency set keyed by
the hash of its requirement files (the shared kernel is then installed editable from the
checkout, so the cached venv never runs old code), Node.js, `node_modules` (checkout keeps it;
reinstalled from the warm npm cache when `package-lock.json` changes), Chromium and its system
libraries. A warm run spends about 2 seconds on this instead of minutes; Docker image layers are
cached in the runner's own Docker. A changed requirement file builds a new venv and drops the
old one. To start over: `docker compose down && docker volume rm mizan-runner_ci-cache`.

**The workstation runner** (`workstation-ci`) shares latitude's labels, so a job asking for
`[self-hosted, ci]` runs on whichever runner is free (a job that must run on one of them can add
`latitude` or `workstation`). The workstation also runs its own containers, including a local
Mizan stack under the same compose project name `mizan` and the same ports, and CI runs
`docker compose down -v`, publishes 8000-8003, 5433 and 5173-5176, and ends with `pkill -f vite`.
So the runner never runs on the host itself (a full CI run takes about 25 minutes there, like on
latitude; checked on 2026-11-23, including the release's image builds):

- **Isolated:** one privileged container, `ci-runner-workstation` (image `mizan-ci-runner`,
  Ubuntu 24.04), with its own Docker daemon inside (`dockerd` started by `entrypoint.sh`). CI's
  compose project, its volumes and images live in that inner daemon; `localhost:8000` in a job is
  the container's own network namespace; `pkill` sees only the container's processes. The
  container publishes no ports and sits on its own bridge network (`ci-runner-workstation`); the
  inner daemon uses 10.213.0.0/24 and 10.214.0.0/16, apart from the host's Docker networks.
  Privileged is what a Docker daemon inside needs: the isolation is from the host's containers,
  ports and processes, not a security boundary against the jobs, which only come from this repo.
- **Limited:** at most 4 of the 6 cores (`--cpus 4`) and half the default CPU weight
  (`--cpu-shares 512`), so the workstation's own work wins when it's busy; 7 GB of memory + 2 GB
  swap; 8192 processes; 1 GB `/dev/shm` for Chromium; `--oom-score-adj 500`, so under memory pressure
  the kernel stops CI first. The inner containers count against the same limits (they live in the
  container's cgroup). One job at a time (one runner).
- **Persistent:** volumes `ci-runner-workstation-docker` (`/var/lib/docker`: image layers, so
  `docker compose up --build` stays fast), `-work` (checkouts; `node_modules` kept), `-cache`
  (`/runner-cache`, as on latitude) and `-state` (the registration). Logs rotate (10 MB × 3, for
  the container and inside); runner diagnostics older than a week are deleted at start.
- **Always on:** `--restart unless-stopped`, and Docker starts at boot, so it comes back after a
  reboot or a crash, unless someone stopped it on purpose.
- **No secrets stored:** the registration token is fetched with `gh` and handed to a single
  `docker exec`; GitHub's runner credentials stay in the `-state` volume.

Run it on the workstation with `.github/runner-image/runner.sh` from any checkout (a copy of that
directory is also kept in `~/mizan-ci-runner`):

| | |
|---|---|
| First setup | `runner.sh build && runner.sh start && runner.sh register` |
| Stop / start | `runner.sh stop` (a running job is cancelled; it then stays off across reboots) / `runner.sh start` |
| State, limits, GitHub's view | `runner.sh status`; `runner.sh logs` follows the runner and its daemon |
| Upgrade the image (base, Docker, deps) | `runner.sh upgrade`: rebuilds, re-creates the container, keeps the volumes and the registration. Bump `RUNNER_VERSION` in the Dockerfile now and then; the runner also updates itself in place |
| Re-register (new name or labels, or after removing it on GitHub) | `runner.sh unregister`, then `runner.sh register` (`RUNNER_NAME`, `RUNNER_LABELS` override the defaults `workstation-ci`, `ci,workstation`) |
| Free disk | `runner.sh prune` (its own Docker only) |
| Remove completely | `runner.sh unregister && runner.sh stop && docker rm ci-runner-workstation`, then `docker volume rm` the four `ci-runner-workstation-*` volumes and `docker network rm ci-runner-workstation` |

Never use `docker compose` in the checkout on the host to manage it: that's the local stack.

**Uptime** isn't a GitHub workflow: checking every 5 minutes would use the free minutes several
times over. It runs as a Cloudflare Worker (ADR-011).

**homie's runner has only the label `homie`** (it was registered without the default `self-hosted`, `Linux`
and `X64` labels). A job asking for `[self-hosted, homie]` matches no runner and waits in the queue
forever, with no error. Use `runs-on: homie`. The scheduled jobs were stuck this way from 14 to 16 Nov 2026.
