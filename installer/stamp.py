#!/usr/bin/env python3
"""Stamp a client's licence into a built Mizan Setup, making a per-client installer.

    python installer/stamp.py dist/MizanSetup-1.0.0-windows.exe "MZN1.…" "MizanSetup - Al Amal.exe"
    python installer/stamp.py dist/MizanSetup-1.0.0-windows.exe licence.mzn out.exe

Setup then finds the licence by itself (no file, no typing). Re-stamping replaces
the previous licence. Layout: see installer/setup/src-tauri/src/embedded.rs.
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

MAGIC = b"MZNSETUP"


def stamp(setup: Path, licence: str, out: Path) -> Path:
    key = re.search(r"MZN1\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+", licence)
    if not key:
        raise SystemExit("That isn't a Mizan licence key (MZN1.…).")
    data = setup.read_bytes()
    footer = data[-32:]
    if footer[:8] != MAGIC:
        raise SystemExit(f"{setup} isn't a built Mizan Setup (no payload footer).")
    offset = int.from_bytes(footer[8:16], "little")
    length = int.from_bytes(footer[16:24], "little")
    body = data[: offset + length]  # program + payload, without any earlier stamp
    stamp_bytes = key.group(0).encode()
    if out.resolve() == setup.resolve():
        raise SystemExit("Write the stamped installer to a new file.")
    with open(out, "wb") as f:
        f.write(body)
        f.write(stamp_bytes)
        f.write(MAGIC + offset.to_bytes(8, "little") + length.to_bytes(8, "little") + len(stamp_bytes).to_bytes(8, "little"))
    shutil.copymode(setup, out)
    return out


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(2)
    source = sys.argv[2]
    text = source if source.startswith("MZN1.") else Path(source).read_text()
    print(stamp(Path(sys.argv[1]), text, Path(sys.argv[3])))
