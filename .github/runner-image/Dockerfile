# A self-contained CI runner (.github/RUNNERS.md): the GitHub Actions runner and its own Docker
# daemon in one container, so the jobs' compose project, ports and `pkill` stay inside it.
# Built and run on the host by runner.sh (next to this file); nothing secret goes in the image.
FROM ubuntu:24.04

ARG RUNNER_VERSION=2.338.2
ENV DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8 LC_ALL=C.UTF-8

# Base tools, build tools, Python (system, for scripts; CI's own Pythons come from uv via
# ci-deps.sh) and WeasyPrint's libraries (the same as deploy/server/Dockerfile.api).
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl wget gnupg git jq sudo tini iptables iproute2 procps psmisc kmod \
      xz-utils zstd unzip zip rsync openssh-client less \
      build-essential pkg-config libpq-dev libffi-dev libssl-dev \
      python3 python3-venv python3-pip python3-dev \
      libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
      shared-mime-info fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

# Docker Engine + buildx + compose: the daemon runs inside this container (entrypoint.sh).
RUN install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu noble stable" \
       > /etc/apt/sources.list.d/docker.list \
    && apt-get update && apt-get install -y --no-install-recommends \
      docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/*

# Chromium's system libraries for the browser flows (Playwright), installed once here so
# ci-deps.sh finds them; it then only keeps the browser itself in the cache volume.
RUN python3 -m venv /tmp/pw && /tmp/pw/bin/pip install -q playwright \
    && /tmp/pw/bin/playwright install-deps chromium \
    && rm -rf /tmp/pw /var/lib/apt/lists/* /root/.cache \
    && mkdir -p /var/lib/mizan-ci \
    && touch /var/lib/mizan-ci/playwright-deps /var/lib/mizan-ci/weasyprint-deps

# The GitHub Actions runner (it updates itself in place when GitHub releases a new one).
RUN mkdir -p /actions-runner && cd /actions-runner \
    && curl -fsSL "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz" \
       | tar -xz \
    && ./bin/installdependencies.sh >/dev/null \
    && rm -rf /var/lib/apt/lists/*

COPY daemon.json /etc/docker/daemon.json
COPY entrypoint.sh register.sh /usr/local/bin/

# Jobs run as root (ci-deps.sh installs packages with apt), as on latitude.
ENV RUNNER_ALLOW_RUNASROOT=1 RUNNER_MANUALLY_TRAP_SIG=1 MIZAN_CI_CACHE=/runner-cache
VOLUME ["/var/lib/docker", "/runner-work", "/runner-cache", "/runner-state"]
STOPSIGNAL SIGTERM
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
