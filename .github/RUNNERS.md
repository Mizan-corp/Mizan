# Where GitHub Actions run

The repository is public and has **no self-hosted runners** (removed 2026-11-26: a self-hosted
runner on a public repository is a risk, and homie must not run GitHub jobs). All workflows use
GitHub-hosted runners (`ubuntu-latest`); fork pull-request workflows are disabled.

| Workflow | Triggers |
|---|---|
| `ci.yml` | push to master/main, tags `v*`, pull requests to master/main, manual |
| `installers.yml` | tags `v*`, pull requests touching installer paths, manual |
| `deploy-server.yml` | manual only, and it only prints a notice: deploys are done by hand, see `docs/deploy-homie.md` |
| `jobs.yml` | manual only. It still says `runs-on: homie`, which no longer exists, so it will queue forever until re-pointed (scheduled jobs run from systemd timers on homie, see `deploy/server/README.md`) |

`.github/ci-deps.sh` keeps its cache under `$MIZAN_CI_CACHE`, defaulting to `$RUNNER_TEMP/ci-cache`;
a hosted runner starts clean every run, so a CI run installs everything cold.
