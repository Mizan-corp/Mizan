# Runners

There are **no self-hosted runners** for this repository (checked 27 November 2026: the repository
has 0 registered runners). Every workflow runs on GitHub-hosted runners, which are free for a public
repository.

| Workflow | Runner | Trigger |
| --- | --- | --- |
| `ci.yml` | `ubuntu-latest` | push, pull request, manual |
| `installers.yml` | `ubuntu-latest`, Windows and macOS (matrix) | push, pull request, manual |
| `deploy-server.yml` ("Deploy (homie)") | `ubuntu-latest` | **manual only**; the `deploy` job waits for a required reviewer on the `production` Environment, then SSHes to homie with a restricted key (see `docs/deploy-homie.md`) |
| `jobs.yml` | `ubuntu-latest` | manual only |

A push to `master` does not deploy. A release is always a manual run that the owner approves.

`.github/runner-image/` and `.github/ci-deps.sh` come from the earlier self-hosted design. The
dependency script still works on hosted runners (it installs what is missing); the runner image is
unused and can be deleted later.

If a self-hosted runner is ever registered again, change `runs-on` for the jobs that should use it,
and keep the deploy job on a hosted runner so the deploy key stays behind the `production` approval.
