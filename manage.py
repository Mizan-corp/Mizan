#!/usr/bin/env python3
"""
manage.py — one command line for the whole Mizan monorepo.

    python manage.py setup                         first run: deps, stack, migrations, first admin
    python manage.py doctor                        check tools, dependencies and stack health

    python manage.py stack  up | down | restart | status | logs [svc] | build | update | shell <svc>
    python manage.py db     migrate [--production] | backup | restore <file> | backups | reset | baseline | export | psql
    python manage.py dev    [system|website|owner|admin|all]       run frontends (default: all)
    python manage.py build  [system|website|owner|admin|all]       type-check and build frontends
    python manage.py test   [unit|backend|e2e|all]           run test suites (default: unit + backend)
    python manage.py lint                                   ruff + TypeScript
    python manage.py check                                  lint + unit/backend tests + builds
    python manage.py vercel status | redeploy <project> | domains
    python manage.py cron   [--job NAME]                    background jobs in the system API

Add --yes to skip confirmations and --verbose to print every command.
Only the Python standard library is needed to run this file.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
BACKUPS = ROOT / "backups"
BASELINE = ROOT / "shared" / "backend" / "app" / "db" / "baseline_schema.sql"
SHARED_BACKEND = ROOT / "shared" / "backend"
COMPOSE = ["docker", "compose", "-f", str(ROOT / "docker-compose.yml")]

DB_SERVICE, DB_NAME, DB_USER = "db", "inventory_db", "postgres"
DB_URL_HOST = f"postgresql://{DB_USER}:postgres@localhost:5433/{DB_NAME}"
TEST_SECRET = "local-dev-only-secret-key-change-me-0123456789abcdef"
VERCEL_TEAM = os.environ.get("VERCEL_TEAM", "ammar0xfs-projects")
BACKUP_RETENTION = 10


# ─── The products ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class App:
    name: str
    title: str
    dev_port: int
    api_service: str
    api_port: int
    vercel_frontend: str
    vercel_api: str
    domain: str
    api_domain: str

    @property
    def frontend(self) -> Path:
        return ROOT / self.name / "frontend"

    @property
    def workspace(self) -> str:
        return f"{self.name}/frontend"

    @property
    def health_url(self) -> str:
        return f"http://localhost:{self.api_port}/health"


APPS: dict[str, App] = {
    a.name: a
    for a in (
        App("system", "the ERP", 5173, "system-api", 8000,
            "mizan-system", "mizan-system-api", "mizan-co-app.vercel.app", "mizan-co-api.vercel.app"),
        App("website", "landing, signup, onboarding", 5174, "website-api", 8001,
            "mizan-website", "mizan-website-api", "mizan-co.vercel.app", "mizan-co-web-api.vercel.app"),
        App("admin", "admin panel (Mizan team)", 5175, "admin-api", 8002,
            "mizan-admin", "mizan-admin-api", "mizan-co-admin.vercel.app", "mizan-co-admin-api.vercel.app"),
        App("owner", "owner panel (workspaces, subscriptions)", 5176, "owner-api", 8003,
            "mizan-owner", "mizan-owner-api", "mizan-co-owner.vercel.app", "mizan-co-owner-api.vercel.app"),
    )
}
SYSTEM = APPS["system"]


# ─── Output & process helpers ───────────────────────────────────────────────

VERBOSE = False
_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOR else text


def info(msg: str) -> None:
    print(msg, flush=True)


def ok(msg: str) -> None:
    print(_c("32", "✔ ") + msg, flush=True)


def warn(msg: str) -> None:
    print(_c("33", "! ") + msg, flush=True)


def step(msg: str) -> None:
    print(_c("1;36", f"\n▸ {msg}"), flush=True)


def die(msg: str, code: int = 1) -> None:
    print(_c("31", "✘ ") + msg, file=sys.stderr, flush=True)
    sys.exit(code)


def run(
    cmd: Sequence[str],
    *,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
    capture: bool = False,
    input_text: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
    if VERBOSE:
        info(_c("2", "  $ " + " ".join(str(c) for c in cmd)))
    result = subprocess.run(
        [str(c) for c in cmd], cwd=cwd, env={**os.environ, **(env or {})},
        capture_output=capture or input_text is not None, text=True, input=input_text, check=False,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or "").strip()[-800:]
        die(f"`{' '.join(str(c) for c in cmd[:4])} …` failed (exit {result.returncode})" + (f"\n{detail}" if detail else ""))
    return result


def confirm(question: str, opts: argparse.Namespace) -> None:
    if getattr(opts, "yes", False):
        return
    if input(f"{question}\nType 'yes' to continue: ").strip().lower() != "yes":
        info("Cancelled.")
        sys.exit(0)


def stamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def need(tool: str, hint: str) -> None:
    if not shutil.which(tool):
        die(f"`{tool}` not found. {hint}")


def python_bin() -> str:
    """The repo's virtualenv if it exists, otherwise the current interpreter."""
    bin_dir = "Scripts" if platform.system() == "Windows" else "bin"
    candidate = VENV / bin_dir / ("python.exe" if platform.system() == "Windows" else "python")
    return str(candidate) if candidate.exists() else sys.executable


def pick_apps(name: str) -> list[App]:
    return list(APPS.values()) if name == "all" else [APPS[name]]


# ─── docker compose ─────────────────────────────────────────────────────────


def compose(*args: str, **kw) -> subprocess.CompletedProcess:
    return run([*COMPOSE, *args], **kw)


def psql(sql: str, *, database: str = DB_NAME, check: bool = False) -> subprocess.CompletedProcess:
    return compose("exec", "-T", DB_SERVICE, "psql", "-U", DB_USER, "-d", database, "-v", "ON_ERROR_STOP=0",
                   input_text=sql, check=check)


def pg_dump(*extra: str) -> str:
    return compose("exec", "-T", DB_SERVICE, "pg_dump", "-U", DB_USER, "--no-password", DB_NAME, *extra,
                   capture=True).stdout


def db_ready() -> bool:
    return compose("exec", "-T", DB_SERVICE, "pg_isready", "-U", DB_USER, capture=True, check=False).returncode == 0


def require_db() -> None:
    need("docker", "Install Docker: https://docs.docker.com/get-docker/")
    if not db_ready():
        die("The database isn't running. Start the stack: python manage.py stack up")


def api_health() -> dict[str, bool]:
    status = {}
    for app in APPS.values():
        try:
            with urllib.request.urlopen(app.health_url, timeout=4) as r:
                status[app.api_service] = b'"ok"' in r.read()
        except (urllib.error.URLError, OSError):
            status[app.api_service] = False
    return status


def wait_for_apis(timeout: int = 180) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if all(api_health().values()):
            return
        time.sleep(2)
    down = [name for name, up in api_health().items() if not up]
    die(f"Not healthy after {timeout}s: {', '.join(down)}. See: python manage.py stack logs")


def print_stack_status() -> None:
    compose("ps", check=False)
    info("")
    for app in APPS.values():
        up = api_health()[app.api_service]
        info(f"  {_c('32', '●') if up else _c('31', '●')} {app.api_service:<12} {app.health_url}")


# ─── Migrations ─────────────────────────────────────────────────────────────

# Every statement runs with RLS bypassed and the first workspace bound, so
# pre-tenancy INSERTs into tenant-scoped tables get a valid tenant_id default.
_PREAMBLE = (
    "SELECT set_config('app.tenant_id', COALESCE((SELECT id::text FROM tenants "
    "ORDER BY created_at LIMIT 1), ''), false), set_config('app.bypass', 'on', false);\n"
)


def _migration_list():
    """The tracked migrations live in the shared kernel (pure Python, no dependencies)."""
    sys.path.insert(0, str(SHARED_BACKEND))
    from app.db.migrations import FOUNDATION_SQL, MIGRATIONS, split_statements

    return FOUNDATION_SQL, MIGRATIONS, split_statements


def _apply(sql: str, split: Callable[[str], list[str]]) -> bool:
    """Run statement by statement so one failure never silently aborts the rest."""
    success = True
    for stmt in split(sql):
        r = psql(_PREAMBLE + stmt + ";")
        errors = [ln for ln in r.stderr.splitlines()
                  if "ERROR" in ln and "already exists" not in ln and "does not exist" not in ln]
        if errors or r.returncode != 0:
            success = False
            warn(f"   {errors[0] if errors else r.returncode}: {stmt.strip()[:90]}")
    return success


def _apply_python(target: str) -> bool:
    """A data migration written in Python ("module:function"), run in the system API container
    with RLS bypassed."""
    module_name, _, fn_name = target.partition(":")
    script = f"""
import asyncio
import main  # noqa: F401  (loads models and settings)
from sqlalchemy import text
from app.db.base import AsyncSessionLocal
from {module_name} import {fn_name}

async def go():
    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT set_config('app.bypass', 'on', false)"))
        await {fn_name}(db)
        await db.commit()

asyncio.run(go())
"""
    r = compose("exec", "-T", SYSTEM.api_service, "python", "-c", script, capture=True, check=False)
    if r.returncode != 0:
        warn(f"   {(r.stderr or r.stdout).strip().splitlines()[-1] if (r.stderr or r.stdout).strip() else r.returncode}")
    return r.returncode == 0


def migrate() -> None:
    foundation, migrations, split = _migration_list()
    require_db()
    step("Migrations")
    _apply(foundation, split)
    applied = set(psql("SELECT id FROM schema_migrations;").stdout.split())
    done = 0
    for name, sql in migrations:
        if name in applied:
            done += 1
            continue
        if sql.startswith("python:"):
            ok_ = _apply_python(sql.removeprefix("python:"))
        else:
            ok_ = _apply(sql, split)
        if ok_:
            psql(f"INSERT INTO schema_migrations (id) VALUES ('{name}') ON CONFLICT DO NOTHING;", check=True)
            ok(name)
            done += 1
        else:
            warn(f"{name} failed")
    if done < len(migrations):
        die(f"{done}/{len(migrations)} migrations applied.")
    ok(f"{done}/{len(migrations)} migrations applied")

    # First-run bootstrap: the first admin on an empty database; no-op otherwise.
    r = compose("exec", "-T", SYSTEM.api_service, "python", "-m", "app.db.bootstrap", capture=True)
    ok(f"Bootstrap: {r.stdout.strip()}")


# ─── production migrations (#64) ────────────────────────────────────────────

PG_IMAGE = "postgres:18"  # pg_dump must be at least the server's version (Neon runs 18)
PROD_VERCEL_PROJECT = "mizan-system-api"


def _production_url() -> str:
    """The production database URL: MIZAN_PROD_DATABASE_URL, else the system API's Vercel env.
    Returned as a plain libpq URL on the direct host (DDL and pg_dump bypass the pooler)."""
    url = os.environ.get("MIZAN_PROD_DATABASE_URL", "").strip()
    if not url:
        need("vercel", "Install the Vercel CLI and run `vercel login`, or set MIZAN_PROD_DATABASE_URL.")
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            run(["vercel", "link", "--project", PROD_VERCEL_PROJECT, "--yes"], cwd=Path(tmp), capture=True)
            run(["vercel", "env", "pull", ".env.prod", "--environment", "production", "--yes"], cwd=Path(tmp), capture=True)
            for line in (Path(tmp) / ".env.prod").read_text().splitlines():
                if line.startswith("DATABASE_URL="):
                    url = line.split("=", 1)[1].strip().strip('"')
        if not url:
            die(f"No DATABASE_URL in the {PROD_VERCEL_PROJECT} production environment.")
    url = url.replace("postgresql+asyncpg://", "postgresql://", 1).replace("-pooler.", ".", 1)
    return url.replace("&channel_binding=require", "").replace("?channel_binding=require&", "?")


def _prod_psql(url: str, sql: str, *, single_transaction: bool = False) -> subprocess.CompletedProcess:
    args = ["docker", "run", "--rm", "-i", "--network", "host", PG_IMAGE, "psql", url, "-v", "ON_ERROR_STOP=1", "-At"]
    if single_transaction:
        args.append("--single-transaction")
    return run(args, input_text=sql, check=False)


def _prod_python_step(url: str, name: str, target: str) -> subprocess.CompletedProcess:
    """A Python migration step against production, run locally with the shared backend; the
    migration is recorded in the same transaction."""
    module_name, _, fn_name = target.partition(":")
    script = f"""
import asyncio, sys
sys.path.insert(0, {str(SHARED_BACKEND)!r})
from sqlalchemy import text
from app.models.registry import load_all_models
from app.db.base import AsyncSessionLocal
from {module_name} import {fn_name}

async def go():
    load_all_models()
    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT set_config('app.bypass', 'on', false)"))
        await {fn_name}(db)
        await db.execute(text("INSERT INTO schema_migrations (id) VALUES (:id) ON CONFLICT DO NOTHING"), {{"id": {name!r}}})
        await db.commit()

asyncio.run(go())
"""
    env = {"DATABASE_URL": url.replace("postgresql://", "postgresql+asyncpg://", 1),
           "SECRET_KEY": os.environ.get("SECRET_KEY", "migration-only-" + "x" * 32), "MIZAN_DB_APP_ROLE": ""}
    return run([python_bin(), "-c", script], env=env, capture=True, check=False)


def _schema_drift(url: str) -> list[str]:
    """Model columns the database lacks. Local databases get tables from create_all, which hides
    a missing migration; production only has what migrations added."""
    script = f"""
import os, sys
sys.path.insert(0, {str(SHARED_BACKEND)!r})
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:y@localhost/z")
os.environ.setdefault("SECRET_KEY", "x" * 40)
from app.models.registry import load_all_models
load_all_models()
from app.db.base import Base
for t in Base.metadata.sorted_tables:
    for c in t.columns:
        print(t.name + "." + c.name)
"""
    models = run([python_bin(), "-c", script], capture=True, check=False).stdout.split()
    r = _prod_psql(url, "SELECT table_name || '.' || column_name FROM information_schema.columns WHERE table_schema = 'public';")
    have = set(r.stdout.split())
    tables = {c.split(".")[0] for c in have}
    return sorted(c for c in models if c.split(".")[0] in tables and c not in have)



def _backup_production(url: str) -> Path:
    step("Backup")
    BACKUPS.mkdir(exist_ok=True)
    out = BACKUPS / f"prod_{stamp()}.dump"
    with out.open("wb") as fh:
        dump = subprocess.run(["docker", "run", "--rm", "--network", "host", PG_IMAGE, "pg_dump", "-Fc", url], stdout=fh,
                              stderr=subprocess.PIPE, text=False, check=False)
    if dump.returncode != 0 or out.stat().st_size < 10_000:
        die(f"Backup failed: {dump.stderr.decode(errors='replace').strip()[-300:]}")
    check = subprocess.run(["docker", "run", "--rm", "-v", f"{BACKUPS}:/b", PG_IMAGE, "pg_restore", "-l", f"/b/{out.name}"],
                           capture_output=True, text=True, check=False)
    tables = sum(1 for line in check.stdout.splitlines() if "TABLE DATA" in line)
    if check.returncode != 0 or not tables:
        die("The backup can't be read back; nothing was changed.")
    ok(f"Backup: {out.relative_to(ROOT)} ({out.stat().st_size // 1024:,} KB, {tables} tables). It holds customer data: keep it private.")
    return out


def migrate_production(opts: argparse.Namespace) -> None:
    """Backup, then apply pending migrations to production in order, each in one transaction.
    Run it BEFORE deploying code that needs them (migrations stay backward compatible)."""
    need("docker", "Install Docker: https://docs.docker.com/get-docker/")
    _, migrations, _ = _migration_list()
    url = _production_url()
    host = url.split("@", 1)[-1].split("/", 1)[0]
    step(f"Production database: {host}")
    r = _prod_psql(url, "SELECT id FROM schema_migrations;")
    if r.returncode != 0:
        die(f"Can't read schema_migrations: {(r.stderr or '').strip()[:200]}")
    applied = set(r.stdout.split())
    pending = [(n, sql) for n, sql in migrations if n not in applied]
    unknown = sorted(applied - {n for n, _ in migrations})
    if unknown:
        warn(f"Applied in production but not in this branch: {', '.join(unknown)}")
    if not pending:
        ok(f"Nothing pending ({len(applied)} applied).")
        drift = _schema_drift(url)
        if drift:
            die(f"Columns the code expects but the database lacks (write a migration): {', '.join(drift)}")
        ok("Schema matches the models.")
        return
    for n, sql in pending:
        info(f"  pending: {n}{'  (python)' if sql.startswith('python:') else ''}")

    out = None
    if getattr(opts, "no_backup", False):
        warn("No backup taken (--no-backup): Neon's point-in-time restore is the way back.")
    else:
        out = _backup_production(url)

    confirm(f"Apply {len(pending)} migration(s) to {host}?", opts)
    step("Migrations")
    for n, sql in pending:
        if sql.startswith("python:"):
            res = _prod_python_step(url, n, sql.removeprefix("python:"))
        else:
            res = _prod_psql(url, sql + f"\nINSERT INTO schema_migrations (id) VALUES ('{n}') ON CONFLICT DO NOTHING;\n",
                             single_transaction=True)
        if res.returncode != 0:
            err = ((res.stderr or "") + (res.stdout or "")).strip().splitlines()
            restore = (f"docker run --rm -i {PG_IMAGE} pg_restore --clean -d <url> < {out}" if out
                       else "Neon's point-in-time restore (console: Branches > Restore)")
            die(f"{n} failed and was rolled back; later ones were not run. {err[-1] if err else ''}\n"
                f"   Restore if needed: {restore}")
        ok(n)
    drift = _schema_drift(url)
    if drift:
        die(f"Migrated, but columns the code expects are still missing (write a migration first, "
            f"don't deploy): {', '.join(drift)}")
    ok(f"{len(pending)} migration(s) applied to production; schema matches the models. Deploy the code now.")


# ─── setup / doctor ─────────────────────────────────────────────────────────


def cmd_setup(opts: argparse.Namespace) -> None:
    """First run: install dependencies, start the stack, migrate, create the first admin."""
    need("docker", "Install Docker: https://docs.docker.com/get-docker/")
    need("npm", "Install Node.js 22+: https://nodejs.org")

    step("Frontend dependencies (npm workspaces)")
    run(["npm", "install", "--no-audit", "--no-fund"])

    if not opts.skip_python:
        step(f"Python environment ({VENV.name}/) for tests and lint")
        _create_venv()

    step("Database + system, website, owner and admin APIs")
    compose("up", "-d", "--build")
    wait_for_apis()
    migrate()

    info("")
    ok("Ready. Sign in with ammar / changeme (unless you set MIZAN_ADMIN_USERNAME / MIZAN_ADMIN_PASSWORD).")
    info("   Run the frontends:  python manage.py dev")


def _create_venv() -> None:
    reqs = ["-r", str(SHARED_BACKEND / "requirements-dev.txt"), "-r", str(ROOT / "e2e" / "requirements.txt"), "ruff"]
    if shutil.which("uv"):
        run(["uv", "venv", "--allow-existing", "-q", "-p", "3.12", str(VENV)])
        run(["uv", "pip", "install", "-q", "-p", python_bin(), "-e", str(SHARED_BACKEND), *reqs])
    else:
        if not VENV.exists():
            run([sys.executable, "-m", "venv", str(VENV)])
        run([python_bin(), "-m", "pip", "install", "-q", "-e", str(SHARED_BACKEND), *reqs])
    ok(f"{VENV.relative_to(ROOT)}/ ready")


def cmd_doctor(opts: argparse.Namespace) -> None:
    """Check tools, dependencies and stack health."""
    problems = 0

    def report(good: bool, label: str, detail: str = "", fix: str = "") -> None:
        nonlocal problems
        if good:
            ok(f"{label} {_c('2', detail)}")
        else:
            problems += 1
            warn(f"{label} {detail}" + (f"\n    → {fix}" if fix else ""))

    def version(cmd: list[str]) -> str:
        try:
            return subprocess.run(cmd, capture_output=True, text=True, check=False).stdout.strip().splitlines()[0]
        except (OSError, IndexError):
            return ""

    step("Tools")
    node = version(["node", "--version"])
    report(bool(node) and int(node.lstrip("v").split(".")[0]) >= 22, "Node.js 22+", node or "missing", "https://nodejs.org")
    report(bool(shutil.which("npm")), "npm", version(["npm", "--version"]))
    report(bool(shutil.which("docker")), "Docker", version(["docker", "--version"]), "https://docs.docker.com/get-docker/")
    report(sys.version_info >= (3, 12), "Python 3.12+", platform.python_version())

    step("Dependencies")
    report((ROOT / "node_modules").exists(), "npm workspaces installed", "", "npm install")
    report(VENV.exists(), f"{VENV.name}/ (tests, lint)", "", "python manage.py setup")

    step("Stack")
    if shutil.which("docker") and db_ready():
        report(True, "database", f"localhost:5433/{DB_NAME}")
        for app in APPS.values():
            report(api_health()[app.api_service], app.api_service, app.health_url, "python manage.py stack logs " + app.api_service)
    else:
        report(False, "database", "not running", "python manage.py stack up")

    info("")
    if problems:
        die(f"{problems} problem(s) found.")
    ok("All good.")


# ─── stack ──────────────────────────────────────────────────────────────────


def cmd_stack(opts: argparse.Namespace) -> None:
    """Database + the three APIs (docker compose)."""
    need("docker", "Install Docker: https://docs.docker.com/get-docker/")
    action = opts.action
    if action == "up":
        compose("up", "-d", *(["--build"] if opts.build else []))
        wait_for_apis()
        print_stack_status()
    elif action == "down":
        compose("down")
        ok("Stopped (data kept). `db reset` wipes it.")
    elif action == "restart":
        compose("restart", *([opts.service] if opts.service else []))
        wait_for_apis()
        print_stack_status()
    elif action == "status":
        print_stack_status()
    elif action == "logs":
        try:
            compose("logs", "--tail=100", "-f", *([opts.service] if opts.service else []), check=False)
        except KeyboardInterrupt:
            pass
    elif action == "build":
        compose("build", *([opts.service] if opts.service else []))
        ok("Images built")
    elif action == "update":
        confirm("Back up, rebuild and restart the stack, then migrate?", opts)
        _backup()
        compose("up", "-d", "--build")
        wait_for_apis()
        migrate()
        ok("Updated")
    elif action == "shell":
        service = opts.service or SYSTEM.api_service
        shell = "psql" if service == DB_SERVICE else "sh"
        cmd = ["psql", "-U", DB_USER, "-d", DB_NAME] if shell == "psql" else ["sh"]
        os.execvp(COMPOSE[0], [*COMPOSE, "exec", service, *cmd])


# ─── db ─────────────────────────────────────────────────────────────────────

MASTER_TABLES = (
    "users", "warehouses", "categories", "subcategories", "products", "suppliers", "customers",
    "payment_wallets", "safes", "store_settings", "hr_employees", "hr_settings", "financial_categories",
)


def _backup() -> Path:
    require_db()
    BACKUPS.mkdir(exist_ok=True)
    out = BACKUPS / f"backup_{stamp()}.sql"
    out.write_text(pg_dump(), encoding="utf-8")
    ok(f"Backup: {out.relative_to(ROOT)} ({out.stat().st_size // 1024:,} KB)")
    for old in sorted(BACKUPS.glob("backup_*.sql"))[:-BACKUP_RETENTION]:
        old.unlink()
        info(f"  pruned {old.name}")
    return out


def _list_backups() -> None:
    files = sorted(BACKUPS.glob("backup_*.sql")) if BACKUPS.exists() else []
    if not files:
        info(f"No backups in {BACKUPS.relative_to(ROOT)}/")
    for f in files:
        info(f"  {f.name}  ({f.stat().st_size // 1024:,} KB)")


def _decode_sql(raw: bytes) -> str:
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16-le" if raw[:2] == b"\xff\xfe" else "utf-16-be")
    return raw.decode("utf-8", errors="replace")


def cmd_db(opts: argparse.Namespace) -> None:
    """Migrations, backups and the baseline schema."""
    need("docker", "Install Docker: https://docs.docker.com/get-docker/")
    action = opts.action
    if action == "migrate":
        migrate_production(opts) if getattr(opts, "production", False) else migrate()
    elif action == "backup":
        _backup()
    elif action == "backups":
        _list_backups()
    elif action == "restore":
        path = next((p for p in (Path(opts.file or ""), BACKUPS / (opts.file or "")) if opts.file and p.is_file()), None)
        if not path:
            _list_backups()
            die(f"Backup not found: {opts.file or '(give a file name)'}")
        confirm(f"⚠️  Replace ALL data with {path.name}?", opts)
        require_db()
        services = [a.api_service for a in APPS.values()]
        compose("stop", *services)
        for sql in (f"DROP DATABASE IF EXISTS {DB_NAME};", f"CREATE DATABASE {DB_NAME};"):
            psql(sql, database="postgres", check=True)
        errors = [ln for ln in psql(_decode_sql(path.read_bytes())).stderr.splitlines() if "ERROR" in ln]
        if errors:
            warn(f"{len(errors)} errors while restoring, first: {errors[0]}")
        compose("start", *services)
        wait_for_apis()
        migrate()
        ok(f"Restored {path.name}")
    elif action == "reset":
        confirm("⚠️  Delete ALL data and start from an empty database?", opts)
        compose("down", "-v")
        compose("up", "-d")
        wait_for_apis()
        migrate()
        ok("Empty database with the first admin")
    elif action == "baseline":
        require_db()
        header = ("-- Mizan baseline schema (structure only, no data). Loaded into a brand-new\n"
                  "-- database by docker compose; refreshed with `python manage.py db baseline`.\n\n")
        sql = pg_dump("--schema-only", "--no-owner", "--no-privileges")
        BASELINE.write_text(header + sql, encoding="utf-8")
        ok(f"{BASELINE.relative_to(ROOT)} refreshed ({sql.count(chr(10)):,} lines)")
    elif action == "export":
        require_db()
        BACKUPS.mkdir(exist_ok=True)
        out = BACKUPS / f"master_data_{stamp()}.sql"
        parts = [pg_dump("--schema-only", "--no-owner", "--no-privileges")]
        parts += [pg_dump("--data-only", "--no-owner", "--no-privileges", f"--table={t}") for t in MASTER_TABLES]
        out.write_text("\n".join(parts), encoding="utf-8")
        ok(f"Master data (no transactions): {out.relative_to(ROOT)}")
    elif action == "psql":
        require_db()
        os.execvp(COMPOSE[0], [*COMPOSE, "exec", DB_SERVICE, "psql", "-U", DB_USER, "-d", DB_NAME])


# ─── Frontends: dev / build ─────────────────────────────────────────────────


def _need_node_modules() -> None:
    need("npm", "Install Node.js 22+: https://nodejs.org")
    if not (ROOT / "node_modules").exists():
        step("npm install")
        run(["npm", "install", "--no-audit", "--no-fund"])


def _stream(proc: subprocess.Popen, label: str, color: str) -> None:
    assert proc.stdout is not None
    for line in proc.stdout:
        print(f"{_c(color, f'{label:>8} │')} {line}", end="", flush=True)


def cmd_dev(opts: argparse.Namespace) -> None:
    """Run frontend dev servers in one terminal. Each proxies /api to its own API."""
    _need_node_modules()
    apps = pick_apps(opts.app)
    down = [a.api_service for a in apps if not api_health()[a.api_service]]
    if down:
        warn(f"API not running: {', '.join(down)}. Start it with: python manage.py stack up")
    for a in apps:
        info(f"  {a.name:<8} http://localhost:{a.dev_port}   ({a.title})")
    procs: list[subprocess.Popen] = []
    colors = ("35", "34", "33")
    posix = os.name == "posix"
    for a, color in zip(apps, colors[: len(apps)], strict=True):
        # Own process group per app, so stopping it also stops vite under npm.
        p = subprocess.Popen(["npm", "run", "dev", "-w", a.workspace], cwd=ROOT, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=posix)
        procs.append(p)
        threading.Thread(target=_stream, args=(p, a.name, color), daemon=True).start()

    def _interrupt(*_: object) -> None:
        raise KeyboardInterrupt

    # Ctrl+C or a termination signal stops everything (even if SIGINT was inherited as ignored).
    signal.signal(signal.SIGINT, _interrupt)
    if posix:
        signal.signal(signal.SIGTERM, _interrupt)
    try:
        while all(p.poll() is None for p in procs):
            time.sleep(0.5)
    except KeyboardInterrupt:
        info("\nStopping...")
    finally:
        for p in procs:
            if p.poll() is None:
                if posix:
                    os.killpg(p.pid, signal.SIGTERM)
                else:
                    p.terminate()
        for p in procs:
            try:
                p.wait(timeout=8)
            except subprocess.TimeoutExpired:
                if posix:
                    os.killpg(p.pid, signal.SIGKILL)
                else:
                    p.kill()


def cmd_build(opts: argparse.Namespace) -> None:
    """Type-check and build frontends."""
    _need_node_modules()
    for a in pick_apps(opts.app):
        step(f"Build {a.name}")
        run(["npm", "run", "build", "-w", a.workspace])
        ok(f"{a.workspace}/dist")


# ─── Quality: test / lint / check ───────────────────────────────────────────


def _backend_env() -> dict[str, str]:
    return {
        "DATABASE_URL": DB_URL_HOST.replace("postgresql://", "postgresql+asyncpg://"),
        "SECRET_KEY": os.environ.get("SECRET_KEY", TEST_SECRET),
        "PYTHONPATH": os.pathsep.join([".", str(SHARED_BACKEND)]),
    }


def _test_unit() -> None:
    _need_node_modules()
    step("Frontend unit tests")
    run(["npm", "test"])


def _test_backend() -> None:
    require_db()
    for app in ("system", "owner", "admin"):
        step(f"Backend tests ({app}/backend/tests)")
        run([python_bin(), "-m", "pytest", "-q", "--no-header"], cwd=ROOT / app / "backend", env=_backend_env())


def _test_e2e() -> None:
    require_db()
    if not api_health()[SYSTEM.api_service]:
        die("system-api isn't running. Start the stack: python manage.py stack up")
    step("End-to-end API suite (e2e/)")
    run([python_bin(), "-m", "pytest", "-q", "--no-header"], cwd=ROOT / "e2e",
        env={"E2E_API_BASE": f"http://localhost:{SYSTEM.api_port}", "E2E_DATABASE_URL": DB_URL_HOST})


def cmd_test(opts: argparse.Namespace) -> None:
    """Run test suites."""
    suites = {"unit": [_test_unit], "backend": [_test_backend], "e2e": [_test_e2e],
              "all": [_test_unit, _test_backend, _test_e2e], None: [_test_unit, _test_backend]}[opts.suite]
    for suite in suites:
        suite()
    ok("Tests passed")


def _lint() -> None:
    step("ruff (Python)")
    ruff = [python_bin(), "-m", "ruff"] if VENV.exists() else ["ruff"]
    if not VENV.exists():
        need("ruff", "Run `python manage.py setup` or `pip install ruff`.")
    run([*ruff, "check", "shared/backend", "system/backend", "website/backend", "owner/backend", "admin/backend",
         "--select", "E9,F63,F7,F82,F821,F601,F401,F841"])
    ok("ruff")
    _need_node_modules()
    for a in APPS.values():
        step(f"TypeScript ({a.name})")
        run(["npx", "tsc", "-b", "--noEmit"], cwd=a.frontend)
        ok(f"tsc {a.name}")


def cmd_lint(opts: argparse.Namespace) -> None:
    """ruff + TypeScript for all three apps."""
    _lint()


def cmd_check(opts: argparse.Namespace) -> None:
    """Everything CI checks except e2e: lint, unit and backend tests, builds."""
    _lint()
    _test_unit()
    if db_ready():
        _test_backend()
    else:
        warn("Skipping backend tests (database not running).")
    cmd_build(argparse.Namespace(app="all"))
    info("")
    ok("All checks passed")


# ─── Vercel ─────────────────────────────────────────────────────────────────


def _vercel_token() -> str:
    token = os.environ.get("VERCEL_TOKEN")
    if token:
        return token
    for p in (Path.home() / ".local/share/com.vercel.cli/auth.json",
              Path.home() / "Library/Application Support/com.vercel.cli/auth.json",
              Path(os.environ.get("APPDATA", "")) / "com.vercel.cli/Data/auth.json"):
        if p.is_file():
            return json.loads(p.read_text())["token"]
    die("No Vercel token. Run `vercel login` or set VERCEL_TOKEN.")
    return ""


def _vercel(method: str, path: str, body: dict | None = None) -> dict:
    sep = "&" if "?" in path else "?"
    req = urllib.request.Request(
        f"https://api.vercel.com{path}{sep}teamId={VERCEL_TEAM}", method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {_vercel_token()}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        die(f"Vercel API {method} {path}: {e.code} {e.read().decode()[:300]}")
        return {}


def _vercel_projects() -> list[tuple[App, str, str]]:
    return [(a, proj, dom) for a in APPS.values()
            for proj, dom in ((a.vercel_frontend, a.domain), (a.vercel_api, a.api_domain))]


def _production(project: str) -> tuple[dict, dict]:
    """(live, newest): the deployment serving production, and the newest attempt.

    A newer attempt may be CANCELED on purpose: the per-folder ignore rule skips
    builds when the project's folder didn't change. That's not a problem.
    """
    pid = _vercel("GET", f"/v9/projects/{project}")["id"]
    deps = _vercel("GET", f"/v6/deployments?projectId={pid}&target=production&limit=20")["deployments"]
    live = next((d for d in deps if d.get("state") == "READY"), {})
    return live, (deps[0] if deps else {})


def cmd_vercel(opts: argparse.Namespace) -> None:
    """Production status and redeploys of the six Vercel projects."""
    if opts.action == "status":
        info(f"{'project':<20} {'live':<9} {'age':>5}  {'domain':<32} newest attempt")
        for _, project, domain in _vercel_projects():
            live, newest = _production(project)
            sha = (live.get("meta") or {}).get("githubCommitSha", "")[:7] or "-"
            age = f"{int((time.time() - live['created'] / 1000) // 3600)}h" if live else "-"
            note = ""
            if newest and newest.get("uid") != live.get("uid"):
                state = newest.get("state", "")
                color = "31" if state == "ERROR" else "33" if state != "CANCELED" else "2"
                label = "skipped (no changes)" if state == "CANCELED" else state.lower()
                note = _c(color, f"{label} @ {(newest.get('meta') or {}).get('githubCommitSha', '')[:7]}")
            info(f"{project:<20} {_c('32', f'{sha:<9}')} {age:>5}  {domain:<32} {note}")
    elif opts.action == "domains":
        for _, project, _ in _vercel_projects():
            names = [d["name"] for d in _vercel("GET", f"/v9/projects/{project}/domains")["domains"]]
            info(f"{project:<20} {', '.join(names)}")
    elif opts.action == "redeploy":
        valid = [p for _, p, _ in _vercel_projects()]
        if opts.project not in valid:
            die(f"Unknown project. One of: {', '.join(valid)}")
        d, _ = _production(opts.project)
        if not d:
            die(f"{opts.project} has no production deployment to redeploy.")
        confirm(f"Redeploy {opts.project} to production (from {d['url']})?", opts)
        new = _vercel("POST", "/v13/deployments?forceNew=1",
                      {"name": opts.project, "deploymentId": d["uid"], "target": "production"})
        ok(f"Queued: https://{new.get('url')}  (track with: python manage.py vercel status)")


# ─── cron ───────────────────────────────────────────────────────────────────


def cmd_cron(opts: argparse.Namespace) -> None:
    """Run background automation jobs inside the system API container."""
    call = f"run_job({opts.job!r}, db)" if opts.job else "run_all_jobs(db)"
    script = f"""
import asyncio
import main  # noqa: F401  (loads models and settings)
from app.db.base import AsyncSessionLocal
from app.platform.automation_worker.runner import run_all_jobs, run_job

async def go():
    async with AsyncSessionLocal() as db:
        result = await {call}
        for r in (result if isinstance(result, list) else [result]):
            print(f"[{{str(r.get('status', '')).upper()}}] {{r.get('title', '')}}: {{r.get('message') or r.get('error') or r}}")

asyncio.run(go())
"""
    step(f"Background jobs: {opts.job or 'all'}")
    compose("exec", "-T", SYSTEM.api_service, "python", "-c", script)


# ─── module ─────────────────────────────────────────────────────────────────


def cmd_module(opts: argparse.Namespace) -> None:
    """The ADR-006 module layout: create a module, fill in missing pieces, or check."""
    sys.path.insert(0, str(ROOT / "shared" / "backend"))
    from app.framework import scaffold

    if opts.action == "new":
        if not (opts.activity and opts.id and opts.name):
            die('Usage: manage.py module new <activity> <module_id> "<name>" [--name-en ...] [--kind ...] [--planned]')
        try:
            folder = scaffold.new_module(opts.activity, opts.id, opts.name, opts.name_en or "", opts.kind,
                                         "planned" if opts.planned else "active")
        except ValueError as err:
            die(str(err))
        ok(f"Created {folder.relative_to(ROOT)} and its screens folder")
        return
    if opts.action == "scaffold":
        created = scaffold.scaffold_all()
        ok(f"{len(created)} missing pieces created" if created else "Every module already has the full layout")
        return
    gaps = [(d, scaffold.missing(d, m)) for d, m in scaffold.manifests()]
    gaps = [(d, g) for d, g in gaps if g]
    for d, g in gaps:
        info(f"{d.relative_to(ROOT)}: missing {', '.join(str(p.relative_to(ROOT)) for p in g[:4])}{' …' if len(g) > 4 else ''}")
    if gaps:
        die(f"{len(gaps)} modules are missing parts of the standard structure (python manage.py module scaffold)")
    ok("Every module has the standard structure (docs/MODULE_STANDARD.md)")


# ─── CLI ────────────────────────────────────────────────────────────────────

APP_CHOICES = [*APPS, "all"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="manage.py",
        description="One command line for the Mizan monorepo: stack, database, frontends, tests and deploys.",
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--yes", "-y", action="store_true", default=argparse.SUPPRESS, help="Skip confirmations")
    common.add_argument("--verbose", "-v", action="store_true", default=argparse.SUPPRESS, help="Print every command")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmations")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print every command")
    sub = parser.add_subparsers(dest="command", metavar="<command>", required=True)

    def add(name: str, fn: Callable[[argparse.Namespace], None], help_text: str) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help_text, description=help_text, parents=[common])
        p.set_defaults(fn=fn)
        return p

    p = add("setup", cmd_setup, "First run: dependencies, stack, migrations, first admin")
    p.add_argument("--skip-python", action="store_true", help="Don't create the .venv for tests and lint")
    add("doctor", cmd_doctor, "Check tools, dependencies and stack health")

    p = add("stack", cmd_stack, "Database + the three APIs: up, down, restart, status, logs, build, update, shell")
    p.add_argument("action", choices=["up", "down", "restart", "status", "logs", "build", "update", "shell"])
    p.add_argument("service", nargs="?", help="e.g. system-api, website-api, owner-api, admin-api, db")
    p.add_argument("--build", action="store_true", help="With `up`: rebuild images first")

    p = add("db", cmd_db, "Database: migrate, backup, restore, backups, reset, baseline, export, psql")
    p.add_argument("action", choices=["migrate", "backup", "restore", "backups", "reset", "baseline", "export", "psql"])
    p.add_argument("file", nargs="?", help="With `restore`: a file in backups/ or a path")
    p.add_argument("--production", action="store_true",
                   help="With `migrate`: back up production, then apply its pending migrations (#64)")
    p.add_argument("--no-backup", dest="no_backup", action="store_true",
                   help="With `migrate --production`: skip the pg_dump (CI; Neon's point-in-time restore covers it)")

    p = add("dev", cmd_dev, "Run frontend dev servers (default: all)")
    p.add_argument("app", nargs="?", default="all", choices=APP_CHOICES)
    p = add("build", cmd_build, "Type-check and build frontends (default: all three)")
    p.add_argument("app", nargs="?", default="all", choices=APP_CHOICES)

    p = add("test", cmd_test, "Run tests: unit, backend, e2e or all (default: unit + backend)")
    p.add_argument("suite", nargs="?", default=None, choices=["unit", "backend", "e2e", "all"])
    add("lint", cmd_lint, "ruff (Python) + TypeScript for all three apps")
    add("check", cmd_check, "Lint, unit and backend tests, and builds (CI minus e2e)")

    p = add("vercel", cmd_vercel, "Vercel: status, domains, redeploy <project>")
    p.add_argument("action", choices=["status", "domains", "redeploy"])
    p.add_argument("project", nargs="?", help="With `redeploy`: e.g. mizan-system-api")

    p = add("module", cmd_module, "Modules (docs/MODULE_STANDARD.md): new, scaffold (fill missing files), check")
    p.add_argument("action", choices=["new", "scaffold", "check"])
    p.add_argument("activity", nargs="?", help="With `new`: the home activity, e.g. pharmacy")
    p.add_argument("id", nargs="?", help="With `new`: the module id, e.g. drug_interactions")
    p.add_argument("name", nargs="?", help="With `new`: the Arabic name")
    p.add_argument("--name-en", dest="name_en", help="With `new`: the English name")
    p.add_argument("--kind", default="business", choices=["business", "platform", "integration"])
    p.add_argument("--planned", action="store_true", help="With `new`: lay out a module that is not built yet")

    p = add("cron", cmd_cron, "Run background automation jobs in the system API")
    p.add_argument("--job", help="One job, e.g. auto_close_shifts (default: all)")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    global VERBOSE
    opts = build_parser().parse_args(argv)
    VERBOSE = bool(getattr(opts, "verbose", False))
    try:
        opts.fn(opts)
    except KeyboardInterrupt:
        info("")
        sys.exit(130)


if __name__ == "__main__":
    main()
