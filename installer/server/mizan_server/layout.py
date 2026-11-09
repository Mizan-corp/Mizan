"""Where things live.

The program (read-only, replaced by updates):
    <install>/server/mizan-server[.exe]   this program
    <install>/pgsql/                      PostgreSQL 16
    <install>/web/                        the built app
    <install>/VERSION

The data (kept across updates and, unless asked, uninstalls):
    <data>/config.json   ports, database password, secret key, mode
    <data>/pg/           the PostgreSQL cluster
    <data>/mizan/        licence key, installation id, state (app.onprem.state)
    <data>/backups/      database backups
    <data>/tls/          LAN certificates
    <data>/uploads/      files uploaded in the app
    <data>/logs/
"""
from __future__ import annotations

import json
import os
import secrets
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

IS_WINDOWS = os.name == "nt"
EXE = ".exe" if IS_WINDOWS else ""


def is_admin() -> bool:
    if IS_WINDOWS:
        try:
            import ctypes

            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    return os.geteuid() == 0


def install_root() -> Path:
    """The folder holding server/, pgsql/ and web/."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent.parent
    # From source (development): installer/build/payload if built, else the repo.
    env = os.environ.get("MIZAN_INSTALL_ROOT")
    return Path(env).resolve() if env else Path(__file__).resolve().parents[2] / "build" / "payload"


def default_data_dir() -> Path:
    if os.environ.get("MIZAN_HOME"):
        return Path(os.environ["MIZAN_HOME"]).expanduser()
    if IS_WINDOWS:
        return Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Mizan"
    if is_admin():
        return Path("/var/lib/mizan")
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "mizan"


def default_install_dir() -> Path:
    if IS_WINDOWS:
        return Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Mizan"
    if is_admin():
        return Path("/opt/mizan")
    return Path.home() / ".local" / "opt" / "mizan"


def version() -> str:
    path = install_root() / "VERSION"
    return path.read_text(encoding="utf-8").strip() if path.exists() else "0.0.0-dev"


@dataclass
class Config:
    mode: str  # desktop | lan
    install_dir: str
    data_dir: str
    http_host: str
    http_port: int
    tls: bool
    db_port: int
    db_password: str
    secret_key: str = field(default_factory=lambda: secrets.token_hex(32))
    db_user: str = "mizan"
    db_name: str = "mizan"
    cloud_url: str = "https://mizan-co-owner-api.vercel.app/api"
    app_env: str = "production"
    run_as: str | None = None  # Linux system user for a root install
    # Testing only: verify licences with this public key instead of production's.
    licence_public_key: str = ""

    @property
    def data(self) -> Path:
        return Path(self.data_dir)

    @property
    def install(self) -> Path:
        return Path(self.install_dir)

    @property
    def pgdata(self) -> Path:
        return self.data / "pg"

    @property
    def pgbin(self) -> Path:
        return self.install / "pgsql" / "bin"

    @property
    def url(self) -> str:
        host = "localhost" if self.http_host in ("127.0.0.1", "0.0.0.0") else self.http_host
        scheme = "https" if self.tls else "http"
        default = 443 if self.tls else 80
        return f"{scheme}://{host}" + ("" if self.http_port == default else f":{self.http_port}")

    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@127.0.0.1:{self.db_port}/{self.db_name}"

    def save(self) -> Path:
        path = self.data / "config.json"
        self.data.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        os.replace(tmp, path)
        if not IS_WINDOWS:
            os.chmod(path, 0o600)
        return path

    @classmethod
    def load(cls, data_dir: Path | None = None) -> Config:
        candidates = [Path(os.environ["MIZAN_CONFIG"])] if os.environ.get("MIZAN_CONFIG") else []
        candidates.append((data_dir or default_data_dir()) / "config.json")
        for path in candidates:
            if path.exists():
                return cls(**json.loads(path.read_text(encoding="utf-8")))
        raise FileNotFoundError("Mizan isn't installed here (no config.json). Run `mizan-server install`.")

    def app_environment(self) -> dict[str, str]:
        """The environment the Mizan API runs with."""
        return {
            "DATABASE_URL": self.database_url(),
            "SECRET_KEY": self.secret_key,
            "APP_ENV": self.app_env,
            "MIZAN_MODE": self.mode,
            "MIZAN_WEB_DIR": str(self.install / "web"),
            "MIZAN_DATA_DIR": str(self.data / "mizan"),
            "MIZAN_CLOUD_URL": self.cloud_url,
            "MIZAN_VERSION": version(),
            "UPLOAD_DIR": str(self.data / "uploads"),
            "UPDATES_DIR": str(self.data / "updates"),
            "CORS_ORIGINS": "[]",
            **({"LICENSE_PUBLIC_KEY": self.licence_public_key} if self.licence_public_key else {}),
        }
