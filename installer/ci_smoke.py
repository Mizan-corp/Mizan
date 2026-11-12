#!/usr/bin/env python3
"""Smoke-test built installers on this machine (CI: Linux and Windows).

    python installer/ci_smoke.py

Uses installer/build/ output. Mints a throwaway licence signed with a key made
for this run, then:
1. single device: `payload/server/mizan-server install`, run, health, sign-in;
2. LAN: the one-file `dist/MizanSetup-*` headless install (unpacks its embedded
   payload), run, HTTPS health, sign-in, the tills' certificate download.
No background service is registered; everything lives in a temporary folder.
"""
from __future__ import annotations

import base64
import json
import os
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"
WINDOWS = os.name == "nt"
EXE = ".exe" if WINDOWS else ""
PASSWORD = "Smoke1234!"
UNVERIFIED = ssl._create_unverified_context()


def b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


KEY = Ed25519PrivateKey.generate()
PUBLIC = b64(KEY.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))


def licence(mode: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "v": 1,
        "lid": str(uuid.uuid4()),
        "workspace": {"id": str(uuid.uuid4()), "name": f"Smoke {mode}", "slug": f"smoke-{mode}", "sector": "retail",
                      "scale": "small", "modules": ["inventory", "pos", "finance"], "palette": {"hue": 350, "name": "mizan"}},
        "owner": {"login": "owner", "full_name": "Smoke Test"},
        "mode": mode,
        "plan": "trial",
        "limits": {"max_users": 3, "max_branches": 1, "max_storage_mb": 1024, "max_monthly_sales": 100},
        "valid_until": (now + timedelta(days=30)).isoformat(),
        "issued_at": now.isoformat(),
    }
    body = f"MZN1.{b64(json.dumps(payload, separators=(',', ':')).encode())}"
    return f"{body}.{b64(KEY.sign(body.encode()))}"


def request(url: str, data: dict | None = None) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data else None,
                                 headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=10, context=UNVERIFIED) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def wait_healthy(base: str, proc: subprocess.Popen, log: Path, timeout: float = 120) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            raise SystemExit(f"mizan-server run exited ({proc.returncode}):\n{log.read_text(encoding="utf-8", errors='replace')[-3000:]}")
        try:
            status, body = request(f"{base}/api/health")
            if status == 200 and json.loads(body).get("status") == "ok":
                return
        except OSError:
            pass
        time.sleep(1.5)
    raise SystemExit(f"{base} didn't become healthy:\n{log.read_text(encoding="utf-8", errors='replace')[-3000:]}")


def check(name: str, cmd: list[str], env: dict, base: str, home: Path, server: Path, lan: bool) -> None:
    print(f"\n▸ {name}: install", flush=True)
    r = subprocess.run(cmd, env=env, text=True, encoding="utf-8", errors="replace", capture_output=True)
    print(r.stdout[-2500:], r.stderr[-2500:], sep="\n")
    if r.returncode != 0:
        pgbin = server.parent.parent / "pgsql" / "bin"
        v = subprocess.run([str(pgbin / f"initdb{EXE}"), "--version"], capture_output=True, text=True)
        print(f"diagnostics: initdb --version → {v.returncode:#x} {v.stdout.strip()} {v.stderr.strip()}")
        print(f"diagnostics: {len(list(pgbin.glob('*')))} files in {pgbin}: {sorted(f.name for f in pgbin.glob('*.dll'))[:40]}")
        raise SystemExit(f"{name}: install failed ({r.returncode})")

    print(f"▸ {name}: run", flush=True)
    log = home / "run.log"
    with open(log, "w") as out:
        proc = subprocess.Popen([str(server), "run"], env=env, stdout=out, stderr=subprocess.STDOUT)
    try:
        wait_healthy(base, proc, log)
        status, body = request(f"{base}/api/auth/login", {"username": "owner", "password": PASSWORD})
        if status != 200 or "access_token" not in json.loads(body):
            raise SystemExit(f"{name}: sign-in failed ({status}): {body[:300]!r}")
        status, _ = request(f"{base}/")
        if status != 200:
            raise SystemExit(f"{name}: the app page returned {status}")
        if lan:
            status, _ = request(f"{base}/api/onprem/ca.crt")
            if status != 200:
                raise SystemExit(f"{name}: certificate download returned {status}")
            if "zeroconf isn't installed" in log.read_text(encoding="utf-8", errors="replace"):
                raise SystemExit(f"{name}: the build is missing zeroconf (mizan.local)")
        st = subprocess.run([str(server), "status", "--json"], env=env, text=True, encoding="utf-8", errors="replace", capture_output=True)
        info = json.loads(st.stdout)
        if info.get("licence", {}).get("status") != "active":
            raise SystemExit(f"{name}: licence isn't active: {st.stdout}")
        bk = subprocess.run([str(server), "backup"], env=env, text=True, encoding="utf-8", errors="replace", capture_output=True)
        if bk.returncode != 0:
            raise SystemExit(f"{name}: backup failed: {bk.stdout}{bk.stderr}")
        print(f"✔ {name}: healthy, sign-in, licence active, backup", flush=True)
    finally:
        proc.terminate()
        try:
            proc.wait(30)
        except subprocess.TimeoutExpired:
            proc.kill()
        pg_ctl = server.parent.parent / "pgsql" / "bin" / f"pg_ctl{EXE}"
        subprocess.run([str(pg_ctl), "stop", "-D", str(home / "pg"), "-m", "fast"], capture_output=True)


def signed_release(release: dict) -> str:
    """A release offer as Mizan Cloud signs it (licence key, release prefix MZR1)."""
    body = f"MZR1.{b64(json.dumps(release, separators=(',', ':')).encode())}"
    return f"{body}.{b64(KEY.sign(body.encode()))}"


def check_update(env: dict, base: str, home: Path, install_dir: Path, tmp: Path) -> None:
    """#89: offer a release one version newer (this build with a bumped VERSION), update to it
    with `mizan-server update --yes`, then run the new version: healthy, sign-in, version shown."""
    import hashlib
    import zipfile

    print("\n▸ update: to a newer release", flush=True)
    current = (install_dir / "VERSION").read_text(encoding="utf-8").strip()
    parts = current.split("-")[0].split(".")
    newer = ".".join([*parts[:-1], str(int(parts[-1]) + 1)])
    archive = tmp / f"payload-{newer}.zip"
    payload = BUILD / "payload"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(payload.rglob("*")):
            if f.is_file() and f.name != "VERSION":
                z.write(f, f.relative_to(payload).as_posix())
        z.writestr("VERSION", newer)
    release = {"version": newer, "platform": "windows" if WINDOWS else "linux", "url": archive.as_uri(),
               "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(), "notes": "smoke test"}
    state_file = home / "mizan" / "state.json"
    state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
    state["update_available"] = {"version": newer, "release": signed_release(release)}
    state_file.write_text(json.dumps(state), encoding="utf-8")

    server = install_dir / "server" / f"mizan-server{EXE}"
    r = subprocess.run([str(server), "update", "--yes"], env=env, text=True, encoding="utf-8", errors="replace",
                       capture_output=True, timeout=1200)
    print(r.stdout[-3000:], r.stderr[-3000:], sep="\n")
    log = home / "logs" / "update.log"
    if r.returncode != 0:
        raise SystemExit(f"update failed ({r.returncode}):\n{log.read_text(encoding='utf-8', errors='replace')[-3000:] if log.exists() else ''}")
    # On Windows the command hands over and returns at once: wait for the outcome.
    deadline = time.time() + 900
    while time.time() < deadline:
        last = (json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}).get("last_update") or {}
        if last.get("to") == newer:
            break
        time.sleep(3)
    else:
        raise SystemExit("update: no outcome after 15 minutes")
    if not last.get("ok"):
        raise SystemExit(f"update failed: {last.get('error')}\n{log.read_text(encoding='utf-8', errors='replace')[-3000:] if log.exists() else ''}")
    if (install_dir / "VERSION").read_text(encoding="utf-8").strip() != newer:
        raise SystemExit("update: the program folder wasn't replaced")

    run_log = home / "run-updated.log"
    with open(run_log, "w") as out:
        proc = subprocess.Popen([str(server), "run"], env=env, stdout=out, stderr=subprocess.STDOUT)
    try:
        wait_healthy(base, proc, run_log)
        status, body = request(f"{base}/api/auth/login", {"username": "owner", "password": PASSWORD})
        if status != 200:
            raise SystemExit(f"update: sign-in after the update failed ({status}): {body[:300]!r}")
        st = json.loads(subprocess.run([str(server), "status", "--json"], env=env, text=True, encoding="utf-8",
                                       errors="replace", capture_output=True).stdout)
        if st.get("version") != newer or not (st.get("last_update") or {}).get("ok"):
            raise SystemExit(f"update: status doesn't show the update: {st}")
        print(f"✔ update: {current} → {newer}, healthy, sign-in, data kept", flush=True)
    finally:
        proc.terminate()
        try:
            proc.wait(30)
        except subprocess.TimeoutExpired:
            proc.kill()
        pg_ctl = install_dir / "pgsql" / "bin" / f"pg_ctl{EXE}"
        subprocess.run([str(pg_ctl), "stop", "-D", str(home / "pg"), "-m", "fast"], capture_output=True)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="mizan-smoke-"))
    common = ["--admin-username", "owner", "--no-service", "--app-env", "development",
              "--cloud-url", "http://127.0.0.1:9", "--licence-public-key", PUBLIC]

    # 1. Single device, from the payload folder.
    server = BUILD / "payload" / "server" / f"mizan-server{EXE}"
    home = tmp / "desktop"
    env = {**os.environ, "MIZAN_HOME": str(home), "MIZAN_ADMIN_PASSWORD": PASSWORD}
    check("single device", [str(server), "install", "--licence", licence("desktop"), "--port", "47900", *common],
          env, "http://127.0.0.1:47900", home, server, lan=False)

    # 2. LAN, from the one-file Mizan Setup.
    setup = next((BUILD / "dist").glob(f"MizanSetup-*{EXE}" if WINDOWS else "MizanSetup-*-linux"), None)
    if not setup:
        raise SystemExit("No dist/MizanSetup-* built")
    home, install_dir = tmp / "lan", tmp / "lan-program"
    env = {**os.environ, "MIZAN_HOME": str(home), "MIZAN_INSTALL_DIR": str(install_dir), "MIZAN_ADMIN_PASSWORD": PASSWORD}
    check("LAN (MizanSetup)", [str(setup), "install", "--licence", licence("lan"), "--port", "8543", *common],
          env, "https://127.0.0.1:8543", home, install_dir / "server" / f"mizan-server{EXE}", lan=True)
    check_update(env, "https://127.0.0.1:8543", home, install_dir, tmp)

    print("\n✔ Smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
