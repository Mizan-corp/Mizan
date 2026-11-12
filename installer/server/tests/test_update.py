"""Updating an installed server (#89): staging, download checks, apply and roll back.

The service, PostgreSQL, migrations and health check are faked; files are real (tmp_path).
"""
import hashlib
import io
import json
import os
import zipfile
from pathlib import Path

import pytest

from mizan_server import postgres, service, update
from mizan_server.layout import EXE, IS_WINDOWS, Config


def make_cfg(tmp_path: Path, program: str = "1.0.0") -> Config:
    install = tmp_path / "program"
    (install / "server").mkdir(parents=True)
    (install / "VERSION").write_text(program)
    (install / "server" / f"mizan-server{EXE}").write_text("old")
    (install / "Mizan.exe").write_text("desktop app")  # not in payloads: must survive updates
    data = tmp_path / "data"
    (data / "logs").mkdir(parents=True)
    return Config(mode="desktop", install_dir=str(install), data_dir=str(data), http_host="127.0.0.1",
                  http_port=47800, tls=False, db_port=55432, db_password="x")


def payload_zip(version: str, *, executable: bool = True, with_server: bool = True) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("VERSION", version)
        if with_server:
            info = zipfile.ZipInfo(f"server/mizan-server{EXE}")
            info.external_attr = (0o755 if executable else 0o644) << 16
            z.writestr(info, "new")
        z.writestr("web/index.html", "<html>new</html>")
    return buf.getvalue()


@pytest.fixture()
def fakes(monkeypatch):
    calls = {"service": [], "pg": [], "restored": None, "records": [], "migrate": 0}
    running = {"on": True}

    def control(cfg, action):
        calls["service"].append(action)
        if action in ("start", "stop"):
            running["on"] = action == "start"
            return True
        return running["on"]

    monkeypatch.setattr(service, "control", control)
    monkeypatch.setattr(postgres, "start", lambda cfg: calls["pg"].append("start"))
    monkeypatch.setattr(postgres, "stop", lambda cfg: calls["pg"].append("stop"))
    monkeypatch.setattr(postgres, "restore", lambda cfg, src: calls.__setitem__("restored", src))
    monkeypatch.setattr(update, "_record", lambda outcome: calls["records"].append(outcome))

    def migrate(cfg):
        calls["migrate"] += 1

    monkeypatch.setattr(update, "_migrate", migrate)
    import mizan_server.engine as engine

    monkeypatch.setattr(engine, "_wait_healthy", lambda url, timeout=90: True)
    return calls


def test_stage_unpacks_with_exec_bits_and_checks_the_version(tmp_path):
    cfg = make_cfg(tmp_path)
    archive = tmp_path / "p.zip"
    archive.write_bytes(payload_zip("1.1.0"))
    staged = update.stage(cfg, archive, {"version": "1.1.0"})
    assert (staged / "VERSION").read_text() == "1.1.0"
    if not IS_WINDOWS:
        assert os.access(staged / "server" / "mizan-server", os.X_OK)
    with pytest.raises(update.UpdateError):
        update.stage(cfg, archive, {"version": "1.2.0"})  # says 1.1.0 inside
    archive.write_bytes(payload_zip("1.1.0", with_server=False))
    with pytest.raises(update.UpdateError):
        update.stage(cfg, archive, {"version": "1.1.0"})


def test_download_checks_the_checksum(tmp_path):
    cfg = make_cfg(tmp_path)
    src = tmp_path / "release.zip"
    src.write_bytes(payload_zip("1.1.0"))
    good = {"version": "1.1.0", "platform": update.PLATFORM, "url": src.as_uri(),
            "sha256": hashlib.sha256(src.read_bytes()).hexdigest()}
    assert update.download(cfg, good).read_bytes() == src.read_bytes()
    bad = {**good, "version": "1.1.1", "sha256": "0" * 64}
    with pytest.raises(update.UpdateError):
        update.download(cfg, bad)
    assert not list((cfg.data / "updates").glob("*1.1.1*"))  # nothing half-downloaded left


def test_apply_replaces_the_program_and_keeps_the_desktop_app(tmp_path, fakes):
    cfg = make_cfg(tmp_path)
    archive = tmp_path / "p.zip"
    archive.write_bytes(payload_zip("1.1.0"))
    staged = update.stage(cfg, archive, {"version": "1.1.0"})
    assert update.apply(cfg, staged, tmp_path / "backup.dump") is True
    assert (cfg.install / "VERSION").read_text() == "1.1.0"
    assert (cfg.install / "server" / f"mizan-server{EXE}").read_text() == "new"
    assert (cfg.install / "Mizan.exe").read_text() == "desktop app"
    assert not cfg.install.with_name("program.previous").exists()
    assert fakes["migrate"] == 1 and fakes["restored"] is None
    assert fakes["service"][:2] == ["status", "stop"] and "start" in fakes["service"]
    assert fakes["records"][-1] == {**fakes["records"][-1], "from": "1.0.0", "to": "1.1.0", "ok": True}


def test_a_failed_migration_rolls_back_program_and_database(tmp_path, fakes, monkeypatch):
    cfg = make_cfg(tmp_path)
    archive = tmp_path / "p.zip"
    archive.write_bytes(payload_zip("1.1.0"))
    staged = update.stage(cfg, archive, {"version": "1.1.0"})

    def broken(cfg):
        raise update.UpdateError("Migrations failed: boom")

    monkeypatch.setattr(update, "_migrate", broken)
    backup = tmp_path / "backup.dump"
    assert update.apply(cfg, staged, backup) is False
    assert (cfg.install / "VERSION").read_text() == "1.0.0"
    assert (cfg.install / "server" / f"mizan-server{EXE}").read_text() == "old"
    assert fakes["restored"] == backup
    assert fakes["service"][-1] == "start"  # the old version runs again
    last = fakes["records"][-1]
    assert last["ok"] is False and "boom" in last["error"]


def test_an_unhealthy_new_version_rolls_back(tmp_path, fakes, monkeypatch):
    import mizan_server.engine as engine

    cfg = make_cfg(tmp_path)
    archive = tmp_path / "p.zip"
    archive.write_bytes(payload_zip("1.1.0"))
    staged = update.stage(cfg, archive, {"version": "1.1.0"})
    monkeypatch.setattr(engine, "_wait_healthy", lambda url, timeout=90: False)
    assert update.apply(cfg, staged, tmp_path / "b.dump") is False
    assert (cfg.install / "VERSION").read_text() == "1.0.0"


def test_a_program_folder_in_use_changes_nothing(tmp_path, fakes, monkeypatch):
    cfg = make_cfg(tmp_path)
    archive = tmp_path / "p.zip"
    archive.write_bytes(payload_zip("1.1.0"))
    staged = update.stage(cfg, archive, {"version": "1.1.0"})
    real_replace = os.replace

    def locked(src, dst):
        if Path(src) == cfg.install:
            raise PermissionError("in use")
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", locked)
    assert update.apply(cfg, staged, tmp_path / "b.dump") is False
    assert (cfg.install / "VERSION").read_text() == "1.0.0"
    assert fakes["migrate"] == 0 and fakes["service"][-1] == "start"
    assert "Close Mizan windows" in fakes["records"][-1]["error"]


def test_version_order():
    assert update._version_tuple("1.10.0") > update._version_tuple("1.9.3")
    assert update._version_tuple("1.0.1") > update._version_tuple("1.0.0-dev")
    assert json.dumps(update._version_tuple("2")) == "[2]"


def test_installs_without_a_service_are_updated_in_place(tmp_path, fakes, monkeypatch):
    cfg = make_cfg(tmp_path)
    archive = tmp_path / "p.zip"
    archive.write_bytes(payload_zip("1.1.0"))
    staged = update.stage(cfg, archive, {"version": "1.1.0"})
    monkeypatch.setattr(service, "control", lambda cfg, action: fakes["service"].append(action) and False)
    assert update.apply(cfg, staged, tmp_path / "b.dump") is True
    assert (cfg.install / "VERSION").read_text() == "1.1.0"
    assert not {"start", "stop"} & set(fakes["service"])  # never started or stopped


def test_apply_waits_for_the_command_that_started_it():
    import subprocess
    import sys
    import time

    import threading

    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(1.2)"])
    threading.Thread(target=proc.wait, daemon=True).start()  # reaped, as the shell does for the CLI
    started = time.time()
    update.wait_for_exit(proc.pid, timeout=10)
    assert 0.8 < time.time() - started < 8
