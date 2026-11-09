"""On-premise server mode: single-device and LAN installs (ADR-005).

Switched on by MIZAN_MODE=desktop|lan on the system API. `state` keeps the
install's identity and licence key on disk, `licence` decides whether the
install may write, `checkin` talks to Mizan Cloud when online, `setup` creates
the database and the workspace on first install, `server` wires it together.
"""
