# installer/ — single-device and LAN Mizan

Everything that installs and runs Mizan on a client's own computer
([ADR-005](../docs/decisions/ADR-005-deployment-modes.md)). One licence key decides
the workspace and the mode; the same installer handles both modes on Windows and Linux.

**Current release: v1.0.2** in [ammar0xff/mizan-releases](https://github.com/ammar0xff/mizan-releases/releases/latest)
(`MizanSetup-1.0.2-windows.exe`, `MizanSetup-1.0.2-linux`, `mizan-setup-1.0.2-linux-x86_64.run`, and the update payloads `payload-1.0.2-*.zip`).
User-facing guide: the website's docs, [running on site](https://mizan-co.vercel.app/docs/deploy/modes).

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
| Certificate | — | the install's own authority; tills install `mizan-ca.crt` once from the sign-in page («ثبّت شهادة الأمان», served at `/api/onprem/ca.crt`) |

Both: a private PostgreSQL 16 on `127.0.0.1` with its own cluster, a background service
(Windows service via WinSW, or systemd), a backup every day (newest 14 kept), and a
licence check-in when online.

```
<program>  C:\Program Files\Mizan · /opt/mizan (root) · ~/.local/opt/mizan
  server/mizan-server[.exe]   pgsql/   web/   VERSION   Mizan.exe | mizan-app (single device)
<data>     C:\ProgramData\Mizan · /var/lib/mizan (root) · ~/.local/share/mizan
  config.json (secrets, restricted)   app.json (port, TLS: for the app window)
  pg/   mizan/ (licence, state)   backups/   tls/   uploads/   logs/
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
mizan-server backup-to E:\MizanBackups | /mnt/share/mizan | --off   # also copy every backup there
mizan-server update [--check] [--yes] [--force]                    # newest release (below)
mizan-server uninstall --yes [--delete-data]
```

## Updating

Every check-in (6-hourly, when online) tells Mizan Cloud the installed version; when a newer
release is published for the platform, the reply carries it **signed with the licence key**
(prefix `MZR1`, so it can't pass as a licence). The owner and admin panels show "1.2.0 available"
next to that computer. On the server, as an administrator:

```bash
mizan-server update            # uses the last check-in's offer;  --check asks Mizan Cloud now
```

It verifies the offer and refuses while a till shift is open (`--force` to override), downloads
the release payload and checks its SHA-256, backs up the database, then unpacks the release
under `<data>/updates/<version>` and lets *that* version's `mizan-server apply-update` do the
switch: stop the service, move the program folder to `<program>.previous`, copy the new one in
(keeping the desktop app), run the migrations, start and wait for it to answer. Any failure
restores the previous folder (and the database backup if migrations had started) and starts
the old version again. Log: `<data>/logs/update.log`; outcome in `mizan-server status`
(`last_update`). Tested end to end by `ci_smoke.py` on Windows and Linux.

The single-device app window (`Mizan.exe` / `mizan-app`) isn't in the payload and is kept; it's
only the window, the server inside is what updates.

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
`.github/workflows/installers.yml` (run on `v*` tags, pull requests touching the
installer, or by hand).

### Publishing

Clients download from the public
[ammar0xff/mizan-releases](https://github.com/ammar0xff/mizan-releases) (this repository
is private). A `v*` tag publishes there when the `RELEASES_TOKEN` secret is set (a
fine-grained token with Contents read/write on mizan-releases). By hand:

```bash
gh run download <run id> --dir dist && cd dist && mv */* . && sha256sum MizanSetup-* mizan-setup-* > SHA256SUMS.txt
gh release create v1.0.0 MizanSetup-* mizan-setup-* SHA256SUMS.txt --repo ammar0xff/mizan-releases --title "Mizan v1.0.0"
```

Then point the owner panel at them: `MIZAN_INSTALLERS` on the owner API (production) and the admin
API (it shows which installs are behind). For updates (#89) each platform also needs
`"payload_url"` (the release's `payload-<version>-<platform>.zip`) and `"payload_sha256"` (from
`SHA256SUMS.txt`); without them nothing is offered. E.g.
`{"windows": {"url": "https://github.com/ammar0xff/mizan-releases/releases/download/v1.0.0/MizanSetup-1.0.0-windows.exe", "version": "1.0.0", "size_mb": 150}, "linux": {…}}`
(see `shared/backend/app/platform/updates/releases.py`), and redeploy it.

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
from `MIZAN_SETUP_EXTRA_ARGS`. Check the Windows side of the Rust code from Linux with
`rustup target add x86_64-pc-windows-msvc` and `cargo check --target x86_64-pc-windows-msvc`
(needs `llvm-rc`, from the `llvm` package).

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `initdb.exe failed (exit code 0xc0000135)` on Windows | PostgreSQL restarted without administrator rights and can't read its own files. Setup grants Users read/execute on `pgsql/`; for a custom install folder check its permissions (`icacls <dir>\pgsql`). |
| `Permission denied` creating the data folder on Windows | Same cause, for the data folder: setup grants the installing account and SYSTEM full control; re-run the install to repair. |
| Tills show a certificate warning / the offline sale queue doesn't work | Install the certificate on that device (sign-in page → «ثبّت شهادة الأمان»). |
| `mizan.local` doesn't open | The device or network doesn't resolve mDNS (some Android versions, guest Wi-Fi): use the address shown at the end of setup (`mizan-server status`). |
| Tills can't reach a Windows server | The firewall rule admits the local subnet only; check the till is on the same network and the port in `mizan-server status`. |
| The app says it's read-only | The licence expired or was revoked: `mizan-server licence check-in`, or `licence set <key>` with the key from the owner panel. |
| Logs | `<data>/logs/` (service, `postgres-start.log`, `pg_ctl.out`) and `<data>/pg/log/` (PostgreSQL). |
