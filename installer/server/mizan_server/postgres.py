"""The install's private PostgreSQL 16: one cluster in <data>/pg, reachable only
from this machine (127.0.0.1, password auth), never on the network."""
from __future__ import annotations

import os
import socket
import subprocess
import tempfile
from pathlib import Path

from mizan_server.layout import EXE, IS_WINDOWS, Config


class PostgresError(RuntimeError):
    pass


def _as_user(cfg: Config, cmd: list[str]) -> list[str]:
    """PostgreSQL refuses to run as root: a root install runs it as its own user."""
    if cfg.run_as and not IS_WINDOWS and os.geteuid() == 0:
        return ["runuser", "-u", cfg.run_as, "--", *cmd]
    return cmd


def _run(cfg: Config, cmd: list[str], *, env: dict | None = None, check: bool = True) -> subprocess.CompletedProcess:
    full_env = {**os.environ, "PGPASSWORD": cfg.db_password, "LC_ALL": "C", **(env or {})}
    r = subprocess.run(_as_user(cfg, cmd), capture_output=True, text=True, env=full_env,
                       creationflags=0x08000000 if IS_WINDOWS else 0)  # CREATE_NO_WINDOW
    if check and r.returncode != 0:
        raise PostgresError(f"{Path(cmd[0]).name} failed: {(r.stderr or r.stdout).strip()[-800:]}")
    return r


def tool(cfg: Config, name: str) -> str:
    path = cfg.pgbin / f"{name}{EXE}"
    if not path.exists():
        raise PostgresError(f"PostgreSQL isn't installed correctly: {path} is missing")
    return str(path)


def port_free(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def free_port(preferred: int) -> int:
    for port in range(preferred, preferred + 50):
        if port_free(port):
            return port
    raise PostgresError(f"No free port near {preferred}")


def is_initialised(cfg: Config) -> bool:
    return (cfg.pgdata / "PG_VERSION").exists()


def initdb(cfg: Config) -> None:
    cfg.pgdata.mkdir(parents=True, exist_ok=True)
    if cfg.run_as and not IS_WINDOWS and os.geteuid() == 0:
        subprocess.run(["chown", "-R", f"{cfg.run_as}:{cfg.run_as}", str(cfg.data)], check=True)
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".pw", dir=cfg.data) as f:
        f.write(cfg.db_password)
        pwfile = f.name
    if cfg.run_as and not IS_WINDOWS and os.geteuid() == 0:
        subprocess.run(["chown", cfg.run_as, pwfile], check=True)
    try:
        _run(cfg, [tool(cfg, "initdb"), "-D", str(cfg.pgdata), "-U", cfg.db_user, f"--pwfile={pwfile}",
                   "--auth=scram-sha-256", "-E", "UTF8", "--locale=C"])
    finally:
        os.unlink(pwfile)
    conf = cfg.pgdata / "postgresql.conf"
    conf.write_text(conf.read_text() + f"""
# ── Mizan ──────────────────────────────────────────────
listen_addresses = '127.0.0.1'
port = {cfg.db_port}
unix_socket_directories = ''
max_connections = 60
logging_collector = on
log_directory = 'log'
log_rotation_age = 1d
log_truncate_on_rotation = on
log_filename = 'postgresql-%a.log'
""")


def running(cfg: Config) -> bool:
    return _run(cfg, [tool(cfg, "pg_ctl"), "status", "-D", str(cfg.pgdata)], check=False).returncode == 0


def start(cfg: Config) -> None:
    if running(cfg):
        return
    log = cfg.data / "logs" / "postgres-start.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    if cfg.run_as and not IS_WINDOWS and os.geteuid() == 0:
        subprocess.run(["chown", "-R", f"{cfg.run_as}:{cfg.run_as}", str(log.parent)], check=True)
    _run(cfg, [tool(cfg, "pg_ctl"), "start", "-D", str(cfg.pgdata), "-l", str(log), "-w", "-t", "90"])


def stop(cfg: Config) -> None:
    if running(cfg):
        _run(cfg, [tool(cfg, "pg_ctl"), "stop", "-D", str(cfg.pgdata), "-m", "fast", "-w", "-t", "60"])


def _conn(cfg: Config) -> list[str]:
    return ["-h", "127.0.0.1", "-p", str(cfg.db_port), "-U", cfg.db_user]


def ensure_database(cfg: Config) -> None:
    r = _run(cfg, [tool(cfg, "psql"), *_conn(cfg), "-d", "postgres", "-tAc",
                   f"SELECT 1 FROM pg_database WHERE datname = '{cfg.db_name}'"])
    if r.stdout.strip() != "1":
        _run(cfg, [tool(cfg, "createdb"), *_conn(cfg), cfg.db_name])


def dump(cfg: Config, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    _run(cfg, [tool(cfg, "pg_dump"), *_conn(cfg), "-Fc", "-f", str(target), cfg.db_name])
    return target


def restore(cfg: Config, source: Path) -> None:
    _run(cfg, [tool(cfg, "pg_restore"), *_conn(cfg), "--clean", "--if-exists", "--no-owner", "-d", cfg.db_name, str(source)])
