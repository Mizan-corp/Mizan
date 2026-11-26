"""`mizan-server run`: what the service runs.

Starts the private PostgreSQL, keeps the LAN certificate current, takes a daily
backup, and serves the app and API (uvicorn, in this process) until stopped.
"""
from __future__ import annotations

import logging
import os
import sys
import threading
import time
from pathlib import Path

from mizan_server import postgres
from mizan_server.layout import Config

logger = logging.getLogger("mizan.server")

BACKUP_EVERY_SECONDS = 24 * 3600
FIRST_BACKUP_AFTER_SECONDS = 15 * 60


def app_import_path() -> None:
    """From source, make the shared kernel and the system API importable."""
    if getattr(sys, "frozen", False):
        return
    repo = Path(__file__).resolve().parents[3]
    for sub in ("system/erp/backend", "system/core/backend"):
        path = str(repo / sub)
        if path not in sys.path:
            sys.path.insert(0, path)


def load_app_environment(cfg: Config) -> None:
    os.environ.update(cfg.app_environment())
    os.environ["MIZAN_TLS_DIR"] = str(cfg.data / "tls")
    app_import_path()


def _backups_forever(cfg: Config, stop: threading.Event) -> None:
    from mizan_server.backup import run_backup

    if stop.wait(FIRST_BACKUP_AFTER_SECONDS):
        return
    while True:
        try:
            path = run_backup(cfg)
            logger.info("Backup written to %s", path)
        except Exception:
            logger.exception("Daily backup failed")
        if stop.wait(BACKUP_EVERY_SECONDS):
            return


def run(cfg: Config) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    postgres.start(cfg)
    ssl = {}
    if cfg.tls:
        from mizan_server.tls import ensure_certificates, needs_renewal

        tls_dir = cfg.data / "tls"
        if needs_renewal(tls_dir):
            ensure_certificates(tls_dir)
        ssl = {"ssl_keyfile": str(tls_dir / "server.key"), "ssl_certfile": str(tls_dir / "server.crt")}

    load_app_environment(cfg)
    import uvicorn
    from main import app  # the system API, wrapped for server mode (MIZAN_MODE)

    stop = threading.Event()
    threading.Thread(target=_backups_forever, args=(cfg, stop), daemon=True, name="backups").start()
    advertiser = None
    if cfg.tls:  # LAN
        from mizan_server.discovery import Advertiser

        advertiser = Advertiser(cfg.http_port)
        advertiser.start()
    server = uvicorn.Server(uvicorn.Config(app, host=cfg.http_host, port=cfg.http_port, proxy_headers=False,
                                           log_level="info", access_log=False, **ssl))
    try:
        server.run()
    finally:
        stop.set()
        if advertiser:
            advertiser.stop()
        time.sleep(0.2)
        postgres.stop(cfg)
    return 0
