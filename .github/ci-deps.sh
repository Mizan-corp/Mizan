#!/usr/bin/env bash
# CI dependencies on our own runner (.github/RUNNERS.md): check what's there, install only what's
# missing, from a cache that survives between runs ($MIZAN_CI_CACHE, a volume on the runner).
#
#   bash .github/ci-deps.sh python=3.13 py=backend
#   bash .github/ci-deps.sh node=24 npm
#   bash .github/ci-deps.sh python=3.12 py=e2e node=22 npm playwright
#
#   python=X   Python X (uv-managed, cached)
#   py=SET     a virtualenv for SET (backend | e2e), cached by the hash of its requirement
#              files; the shared kernel is installed editable from this checkout every run (fast)
#   node=X     Node.js X (latest of that major, cached)
#   npm        node_modules from package-lock.json, through a warm npm cache (--prefer-offline)
#   playwright Chromium for the browser flows, and its system libraries (once per container)
#   weasyprint WeasyPrint's system libraries and Arabic fonts, for PDFs (once per container)
#
# Puts the tools on PATH for the next steps ($GITHUB_PATH, $GITHUB_ENV) and prints what it found
# or installed, with the time each part took.
set -euo pipefail

CACHE="${MIZAN_CI_CACHE:-${RUNNER_TEMP:-/tmp}/ci-cache}"   # hosted runners: fresh each run; self-hosted can set MIZAN_CI_CACHE
mkdir -p "$CACHE/bin" "$CACHE/markers"
SUDO=""; [ "$(id -u)" = 0 ] || SUDO="sudo -E"   # hosted runners: non-root user with sudo
export PATH="$CACHE/bin:$PATH"
export UV_CACHE_DIR="$CACHE/uv-cache" UV_PYTHON_INSTALL_DIR="$CACHE/python" UV_LINK_MODE=copy
export npm_config_cache="$CACHE/npm"
export PLAYWRIGHT_BROWSERS_PATH="$CACHE/ms-playwright"
gh_path() { [ -n "${GITHUB_PATH:-}" ] && echo "$1" >> "$GITHUB_PATH"; export PATH="$1:$PATH"; }
gh_env()  { [ -n "${GITHUB_ENV:-}" ] && echo "$1=$2" >> "$GITHUB_ENV"; export "$1=$2"; }
gh_env npm_config_cache "$npm_config_cache"
gh_env PLAYWRIGHT_BROWSERS_PATH "$PLAYWRIGHT_BROWSERS_PATH"

say() { printf '%-12s %s\n' "$1" "$2"; }
timed() { local t0=$SECONDS; "$@"; echo "   ($(( SECONDS - t0 ))s)"; }

ensure_uv() {
  if command -v uv >/dev/null; then say uv "cached ($(uv --version | cut -d' ' -f2))"; return; fi
  say uv "installing"
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$CACHE/bin" UV_NO_MODIFY_PATH=1 sh >/dev/null
}

PY=""
ensure_python() {
  ensure_uv
  if uv python find "$1" >/dev/null 2>&1; then say python "$1 cached"; else say python "$1 installing"; timed uv python install "$1" >/dev/null; fi
  PY="$1"
}

ensure_venv() {  # $1 = backend | e2e
  local files
  case "$1" in
    backend) files="shared/backend/pyproject.toml" ;;
    e2e)     files="shared/backend/pyproject.toml shared/backend/requirements-dev.txt e2e/requirements.txt" ;;
    *) echo "unknown py set: $1" >&2; exit 2 ;;
  esac
  local key; key=$(cat $files | sha256sum | cut -c1-16)
  local venv="$CACHE/venv/$1-py$PY-$key"
  if [ -x "$venv/bin/python" ]; then
    say "venv $1" "cached ($key)"
  else
    say "venv $1" "building ($key)"
    rm -rf "$venv.tmp"
    uv venv -q -p "$PY" "$venv.tmp"
    local t0=$SECONDS
    case "$1" in
      backend) VIRTUAL_ENV="$venv.tmp" uv pip install -q ./shared/backend ruff ;;
      e2e)     VIRTUAL_ENV="$venv.tmp" uv pip install -q ./shared/backend -r shared/backend/requirements-dev.txt \
                                                     -r e2e/requirements.txt httpx ;;
    esac
    echo "   ($(( SECONDS - t0 ))s)"
    mv "$venv.tmp" "$venv"
    # Old venvs of this set (another hash): keep the cache from growing without bound.
    find "$CACHE/venv" -maxdepth 1 -name "$1-py$PY-*" ! -name "$(basename "$venv")" -exec rm -rf {} + 2>/dev/null || true
  fi
  # This checkout's own code: editable, so a cached venv never runs yesterday's kernel.
  VIRTUAL_ENV="$venv" uv pip install -q --no-deps -e ./shared/backend
  gh_path "$venv/bin"
  gh_env VIRTUAL_ENV "$venv"
}

ensure_node() {  # $1 = major
  local dir; dir=$(ls -d "$CACHE"/node/node-v"$1".*-linux-x64 2>/dev/null | sort -V | tail -1 || true)
  if [ -z "$dir" ]; then
    local version
    version=$(curl -fsS https://nodejs.org/dist/index.json | python3 -c "import json,sys; print(next(r['version'] for r in json.load(sys.stdin) if r['version'].startswith('v$1.')))")
    say node "$version installing"
    mkdir -p "$CACHE/node"
    curl -fsS "https://nodejs.org/dist/$version/node-$version-linux-x64.tar.xz" | tar -xJ -C "$CACHE/node"
    dir="$CACHE/node/node-$version-linux-x64"
  else
    say node "$(basename "$dir" | cut -d- -f2) cached"
  fi
  gh_path "$dir/bin"
}

ensure_npm() {
  local key; key=$(sha256sum package-lock.json | cut -c1-16)
  if [ -f node_modules/.mizan-lock ] && [ "$(cat node_modules/.mizan-lock)" = "$key" ]; then
    say npm "node_modules current ($key)"; return
  fi
  say npm "npm ci ($key, from the cache)"
  timed npm ci --prefer-offline --no-audit --fund=false --loglevel=error
  echo "$key" > node_modules/.mizan-lock
}

ensure_playwright() {
  # The browser: in the cache volume. Its system libraries: in this container (root, apt).
  if ls "$PLAYWRIGHT_BROWSERS_PATH"/chromium-* >/dev/null 2>&1; then say chromium cached; else
    say chromium installing; timed python -m playwright install chromium >/dev/null; fi
  if [ -f $CACHE/markers/playwright-deps ]; then say "chromium libs" present; else
    say "chromium libs" installing
    timed $SUDO env "PATH=$PATH" python -m playwright install-deps chromium >/dev/null
    touch $CACHE/markers/playwright-deps
  fi
}

ensure_weasyprint() {
  # The same libraries as the server image (deploy/server/Dockerfile.api).
  if [ -f $CACHE/markers/weasyprint-deps ]; then say "pdf libs" present; return; fi
  say "pdf libs" installing
  local t0=$SECONDS
  $SUDO env DEBIAN_FRONTEND=noninteractive apt-get update -qq >/dev/null
  $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
    shared-mime-info fonts-noto-core >/dev/null
  echo "   ($(( SECONDS - t0 ))s)"
  touch $CACHE/markers/weasyprint-deps
}

echo "CI dependencies (cache: $CACHE)"
for arg in "$@"; do
  case "$arg" in
    python=*) ensure_python "${arg#python=}" ;;
    py=*)     ensure_venv "${arg#py=}" ;;
    node=*)   ensure_node "${arg#node=}" ;;
    npm)      ensure_npm ;;
    playwright) ensure_playwright ;;
    weasyprint) ensure_weasyprint ;;
    *) echo "unknown: $arg" >&2; exit 2 ;;
  esac
done
