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


def _env(cfg: Config, extra: dict | None = None) -> dict[str, str]:
    # PostgreSQL's own folder first, so its programs find its DLLs on Windows.
    path = os.pathsep.join([str(cfg.pgbin), os.environ.get("PATH", "")])
    return {**os.environ, "PATH": path, "LC_ALL": "C", **(extra or {})}


def _failure(name: str, r: subprocess.CompletedProcess) -> str:
    out = (r.stderr or r.stdout or "").strip()[-800:]
    code = r.returncode if r.returncode >= 0 else r.returncode & 0xFFFFFFFF
    hint = " (a DLL is missing: install the Microsoft Visual C++ Redistributable)" if code == 0xC0000135 else ""
    return f"{name} failed (exit code {code:#x}){hint}" + (f": {out}" if out else "")


def _run(cfg: Config, cmd: list[str], *, env: dict | None = None, check: bool = True) -> subprocess.CompletedProcess:
    full_env = _env(cfg, {"PGPASSWORD": cfg.db_password, **(env or {})})
    r = subprocess.run(_as_user(cfg, cmd), capture_output=True, text=True, encoding="utf-8", errors="replace", env=full_env,
                       creationflags=0x08000000 if IS_WINDOWS else 0)  # CREATE_NO_WINDOW
    if check and r.returncode != 0:
        raise PostgresError(_failure(Path(cmd[0]).name, r))
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


def _icacls(path: Path, *grants: str) -> None:
    r = subprocess.run(["icacls", str(path), "/grant", *grants, "/T", "/C", "/Q"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", creationflags=0x08000000)
    if r.returncode != 0:
        raise PostgresError(f"Couldn't set permissions on {path}: {(r.stdout or r.stderr).strip()[-400:]}")


def grant_windows_access(cfg: Config) -> None:
    """Windows: run as an administrator, PostgreSQL restarts itself without the
    Administrators group. It must still be able to read its programs (otherwise
    Windows reports a missing DLL) and write its data, whatever the folders'
    permissions: Users may read and run pgsql/; this account and SYSTEM (the
    service) get full control of the data."""
    who = subprocess.run(["whoami"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                         creationflags=0x08000000).stdout.strip()
    _icacls(cfg.install / "pgsql", "*S-1-5-32-545:(OI)(CI)RX")
    _icacls(cfg.data, "*S-1-5-18:(OI)(CI)F", *([f"{who}:(OI)(CI)F"] if who else []))


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
    conf.write_text(conf.read_text(encoding="utf-8") + f"""
# --- Mizan ---
listen_addresses = '127.0.0.1'
port = {cfg.db_port}
unix_socket_directories = ''
max_connections = 60
logging_collector = on
log_directory = 'log'
log_rotation_age = 1d
log_truncate_on_rotation = on
log_filename = 'postgresql-%a.log'
""", encoding="utf-8")


def running(cfg: Config) -> bool:
    return _run(cfg, [tool(cfg, "pg_ctl"), "status", "-D", str(cfg.pgdata)], check=False).returncode == 0


def start(cfg: Config) -> None:
    if running(cfg):
        return
    log = cfg.data / "logs" / "postgres-start.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    if cfg.run_as and not IS_WINDOWS and os.geteuid() == 0:
        subprocess.run(["chown", "-R", f"{cfg.run_as}:{cfg.run_as}", str(log.parent)], check=True)
    # Not a pipe: the server inherits pg_ctl's output handles, and on Windows a
    # captured pipe would then never close.
    out_path = cfg.data / "logs" / "pg_ctl.out"
    with open(out_path, "w") as out:
        r = subprocess.run(_as_user(cfg, [tool(cfg, "pg_ctl"), "start", "-D", str(cfg.pgdata), "-l", str(log), "-w", "-t", "90"]),
                           stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                           env=_env(cfg), creationflags=0x08000000 if IS_WINDOWS else 0)
    if r.returncode != 0:
        detail = out_path.read_text(encoding="utf-8", errors="replace").strip() or (log.read_text(encoding="utf-8", errors="replace")[-800:] if log.exists() else "")
        raise PostgresError(f"pg_ctl start failed: {detail[-800:]}")


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
