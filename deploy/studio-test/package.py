"""Package the existing isolated Studio + ERP test deployment, without secrets.
Run frontend builds first as README.md describes. Does not deploy or migrate.
"""
import argparse
import json
from pathlib import Path
import shutil
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

parser = argparse.ArgumentParser()
parser.add_argument("--repo", type=Path, required=True)
parser.add_argument("--studio-build", type=Path, required=True)
parser.add_argument("--erp-build", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
a = parser.parse_args()
r, out = a.repo.resolve(), a.output.resolve()
if out.exists():
    raise SystemExit("Use a new output directory. Existing output is never overwritten.")
for needed in [r/"system/core/backend/app", r/"system/backend/system_api", r/"website/backend/website_api", a.studio_build/"studio-preview.html", a.erp_build/"index.html"]:
    if not needed.exists():
        raise SystemExit(f"Missing required build/source: {needed}")
# Catch the repository production-env default before packaging a test ERP.
for asset in (a.erp_build/"assets").glob("*.js"):
    if "https://api.allmizan.live/api" in asset.read_text():
        raise SystemExit("ERP build targets the existing external API. Rebuild with VITE_API_URL=/api.")
out.mkdir(parents=True)
ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".ruff_cache", ".pytest_cache", ".env*", "*.egg-info", "build")
shutil.copytree(r/"system/core/backend/app", out/"app", ignore=ignore)
shutil.copytree(r/"system/backend/system_api", out/"system_api", ignore=ignore)
shutil.copytree(r/"website/backend/website_api", out/"website_api", ignore=ignore)
deps = tomllib.loads((r/"system/core/backend/pyproject.toml").read_text())["project"]["dependencies"]
(out/"requirements.txt").write_text("\n".join(deps)+"\n")
(out/".python-version").write_text("3.12\n")
(out/"api").mkdir()
recipe = Path(__file__).resolve().parent
shutil.copy(recipe/"index.py", out/"api/index.py")
shutil.copy(recipe/"vercel.json", out/"vercel.json")
shutil.copytree(a.studio_build, out/"static", ignore=ignore)
shutil.copy(out/"static/studio-preview.html", out/"static/index.html")
shutil.copytree(a.erp_build, out/"static/erp", ignore=ignore)
(out/".gitignore").write_text(".vercel\n.env*\n")
print(json.dumps({"output":str(out),"files":sum(p.is_file() for p in out.rglob("*")),"deployed":False}))
