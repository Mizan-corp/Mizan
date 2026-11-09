"""Run Mizan in the background and start it with the computer.

- Linux, installed as root: a systemd system service running as user `mizan`.
- Linux, installed as a normal user: a systemd user service (`loginctl
  enable-linger` keeps it running after logout when available).
- Windows: a Windows service through WinSW (shipped next to this program as
  mizan-service.exe), running `mizan-server run`.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from mizan_server.layout import IS_WINDOWS, Config

NAME = "mizan"


def _program(cfg: Config) -> Path:
    return cfg.install / "server" / ("mizan-server.exe" if IS_WINDOWS else "mizan-server")


def _systemctl(*args: str, user: bool) -> subprocess.CompletedProcess:
    return subprocess.run(["systemctl", *(["--user"] if user else []), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")


def _unit(cfg: Config, user: bool) -> str:
    lines = [
        "[Unit]",
        "Description=Mizan (ميزان) — local server",
        "After=network-online.target",
        "Wants=network-online.target",
        "",
        "[Service]",
        f'Environment="MIZAN_CONFIG={cfg.data / "config.json"}"',
        f"ExecStart={_program(cfg)} run",
        "Restart=on-failure",
        "RestartSec=5",
        "TimeoutStopSec=90",
    ]
    if not user:
        lines += [f"User={cfg.run_as}", "AmbientCapabilities=CAP_NET_BIND_SERVICE"]
    lines += ["", "[Install]", f"WantedBy={'default.target' if user else 'multi-user.target'}", ""]
    return "\n".join(lines)


def install(cfg: Config) -> str:
    if IS_WINDOWS:
        return _install_windows(cfg)
    if not shutil.which("systemctl"):
        return "manual"  # no systemd: the user starts `mizan-server run` themselves
    user = os.geteuid() != 0
    unit_dir = Path.home() / ".config" / "systemd" / "user" if user else Path("/etc/systemd/system")
    unit_dir.mkdir(parents=True, exist_ok=True)
    (unit_dir / f"{NAME}.service").write_text(_unit(cfg, user), encoding="utf-8")
    _systemctl("daemon-reload", user=user)
    r = _systemctl("enable", "--now", NAME, user=user)
    if r.returncode != 0:
        raise RuntimeError(f"systemctl enable failed: {r.stderr.strip()[-400:]}")
    if user and shutil.which("loginctl"):
        subprocess.run(["loginctl", "enable-linger", os.environ.get("USER", "")], capture_output=True)
    return "systemd-user" if user else "systemd"


FIREWALL_RULE = "Mizan (ميزان)"


def _netsh(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["netsh", "advfirewall", "firewall", *args], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", creationflags=0x08000000)


def _firewall_allow(cfg: Config) -> None:
    """Windows Firewall blocks incoming connections: let tills reach a LAN server.
    Only from the local subnet; any network profile, since Windows often labels a
    shop's network "Public"."""
    _netsh("delete", "rule", f"name={FIREWALL_RULE}")
    for proto, port in (("TCP", str(cfg.http_port)), ("UDP", "5353")):  # the app; mDNS for mizan.local
        r = _netsh("add", "rule", f"name={FIREWALL_RULE}", "dir=in", "action=allow", f"protocol={proto}",
                   f"localport={port}", "profile=any", "remoteip=localsubnet", f"program={_program(cfg)}")
        if r.returncode != 0:
            raise RuntimeError(f"Windows Firewall rule failed: {(r.stdout or r.stderr).strip()[-300:]}")


def _install_windows(cfg: Config) -> str:
    winsw = cfg.install / "server" / "mizan-service.exe"
    if not winsw.exists():
        return "manual"
    (cfg.install / "server" / "mizan-service.xml").write_text(f"""<service>
  <id>Mizan</id>
  <name>Mizan (ميزان)</name>
  <description>Mizan local server: database, API and app.</description>
  <executable>{_program(cfg)}</executable>
  <arguments>run</arguments>
  <env name="MIZAN_CONFIG" value="{cfg.data / 'config.json'}"/>
  <startmode>Automatic</startmode>
  <delayedAutoStart>true</delayedAutoStart>
  <stoptimeout>90 sec</stoptimeout>
  <onfailure action="restart" delay="10 sec"/>
  <log mode="roll-by-size"><sizeThreshold>10240</sizeThreshold><keepFiles>5</keepFiles></log>
  <logpath>{cfg.data / 'logs'}</logpath>
</service>
""", encoding="utf-8")
    if cfg.tls:
        _firewall_allow(cfg)
    for args in (["install"], ["start"]):
        r = subprocess.run([str(winsw), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0 and "already" not in (r.stdout + r.stderr).lower():
            raise RuntimeError(f"Windows service {args[0]} failed: {(r.stderr or r.stdout).strip()[-400:]}")
    return "windows-service"


def control(cfg: Config, action: str) -> bool:
    """start | stop | restart | status → True if it succeeded / is running."""
    if IS_WINDOWS:
        winsw = cfg.install / "server" / "mizan-service.exe"
        if not winsw.exists():
            return False
        r = subprocess.run([str(winsw), action], capture_output=True, text=True, encoding="utf-8", errors="replace")
        return r.returncode == 0 and ("Stopped" not in r.stdout if action == "status" else True)
    if not shutil.which("systemctl"):
        return False
    user = os.geteuid() != 0
    verb = "is-active" if action == "status" else action
    return _systemctl(verb, NAME, user=user).returncode == 0


def uninstall(cfg: Config) -> None:
    if IS_WINDOWS:
        winsw = cfg.install / "server" / "mizan-service.exe"
        if winsw.exists():
            subprocess.run([str(winsw), "stop"], capture_output=True)
            subprocess.run([str(winsw), "uninstall"], capture_output=True)
        _netsh("delete", "rule", f"name={FIREWALL_RULE}")
        return
    if not shutil.which("systemctl"):
        return
    user = os.geteuid() != 0
    _systemctl("disable", "--now", NAME, user=user)
    unit = (Path.home() / ".config" / "systemd" / "user" if user else Path("/etc/systemd/system")) / f"{NAME}.service"
    unit.unlink(missing_ok=True)
    _systemctl("daemon-reload", user=user)
