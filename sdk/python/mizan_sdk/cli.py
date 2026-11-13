"""The `mizan` command: create, check and package community modules (ADR-007).

  mizan module new acme.visits        a starter module in ./acme.visits
  mizan check [folder]                what Mizan would refuse, before you package
  mizan keys new                      a signing key; register its public part in the portal
  mizan package [folder]              a signed .mzm for owners to install from file

Keys live in ~/.mizan (MIZAN_HOME). The certificate the portal issues for your key is saved
next to it as <key>.cert.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path

from mizan_sdk import __version__
from mizan_sdk.package import PackageError, build, module_files, problems

HOME = Path(os.environ.get("MIZAN_HOME", Path.home() / ".mizan"))
MODULE_ID = re.compile(r"^[a-z][a-z0-9_]{1,31}\.[a-z][a-z0-9_]{1,47}$")


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def starter(module_id: str) -> dict[str, dict]:
    developer, name = module_id.split(".", 1)
    return {
        "manifest.json": {
            "id": module_id, "name": "سجلاتي", "name_en": name.replace("_", " ").title(), "version": "0.1.0",
            "kind": "community", "icon": "Blocks", "description": "وصف قصير لما تفعله الوحدة.",
            "entities": ["item"],
            "permissions": [{"id": f"{module_id}.use", "name": "استخدام الوحدة", "name_en": "Use the module"}],
            "menu": [{"entity": "item", "label": "سجلاتي", "icon": "Blocks", "permission": f"{module_id}.use"}],
            "scopes": [],
        },
        "entities/item.json": {
            "id": "item", "name": "سجل", "name_en": "Item", "title": "title",
            "fields": [
                {"key": "title", "type": "text", "label": "العنوان", "required": True},
                {"key": "on", "type": "date", "label": "التاريخ"},
                {"key": "amount", "type": "money", "label": "المبلغ"},
                {"key": "state", "type": "select", "label": "الحالة", "options": ["جديد", "منتهٍ"]},
            ],
            "list": ["title", "on", "state"],
            "form": {"sections": [{"id": "main", "label": "البيانات", "fields": ["title", "on", "amount", "state"]}]},
        },
    }


def cmd_new(a) -> int:
    if not MODULE_ID.match(a.id):
        print("✘ The id is '<developer>.<module>' in lower case, e.g. acme.visits", file=sys.stderr)
        return 2
    folder = Path(a.dir or a.id)
    if folder.exists() and any(folder.iterdir()):
        print(f"✘ {folder} isn't empty", file=sys.stderr)
        return 1
    for rel, body in starter(a.id).items():
        path = folder / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (folder / "README.md").write_text(f"# {a.id}\n\nA Mizan community module. Docs: https://dev.allmizan.live/docs\n", encoding="utf-8")
    print(f"✔ Created {folder}. Next: edit it, then `mizan check {folder}` and `mizan package {folder}`.")
    return 0


def cmd_check(a) -> int:
    folder = Path(a.dir)
    try:
        found = problems(module_files(folder))
    except PackageError as e:
        print(f"✘ {e}", file=sys.stderr)
        return 1
    if found:
        for p in found:
            print(f"✘ {p}")
        return 1
    print(f"✔ {folder}: Mizan would accept it")
    return 0


def cmd_keys_new(a) -> int:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    HOME.mkdir(parents=True, exist_ok=True)
    path = HOME / f"{a.name}.key"
    if path.exists() and not a.force:
        print(f"✘ {path} exists (add --force to replace it)", file=sys.stderr)
        return 1
    key = Ed25519PrivateKey.generate()
    raw = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    path.write_text(_b64e(raw) + "\n", encoding="utf-8")
    if os.name != "nt":
        os.chmod(path, 0o600)
    public = _b64e(key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))
    print(f"✔ Private key: {path} (keep it secret, back it up)")
    print("Register this public key in the developer portal (Keys → Add), then save the certificate it")
    print(f"gives you as {HOME / (a.name + '.cert')}:")
    print(public)
    return 0


def cmd_package(a) -> int:
    folder = Path(a.dir)
    key_path = Path(a.key) if a.key else HOME / "default.key"
    cert_path = Path(a.certificate) if a.certificate else key_path.with_suffix(".cert")
    if not key_path.exists():
        print(f"✘ No signing key at {key_path}. Run `mizan keys new` first.", file=sys.stderr)
        return 1
    if not cert_path.exists():
        print(f"✘ No certificate at {cert_path}. Register your key in the developer portal and save its certificate there.",
              file=sys.stderr)
        return 1
    raw = base64.urlsafe_b64decode(key_path.read_text().strip() + "==")
    try:
        files = module_files(folder)
        data = build(files, raw, cert_path.read_text())
    except PackageError as e:
        print(f"✘ {e}", file=sys.stderr)
        return 1
    manifest = json.loads(files["manifest.json"])
    out = Path(a.out or f"{manifest['id']}-{manifest['version']}.mzm")
    out.write_bytes(data)
    print(f"✔ {out} ({len(data) // 1024 + 1} KB). Owners install it from the module centre: وحدات المطورين → تثبيت من ملف.")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="mizan", description="Build Mizan community modules (https://dev.allmizan.live/docs).")
    p.add_argument("--version", action="version", version=f"mizan-sdk {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    module = sub.add_parser("module", help="create modules").add_subparsers(dest="action", required=True)
    new = module.add_parser("new", help="a starter module")
    new.add_argument("id", help="<developer>.<module>, e.g. acme.visits")
    new.add_argument("--dir", help="folder (default: the id)")
    new.set_defaults(func=cmd_new)

    check = sub.add_parser("check", help="check a module against Mizan's rules")
    check.add_argument("dir", nargs="?", default=".")
    check.set_defaults(func=cmd_check)

    keys = sub.add_parser("keys", help="signing keys").add_subparsers(dest="action", required=True)
    kn = keys.add_parser("new", help="create a signing key")
    kn.add_argument("--name", default="default")
    kn.add_argument("--force", action="store_true")
    kn.set_defaults(func=cmd_keys_new)

    pkg = sub.add_parser("package", help="build a signed .mzm")
    pkg.add_argument("dir", nargs="?", default=".")
    pkg.add_argument("--key", help="private key file (default ~/.mizan/default.key)")
    pkg.add_argument("--certificate", help="certificate file (default: next to the key, .cert)")
    pkg.add_argument("--out", help="output file")
    pkg.set_defaults(func=cmd_package)

    a = p.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
