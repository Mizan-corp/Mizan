# installer/ — single-device and LAN Mizan

Everything that installs and runs Mizan on a client's own computer
([ADR-005](../docs/decisions/ADR-005-deployment-modes.md)). One licence key decides
the workspace and the mode; the same installer handles both modes on Windows and Linux.

| Part | What it is |
|---|---|
| `server/mizan_server/` | **mizan-server**: the install engine, the service (PostgreSQL + API + app) and the management command line. Packaged with PyInstaller (`server/mizan-server.spec`). |
| `setup/` | **Mizan Setup** (Tauri 2: Rust + React): the guided installer, the single-device desktop app (`--app`) and headless installs, in one file. |
| `build.py` | Builds the payload (app, PostgreSQL, mizan-server) and the installers. |
| `stamp.py` | Puts a client's licence into a built installer (a per-client installer). |
| `ci_smoke.py` | Installs, runs and signs in to both modes from the built files (CI). |
| `assets/` | App icon sources. |

## What gets installed

| | Single device | LAN |
|---|---|---|
| Listens on | `http://127.0.0.1:47800` | `https://<every interface>:443` (8443 without admin rights) |
| Opened from | the "Mizan" desktop shortcut (a Mizan app window) | any browser on the network: `https://mizan.local`, the computer's name or address |
| Certificate | — | the install's own authority; tills install `mizan-ca.crt` once (`/api/onprem/ca.crt`) |

Both: a private PostgreSQL 16 on `127.0.0.1` with its own cluster, a background service
(Windows service via WinSW, or systemd), a backup every day (newest 14 kept), and a
licence check-in when online.

```
<program>  C:\Program Files\Mizan · /opt/mizan (root) · ~/.local/opt/mizan
  server/mizan-server[.exe]   pgsql/   web/   VERSION   Mizan.exe | mizan-app (single device)
<data>     C:\ProgramData\Mizan · /var/lib/mizan (root) · ~/.local/share/mizan
  config.json   pg/   mizan/ (licence, state)   backups/   tls/   uploads/   logs/
```

## Installing

**Graphical**: run `MizanSetup`. It finds the licence by itself when it's stamped into the
installer, saved as a `.mzn` file next to it or in Downloads (the owner panel's
Download → "ملف الترخيص"), or copied. Otherwise paste the key.

**Command line** (servers, scripts):

```bash
MizanSetup install --licence "MZN1.…" --admin-password '…' [--admin-username nour] [--demo]
#   or: --licence-file "Mizan - Al Amal.mzn"; the password can come from MIZAN_ADMIN_PASSWORD
# Linux without the graphical setup:
sh mizan-setup-1.0.0-linux-x86_64.run install --licence "MZN1.…" --admin-password '…'
```

Running the install again repairs or updates in place (same database, workspace and settings).

## Managing

```bash
mizan-server status [--json]
mizan-server start | stop | restart
mizan-server licence show | set "MZN1.…" | check-in
mizan-server backup [--to /media/usb] | backups | restore <file>   # restore backs up first
mizan-server uninstall --yes [--delete-data]
```

## Building

Needs Node 22, Python 3.12 with `./shared/backend` and `installer/server/requirements.txt` installed,
Rust (stable), and on Linux the Tauri packages (`libwebkit2gtk-4.1-dev libgtk-3-dev
librsvg2-dev libayatana-appindicator3-dev`).

```bash
python installer/build.py                    # everything for this OS → installer/build/dist/
python installer/build.py --only web,pgsql   # parts (then run mizan-server from source)
python installer/ci_smoke.py                 # install + run + sign in, both modes
python installer/stamp.py installer/build/dist/MizanSetup-1.0.0-windows.exe "Mizan - Al Amal.mzn" "MizanSetup - Al Amal.exe"
```

PyInstaller doesn't cross-compile: Windows builds come from
`.github/workflows/installers.yml` (every `v*` tag publishes a release; it can also be
run by hand). Publish the files somewhere clients can download them and set
`MIZAN_INSTALLERS` on the owner API (see `shared/backend/app/core/releases.py`).

The setup binary's layout: `[program][payload.zip][licence stamp][footer]`, footer =
`MZNSETUP` + payload offset + payload length + stamp length (u64 LE each). See
`setup/src-tauri/src/embedded.rs`.

### Developing

```bash
cd installer/setup && npm run dev   # the wizard in a browser, with a simulated install
                                    # ?mode=lan · ?nolicence=1
# From source against a local stack (dev-signed licences):
PYTHONPATH=installer/server MIZAN_HOME=/tmp/mizan-test python -m mizan_server install \
  --licence "$(cat key)" --admin-password 'Test1234!' --no-service \
  --app-env development --cloud-url http://localhost:8003 --licence-public-key <dev public key>
```

The Tauri debug build takes the payload from `MIZAN_PAYLOAD_DIR` and extra engine flags
from `MIZAN_SETUP_EXTRA_ARGS`.
