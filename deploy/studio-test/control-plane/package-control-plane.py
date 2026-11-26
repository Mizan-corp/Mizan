"""Extend a reviewed test package into a fresh candidate. Does not link or deploy."""
import argparse
import json
from pathlib import Path
import shutil

p = argparse.ArgumentParser()
p.add_argument("--base-package", type=Path, required=True)
p.add_argument("--service-source", type=Path, required=True)
p.add_argument("--frontend-builds", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
if a.output.exists():
    raise SystemExit("Use a new output directory; existing packages are never changed.")
recipe = Path(__file__).resolve().parent
for kind in ("owner", "admin", "website"):
    for required in [a.service_source/kind/"backend"/(kind+"_api"), a.frontend_builds/kind/"index.html"]:
        if not required.exists():
            raise SystemExit(f"Missing prepared source/build: {required}")
    if kind != "website":
        for asset in (a.frontend_builds/kind/"assets").glob("*.js"):
            if "allmizan.live" in asset.read_text():
                raise SystemExit("Production Mizan URL in execution bundle; do not package.")
ignore = shutil.ignore_patterns(".env*", ".vercel", "__pycache__", "*.pyc", ".ruff_cache", ".pytest_cache")
shutil.copytree(a.base_package, a.output, ignore=ignore)
for kind in ("owner", "admin", "website"):
    shutil.copytree(a.service_source/kind/"backend"/(kind+"_api"), a.output/(kind+"_api"), ignore=ignore)
    shutil.copy(recipe/(kind+".py"), a.output/"api"/(kind+".py"))
    shutil.copytree(a.frontend_builds/kind, a.output/"static"/kind, ignore=ignore)
if not (a.frontend_builds/"studio"/"studio.html").exists():
    raise SystemExit("Missing prepared studio build: studio/studio.html")
shutil.copytree(a.frontend_builds/"studio", a.output/"static"/"studio", ignore=ignore)
shutil.copy(recipe/"vercel.full.json", a.output/"vercel.json")
for preserved in ["api/index.py", "static/index.html", "static/erp/index.html"]:
    if (a.base_package/preserved).read_bytes() != (a.output/preserved).read_bytes():
        raise SystemExit(f"Preservation check failed: {preserved}")
print(json.dumps({"candidate":str(a.output),"deployed":False,"linked":False}))
