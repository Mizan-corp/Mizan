"""Backups (#90): copies to a configured destination; an unreachable one never loses the backup."""
import json
from pathlib import Path

from mizan_server import backup, postgres
from mizan_server.layout import Config


def cfg_at(tmp_path: Path, **extra) -> Config:
    data = tmp_path / "data"
    (data / "backups").mkdir(parents=True)
    (data / "mizan").mkdir()
    return Config(mode="lan", install_dir=str(tmp_path / "program"), data_dir=str(data), http_host="0.0.0.0",
                  http_port=8443, tls=True, db_port=55432, db_password="x", **extra)


def fake_pg(monkeypatch):
    monkeypatch.setattr(postgres, "start", lambda cfg: None)
    monkeypatch.setattr(postgres, "dump", lambda cfg, target: target.write_bytes(b"PGDMP") or target)


def state(cfg: Config) -> dict:
    return json.loads((cfg.data / "mizan" / "state.json").read_text())


def test_backups_are_copied_to_the_destination_and_rotated(tmp_path, monkeypatch):
    fake_pg(monkeypatch)
    usb = tmp_path / "usb"
    cfg = cfg_at(tmp_path, backup_copy_to=str(usb))
    usb.mkdir()
    for i in range(16):
        (usb / f"mizan-20200101-0000{i:02d}.dump").write_bytes(b"old")
    made = backup.run_backup(cfg)
    assert (usb / made.name).read_bytes() == b"PGDMP"
    assert len(list(usb.glob("mizan-*.dump"))) == backup.KEEP
    assert state(cfg)["backup_copy_error"] is None and state(cfg)["last_backup_at"]


def test_an_unreachable_destination_keeps_the_backup(tmp_path, monkeypatch):
    fake_pg(monkeypatch)
    blocker = tmp_path / "not-a-folder"
    blocker.write_text("a file where the folder should be")
    cfg = cfg_at(tmp_path, backup_copy_to=str(blocker / "sub"))
    made = backup.run_backup(cfg)
    assert made.exists()
    assert state(cfg)["backup_copy_error"].startswith(str(blocker / "sub"))


def test_config_from_a_newer_version_still_loads(tmp_path):
    cfg = cfg_at(tmp_path)
    cfg.save()
    saved = json.loads((cfg.data / "config.json").read_text())
    saved["something_new"] = 1
    (cfg.data / "config.json").write_text(json.dumps(saved))
    assert Config.load(cfg.data).mode == "lan"
