# Where GitHub Actions run

GitHub's hosted minutes for this private repository are limited (2,000 a month on the free plan,
with a $0 spending limit: past them, jobs don't start until the month resets; that happened on
2026-11-14). So the regular work runs on Mizan's own machines, which cost nothing:

| Runner | Labels | Runs | Where |
|---|---|---|---|
| `latitude-ci` | `self-hosted, ci, latitude` | CI (`ci.yml`), the release's "wait for CI" step | latitude-e6530 (Tailscale), `~/mizan-runner`: the runner in an Ubuntu 22.04 container with its own Docker (dind), so CI's ports never touch the laptop's containers |
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

**Uptime** isn't a GitHub workflow: checking every 5 minutes would use the free minutes several
times over. It runs as a Cloudflare Worker (ADR-011).

**homie's runner has only the label `homie`** (it was registered without the default `self-hosted`, `Linux`
and `X64` labels). A job asking for `[self-hosted, homie]` matches no runner and waits in the queue
forever, with no error. Use `runs-on: homie`. The scheduled jobs were stuck this way from 14 to 16 Nov 2026.
