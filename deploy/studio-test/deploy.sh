#!/usr/bin/env bash
# Fail-closed deploy for the isolated Studio test host.
#
# Every step aborts the deploy on failure (set -euo pipefail), including the
# static-manifest guard - which must never be piped through tail/head on its
# verdict line. Entry HTML files are checked for RELATIVE asset refs before
# packaging: a relative ref means the bundle was built without its required
# base (studio -> /studio/, erp -> /erp/, preview -> /) and the deploy stops.
#
# This script deploys ONLY to the separately approved isolated test project.
# It never touches production, never runs migrations, never spends money.
#
# Usage:
#   deploy/studio-test/deploy.sh --repo /path/to/checkout --token-file /path/to/token
#   [--skip-build] [--studio-build DIR] [--erp-build DIR] [--augment-static DIR] [--output DIR]
set -euo pipefail

REPO=""
TOKEN_FILE=""
SKIP_BUILD=0
STUDIO_BUILD=/tmp/build-preview
ERP_BUILD=/tmp/mizan-erp-build
AUGMENT_STATIC=/tmp/mizan-package-fix/static
OUTPUT=""

while [ $# -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2;;
    --token-file) TOKEN_FILE="$2"; shift 2;;
    --skip-build) SKIP_BUILD=1; shift;;
    --studio-build) STUDIO_BUILD="$2"; shift 2;;
    --erp-build) ERP_BUILD="$2"; shift 2;;
    --augment-static) AUGMENT_STATIC="$2"; shift 2;;
    --output) OUTPUT="$2"; shift 2;;
    *) echo "unknown argument: $1" >&2; exit 2;;
  esac
done

[ -n "$REPO" ] || { echo "--repo is required" >&2; exit 2; }
[ -n "$TOKEN_FILE" ] || { echo "--token-file is required" >&2; exit 2; }
[ -f "$TOKEN_FILE" ] || { echo "token file not found: $TOKEN_FILE" >&2; exit 2; }
[ -d "$REPO" ] || { echo "repo not found: $REPO" >&2; exit 2; }

if [ "$SKIP_BUILD" -eq 0 ]; then
  echo "== build: studio preview (root entry)"
  rm -rf "$STUDIO_BUILD"
  (cd "$REPO/system/erp/frontend" && npx vite build --config vite.preview.config.ts --outDir "$STUDIO_BUILD")

  echo "== build: studio app (base /studio/, hosted api /api)"
  rm -rf /tmp/build-studio
  # Hosted build: without VITE_STUDIO_API the editor ships in local-prototype
  # mode and backend save/load silently disappears on the deployment.
  (cd "$REPO/system/erp/frontend" && VITE_STUDIO_API=/api VITE_STUDIO_BASE=/studio/ npx vite build --config vite.studio.config.ts --base=/studio/ --outDir /tmp/build-studio)
  node "$REPO/scripts/check-studio-hosted-build.mjs" /tmp/build-studio

  echo "== build: erp (base /erp/, api /api)"
  rm -rf "$ERP_BUILD"
  (cd "$REPO/system/erp/frontend" && VITE_API_URL=/api VITE_BASE=/erp/ VITE_WEBSITE_URL=https://mizan-studio-feature-test.vercel.app/erp VITE_SYSTEM_URL=https://mizan-studio-feature-test.vercel.app/erp VITE_OWNER_URL=https://mizan-studio-feature-test.vercel.app/erp/c/studio-test VITE_ADMIN_URL=https://mizan-studio-feature-test.vercel.app/erp  npx vite build --outDir "$ERP_BUILD")
fi

echo "== verify: entry HTML carries no relative asset refs (build base check)"
verify_entry() {
  # $1 = html file, $2 = required absolute base prefix
  local html="$1" base="$2" bad
  [ -f "$html" ] || { echo "entry missing: $html" >&2; exit 1; }
  bad=$(grep -oE '(src|href)="(assets/[^"]+)"' "$html" || true)
  if [ -n "$bad" ]; then
    echo "DEPLOY BLOCKED: $html has relative asset refs; rebuild its entry with base $base:" >&2
    echo "$bad" >&2
    exit 1
  fi
  grep -q "\"$base" "$html" || { echo "DEPLOY BLOCKED: $html does not reference base $base; wrong build base?" >&2; exit 1; }
  echo "ok: $html uses base $base"
}
verify_entry "$STUDIO_BUILD/studio-preview.html" "/assets/"
verify_entry /tmp/build-studio/studio.html "/studio/assets/"
verify_entry "$ERP_BUILD/index.html" "/erp/"

[ -d "$AUGMENT_STATIC" ] || { echo "augment static dir not found: $AUGMENT_STATIC" >&2; exit 2; }

if [ -z "$OUTPUT" ]; then
  OUTPUT=$(mktemp -d /tmp/mizan-package.XXXXXX)
  rmdir "$OUTPUT"  # package.py refuses an existing output directory
fi

echo "== package"
python3 "$REPO/deploy/studio-test/package.py" --repo "$REPO" \
  --studio-build "$STUDIO_BUILD" --erp-build "$ERP_BUILD" --output "$OUTPUT"

echo "== augment static (studio app + admin/owner/website frontends)"
mkdir -p "$OUTPUT/static/studio"
cp -r /tmp/build-studio/. "$OUTPUT/static/studio/"
for app in admin owner website; do
  mkdir -p "$OUTPUT/static/$app"
  cp -r "$AUGMENT_STATIC/$app/." "$OUTPUT/static/$app/"
done

echo "== prune stale hashed assets"
node "$REPO/scripts/prune-static-assets.mjs" "$OUTPUT/static"

echo "== static manifest guard (fail-closed; verdict never piped)"
node "$REPO/scripts/check-static-manifest.mjs" "$OUTPUT/static"

if [ ! -d "$OUTPUT/.vercel" ]; then
  [ -d /tmp/vercel-proj/.vercel ] || { echo "linked .vercel dir not found at /tmp/vercel-proj/.vercel" >&2; exit 2; }
  cp -r /tmp/vercel-proj/.vercel "$OUTPUT/"
fi

echo "== deploy (vercel --prod, isolated test project)"
(cd "$OUTPUT" && npx vercel deploy --prod --yes --token "$(cat "$TOKEN_FILE")")

echo "== done"
