# PyInstaller spec for mizan-server (one folder: server/mizan-server[.exe] + server/_internal/).
# Build with: python installer/build.py --only server
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

HERE = Path(SPECPATH).resolve()
REPO = HERE.parents[1]
SHARED = REPO / "system" / "core" / "backend"
SYSTEM = REPO / "system" / "erp" / "backend"

# Importing the app during analysis reads settings: give it harmless values.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://build:build@127.0.0.1/build")
os.environ.setdefault("SECRET_KEY", "build-only")


def package_modules(root: Path, package: str) -> list[str]:
    """Every module under a package folder, including namespace packages (app.modules)."""
    names = []
    for path in (root / package.replace(".", "/")).rglob("*.py"):
        if "__pycache__" in path.parts or "tests" in path.parts:
            continue
        rel = path.relative_to(root).with_suffix("")
        parts = list(rel.parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        names.append(".".join(parts))
    return sorted(set(names))


def package_data(root: Path, package: str) -> list[tuple[str, str]]:
    """Non-Python files (module manifests, SQL, print templates, fonts…)."""
    out = []
    for path in (root / package).rglob("*"):
        if path.is_file() and path.suffix not in (".py", ".pyc") and "__pycache__" not in path.parts:
            out.append((str(path), str(path.parent.relative_to(root))))
    return out


hidden = (
    package_modules(SHARED, "app")
    + package_modules(SYSTEM, "system_api")
    + ["main"]
    + collect_submodules("uvicorn")
    + collect_submodules("asyncpg")
    + collect_submodules("passlib.handlers")
    + collect_submodules("mizan_server")
    + collect_submodules("zeroconf")
    + ["email_validator", "multipart", "python_multipart"]
)

datas = (
    package_data(SHARED, "app")
    + collect_data_files("weasyprint")
    + collect_data_files("pyphen")
    + collect_data_files("reportlab")
    + collect_data_files("tzdata")
)

a = Analysis(
    [str(HERE / "mizan_server" / "__main__.py")],
    pathex=[str(HERE), str(SHARED), str(SYSTEM)],
    hiddenimports=hidden,
    datas=datas,
    excludes=["tkinter", "pytest", "IPython", "matplotlib", "PyInstaller"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="mizan-server",
    console=True,
    icon=str(REPO / "installer" / "assets" / "mizan.ico") if (REPO / "installer" / "assets" / "mizan.ico").exists() else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="server")
