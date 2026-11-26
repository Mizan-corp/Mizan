"""Build only, no upload. Existing project production env files are not modified."""
import argparse
import os
from pathlib import Path
import subprocess
from urllib.parse import urlparse

p = argparse.ArgumentParser()
p.add_argument("--repo", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
p.add_argument("--origin", required=True)
a = p.parse_args()
u = urlparse(a.origin)
if u.scheme != "https" or u.hostname != "mizan-studio-feature-test.vercel.app" or u.path not in ("", "/") or u.username or u.password or u.query or u.fragment or u.port:
    raise SystemExit("Only the existing isolated HTTPS test origin is supported.")
origin = a.origin.rstrip("/")
if a.output.exists():
    raise SystemExit("Use a fresh output directory.")
for kind in ("owner", "admin", "website"):
    env = {**os.environ, "VITE_APP_KIND": kind, "VITE_BASE": f"/{kind}/",
           "VITE_API_URL": ("/website-api" if kind == "website" else f"/{kind}-api"), "VITE_SYSTEM_API_URL": "/api",
           "VITE_OWNER_API_URL": "/owner-api", "VITE_DEV_PORTAL_URL": origin + "/website/dev", "VITE_WORKSPACE_DOMAIN": "",
           "VITE_WEBSITE_URL": origin + "/website", "VITE_SYSTEM_URL": origin + "/erp",
           "VITE_OWNER_URL": origin + "/owner", "VITE_ADMIN_URL": origin + "/admin"}
    subprocess.run(["npx", "vite", "build", "--outDir", str(a.output.resolve()/kind)],
                   cwd=a.repo/kind/"frontend", env=env, check=True)
# Hosted Studio editor (system/erp/frontend studio entry): talks to the deployment's own
# system API with the signed-in workspace session; served under /studio/.
studio_env = {**os.environ, "VITE_STUDIO_API": "/api", "VITE_STUDIO_BASE": "/studio/"}
subprocess.run(["npx", "vite", "build", "--config", "vite.studio.config.ts", "--outDir", str(a.output.resolve()/"studio")],
               cwd=a.repo/"system"/"erp"/"frontend", env=studio_env, check=True)
print("Builds prepared only. All services and website session handoff remain unhosted.")

# Owner/admin are execution surfaces. Fail if a production Mizan URL slipped in.
for kind in ("owner", "admin"):
    for asset in (a.output/kind/"assets").glob("*.js"):
        if "allmizan.live" in asset.read_text():
            raise SystemExit(f"Production Mizan URL in {kind} bundle. Do not deploy.")
