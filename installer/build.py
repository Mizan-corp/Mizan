#!/usr/bin/env python3
"""Build Mizan's on-premise payload and installers (ADR-005, phase 2).

    python installer/build.py                    # everything for this platform
    python installer/build.py --only web,pgsql   # just some parts (dev: run mizan-server from source)

Output (installer/build/, git-ignored):
    payload/server/     mizan-server (PyInstaller, one folder) [+ mizan-service.exe on Windows]
    payload/pgsql/      PostgreSQL 16 (theseus-rs portable build)
    payload/web/        the app's on-premise build
    payload/VERSION
    dist/mizan-setup-<version>-linux-x86_64.run     Linux: self-extracting, command line
    dist/payload-<version>-<platform>.zip           what Mizan Setup (Tauri) embeds
    dist/MizanSetup-<version>-<platform>[.exe]      Mizan Setup with the payload appended (one file)

Per-client installers: python installer/stamp.py <setup> <licence key or .mzn> <output>
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform as _platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BUILD = HERE / "build"
PAYLOAD = BUILD / "payload"
CACHE = BUILD / "cache"
DIST = BUILD / "dist"
VERSION = (HERE / "VERSION").read_text(encoding="utf-8").strip()

PG_VERSION = "16.15.1"
PG_TARGETS = {"linux": "x86_64-unknown-linux-gnu", "windows": "x86_64-pc-windows-msvc"}
WINSW_URL = "https://github.com/winsw/winsw/releases/download/v2.12.0/WinSW-x64.exe"


def step(msg: str) -> None:
    print(f"\n▸ {msg}", flush=True)


def run(cmd: list[str], **kw) -> None:
    print("  $ " + " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, **kw)


def download(url: str, dest: Path) -> Path:
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  ↓ {url}", flush=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=600) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f)
    tmp.rename(dest)
    return dest


# ─── Parts ─────────────────────────────────────────────────────────────────


def build_web() -> None:
    step("App (on-premise build)")
    env = {**os.environ, "VITE_DEPLOYMENT": "onprem", "VITE_API_URL": "/api"}
    out = PAYLOAD / "web"
    shutil.rmtree(out, ignore_errors=True)
    npx = "npx.cmd" if os.name == "nt" else "npx"
    run([npx, "vite", "build", "--outDir", str(out), "--emptyOutDir"], cwd=ROOT / "system" / "frontend", env=env)


def build_pgsql(target: str) -> None:
    step(f"PostgreSQL {PG_VERSION} ({target})")
    name = f"postgresql-{PG_VERSION}-{PG_TARGETS[target]}.tar.gz"
    archive = download(f"https://github.com/theseus-rs/postgresql-binaries/releases/download/{PG_VERSION}/{name}", CACHE / name)
    out = PAYLOAD / "pgsql"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    with tarfile.open(archive) as tar:
        for m in tar.getmembers():
            parts = Path(m.name).parts
            if len(parts) < 2 or parts[1] in ("include", "doc"):
                continue  # headers and docs aren't needed at run time
            m.name = str(Path(*parts[1:]))
            if m.islnk():  # hard links name the original path
                link = Path(m.linkname).parts
                m.linkname = str(Path(*link[1:])) if len(link) > 1 else m.linkname
            tar.extract(m, out, filter="tar")
    if target == "windows":
        bundle_vc_runtime(out / "bin")
    print(f"  {sum(f.stat().st_size for f in out.rglob('*') if f.is_file()) // 1_000_000} MB")


VC_RUNTIME = ("vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll")


def bundle_vc_runtime(bin_dir: Path) -> None:
    """PostgreSQL's Windows build needs the Visual C++ runtime, which a clean
    Windows may lack: ship it next to the programs (app-local deployment)."""
    system32 = Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "System32"
    for dll in VC_RUNTIME:
        if (bin_dir / dll).exists():
            continue
        if not (system32 / dll).exists():
            raise SystemExit(f"{dll} isn't in {system32}: build the Windows payload on Windows")
        shutil.copy2(system32 / dll, bin_dir / dll)
    print(f"  + Visual C++ runtime ({', '.join(VC_RUNTIME)})")


def build_server(target: str) -> None:
    step("mizan-server (PyInstaller)")
    spec = HERE / "server" / "mizan-server.spec"
    work = BUILD / "pyinstaller"
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--distpath", str(PAYLOAD), "--workpath", str(work), str(spec)],
        cwd=HERE / "server")
    if target == "windows":
        download(WINSW_URL, CACHE / "WinSW-x64.exe")
        shutil.copy2(CACHE / "WinSW-x64.exe", PAYLOAD / "server" / "mizan-service.exe")


def write_version() -> None:
    (PAYLOAD / "VERSION").write_text(VERSION + "\n", encoding="utf-8")


# ─── Packages ──────────────────────────────────────────────────────────────

RUN_HEADER = r"""#!/bin/sh
# Mizan (ميزان) {version} — Linux installer. Command line:
#   sh {name} install --licence <key> --admin-password <password> [--demo]
#   sh {name} --extract-only /opt/mizan
# Unpacks itself (to /opt/mizan as root, ~/.local/opt/mizan otherwise), then runs
# `mizan-server` with the arguments given (default: install).
set -e
DEST="${{MIZAN_INSTALL_DIR:-}}"
if [ -z "$DEST" ]; then
  if [ "$(id -u)" = "0" ]; then DEST=/opt/mizan; else DEST="$HOME/.local/opt/mizan"; fi
fi
if [ "$1" = "--extract-only" ]; then DEST="${{2:-$DEST}}"; EXTRACT_ONLY=1; fi
mkdir -p "$DEST"
LINE=$(awk '/^__PAYLOAD_BELOW__$/ {{ print NR + 1; exit 0; }}' "$0")
echo "Unpacking Mizan {version} to $DEST …"
tail -n +"$LINE" "$0" | tar -xz -C "$DEST"
if [ -n "$EXTRACT_ONLY" ]; then echo "Unpacked. Run: $DEST/server/mizan-server install --help"; exit 0; fi
if [ $# -eq 0 ]; then set -- install --help; fi
exec "$DEST/server/mizan-server" "$@"
__PAYLOAD_BELOW__
"""


def package_linux_run() -> Path:
    step("Linux installer (.run)")
    DIST.mkdir(parents=True, exist_ok=True)
    name = f"mizan-setup-{VERSION}-linux-x86_64.run"
    out = DIST / name
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz", compresslevel=6) as tar:
        for item in sorted(PAYLOAD.iterdir()):
            tar.add(item, arcname=item.name)
    out.write_bytes(RUN_HEADER.format(version=VERSION, name=name).encode() + buf.getvalue())
    out.chmod(0o755)
    print(f"  {out} ({out.stat().st_size // 1_000_000} MB)")
    return out


def package_payload_zip(target: str) -> Path:
    step("Payload for Mizan Setup")
    DIST.mkdir(parents=True, exist_ok=True)
    out = DIST / f"payload-{VERSION}-{target}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in sorted(PAYLOAD.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(PAYLOAD).as_posix())
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    (DIST / f"{out.name}.json").write_text(json.dumps({"version": VERSION, "platform": target, "sha256": digest}), encoding="utf-8")
    print(f"  {out} ({out.stat().st_size // 1_000_000} MB)")
    return out


FOOTER_MAGIC = b"MZNSETUP"


def package_setup(target: str) -> Path:
    """Mizan Setup (Tauri, release) + payload.zip + footer: see installer/setup/src-tauri/src/embedded.rs."""
    step("Mizan Setup (Tauri)")
    setup = HERE / "setup"
    npm = "npm.cmd" if os.name == "nt" else "npm"
    run([npm, "run", "build"], cwd=setup)
    cargo = shutil.which("cargo") or str(Path.home() / ".cargo" / "bin" / "cargo")
    run([cargo, "build", "--release"], cwd=setup / "src-tauri")
    exe = setup / "src-tauri" / "target" / "release" / ("mizan-setup.exe" if target == "windows" else "mizan-setup")
    payload = DIST / f"payload-{VERSION}-{target}.zip"
    if not payload.exists():
        package_payload_zip(target)
    out = DIST / (f"MizanSetup-{VERSION}-{target}" + (".exe" if target == "windows" else ""))
    program = exe.read_bytes()
    with open(out, "wb") as f:
        f.write(program)
        offset = f.tell()
        with open(payload, "rb") as z:
            shutil.copyfileobj(z, f)
        length = f.tell() - offset
        f.write(FOOTER_MAGIC + offset.to_bytes(8, "little") + length.to_bytes(8, "little") + (0).to_bytes(8, "little"))
    out.chmod(0o755)
    print(f"  {out} ({out.stat().st_size // 1_000_000} MB)")
    return out


def main() -> int:
    host = "windows" if os.name == "nt" else "linux"
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--platform", choices=list(PG_TARGETS), default=host)
    p.add_argument("--only", help="comma-separated: web,pgsql,server,run,zip,setup")
    a = p.parse_args()
    if a.platform != host and "server" in (a.only or "server"):
        print("mizan-server must be built on its own platform (PyInstaller doesn't cross-compile).", file=sys.stderr)
        return 2
    parts = (a.only or "web,pgsql,server,run,zip,setup").split(",")
    PAYLOAD.mkdir(parents=True, exist_ok=True)
    write_version()
    if "web" in parts:
        build_web()
    if "pgsql" in parts:
        build_pgsql(a.platform)
    if "server" in parts:
        build_server(a.platform)
    if "run" in parts and a.platform == "linux":
        package_linux_run()
    if "zip" in parts:
        package_payload_zip(a.platform)
    if "setup" in parts:
        package_setup(a.platform)
    print(f"\n✔ Built for {a.platform} on {_platform.system()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
