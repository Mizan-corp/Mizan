"""mizan-server: installs, runs and manages a single-device or LAN Mizan (ADR-005).

One program, three jobs:
- the install engine (`mizan-server install`), used by Mizan Setup's wizard and
  by the command line on servers;
- the service (`mizan-server run`): a private PostgreSQL plus the Mizan API and app;
- the management command line (`status`, `licence`, `backup`, `restore`, `uninstall`).
"""
