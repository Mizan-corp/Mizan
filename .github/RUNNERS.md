# Where GitHub Actions run

GitHub's hosted minutes for this private repository are limited (2,000 a month on the free plan,
with a $0 spending limit: past them, jobs don't start until the month resets; that happened on
2026-11-14). So the regular work runs on Mizan's own machines, which cost nothing:

| Runner | Labels | Runs | Where |
|---|---|---|---|
| `latitude-ci` | `self-hosted, ci, latitude` | CI (`ci.yml`), the release's "wait for CI" step | latitude-e6530 (Tailscale), `~/mizan-runner`: the runner in an Ubuntu 22.04 container with its own Docker (dind), so CI's ports never touch the laptop's containers |
| `homie` | `self-hosted, homie` | The release (`deploy-server.yml`), scheduled jobs (`jobs.yml`) | The production server, `/srv/actions-runner` |

GitHub-hosted runners remain only for the installers (`installers.yml`: Windows and macOS builds,
on tags).

**The CI runner** (`latitude-e6530:~/mizan-runner/compose.yaml`): `docker compose up -d` starts it,
`docker compose logs -f runner` follows it. It registered once with a token from
`gh api -X POST repos/ammar0xff/Mizan/actions/runners/registration-token` (kept in `runner.env`);
the registration is kept in a volume across restarts. If the laptop is off, CI waits until it is
back, and so does the release. Free disk now and then:
`docker compose exec dind docker system prune -af`.

**Uptime** isn't a GitHub workflow: checking every 5 minutes would use the free minutes several
times over. It runs as a Cloudflare Worker (ADR-011).
