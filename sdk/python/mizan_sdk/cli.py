"""The `mizan` command: create, check and package community modules (ADR-007).

  mizan login                         sign in with a CLI token from the developer portal
  mizan module new acme.visits        a starter module in ./acme.visits
  mizan theme new acme.sunrise        a starter theme pack (colours, fonts, radius, motion)
  mizan activity new acme.laundry     a starter business activity: modules, variants, theme, menus
  mizan check [folder]                what Mizan would refuse, before you package
  mizan keys new --team acme          a signing key, certified by Mizan for your team
  mizan package [folder]              a signed package for owners to install from file (.mzmo module, .mzba activity, .mzth theme)
  mizan publish [folder|package file]     send it to the marketplace for review (needs `mizan login`)

Keys, certificates and credentials live in ~/.mizan (MIZAN_HOME). Signed in, `keys new` registers
the key and saves its certificate as <key>.cert; otherwise register the printed public key in the
portal and save the certificate there yourself.
"""
from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
import re
import sys
from pathlib import Path

from mizan_sdk import __version__
from mizan_sdk.package import PackageError, build, module_files, package_name, problems

HOME = Path(os.environ.get("MIZAN_HOME", Path.home() / ".mizan"))
PORTAL_API = os.environ.get("MIZAN_PORTAL_API", "https://web-api.allmizan.live/api")
PORTAL = "https://dev.allmizan.live"
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


def theme_starter(theme_id: str) -> dict:
    """Mizan's own theme as a starting point: change the colours, fonts, radius and motion."""
    from mizan_sdk.themes import MIZAN, MIZAN_COLORS

    name = theme_id.split(".", 1)[1].replace("_", " ").title()
    base = {k: v for k, v in MIZAN.items() if k != "palette"}
    return {**base, "id": theme_id, "name": name, "name_en": name, "version": "0.1.0",
            "description": "وصف قصير للمظهر.", "colors": MIZAN_COLORS, "fonts": {"body": "Manrope"}}


def cmd_theme_new(a) -> int:
    if not MODULE_ID.match(a.id):
        print("✘ The id is '<developer>.<theme>' in lower case, e.g. acme.sunrise", file=sys.stderr)
        return 2
    folder = Path(a.dir or a.id)
    if folder.exists() and any(folder.iterdir()):
        print(f"✘ {folder} isn't empty", file=sys.stderr)
        return 1
    (folder / "assets").mkdir(parents=True, exist_ok=True)
    (folder / "manifest.json").write_text(json.dumps(theme_starter(a.id), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (folder / "README.md").write_text(f"# {a.id}\n\nA Mizan theme pack. Fonts go in assets/ and are listed in fonts.files.\n"
                                      "Docs: https://dev.allmizan.live/docs/themes\n", encoding="utf-8")
    print(f"✔ Created {folder}. Edit manifest.json, then `mizan check {folder}` and `mizan package {folder}`.")
    return 0


def activity_starter(activity_id: str) -> dict[str, dict]:
    """A small, complete activity (ADR-010 D2): Mizan's modules it builds on, one module of its own,
    how it adapts the POS, its theme, menus, a position and demo records."""
    from mizan_sdk.themes import MIZAN, MIZAN_COLORS

    dev, name = activity_id.split(".", 1)
    orders = f"{dev}.{name}_orders"[:80]
    theme_id = f"{dev}.{name}_fresh"
    light = {**MIZAN_COLORS["light"], "primary": "oklch(0.48 0.09 200)", "ring": "oklch(0.48 0.09 200)",
             "sidebar": "oklch(0.24 0.05 200)", "sidebar-primary": "oklch(0.7 0.1 195)", "sidebar-accent": "oklch(0.3 0.05 200)",
             "accent": "oklch(0.94 0.03 195)", "accent-foreground": "oklch(0.3 0.06 200)"}
    menu = [{"id": "orders", "label": "الطلبات", "items": [{"screen": f"{orders}/order", "label": "طلبات العملاء"},
                                                           {"screen": "pos.pos", "label": "الكاشير"},
                                                           {"screen": "pos.sales", "label": "الفواتير"}]}]
    return {
        "manifest.json": {
            "id": activity_id, "name": "نشاطي", "name_en": name.replace("_", " ").title(), "version": "0.1.0",
            "kind": "activity", "family": "services", "icon": "Store", "description": "وصف قصير للنشاط ولمن هو.",
            "modules": ["pos", "inventory", "sales", "finance", "hr", orders], "optional": [],
            "terms": {"item": "قطعة"}, "home": "/pos", "theme": theme_id, "settings": {},
            "positions": [{"code": "counter_clerk", "name": "موظف الاستقبال", "name_en": "Counter clerk",
                           "suggested_roles": ["cashier"]}],
            "menu": menu, "dashboard": ["pos.recent_sales"],
            "roles": {"cashier": {"home": "pos.pos", "menu": menu, "dashboard": ["pos.recent_sales"]}},
        },
        f"modules/{orders}/manifest.json": {
            "id": orders, "name": "الطلبات", "name_en": "Orders", "version": "0.1.0", "kind": "community", "icon": "ClipboardList",
            "entities": ["order"], "scopes": ["customers:read"],
            "menu": [{"entity": "order", "label": "طلبات العملاء", "icon": "ClipboardList"}],
        },
        f"modules/{orders}/entities/order.json": {
            "id": "order", "name": "طلب", "name_en": "Order", "title": "customer",
            "fields": [
                {"key": "customer", "type": "reference", "to": "customers", "label": "العميل", "required": True},
                {"key": "received", "type": "date", "label": "تاريخ الاستلام"},
                {"key": "ready_on", "type": "date", "label": "موعد التسليم"},
                {"key": "pieces", "type": "number", "label": "عدد القطع"},
                {"key": "price", "type": "money", "label": "السعر"},
                {"key": "state", "type": "select", "label": "الحالة", "options": ["جديد", "جاهز", "سُلّم"]},
            ],
            "list": ["customer", "received", "ready_on", "state"],
        },
        "variants/pos/variant.json": {
            "module": "pos", "description": "يضيف موعد الاستلام إلى فاتورة البيع.",
            "fields": {"sale": [{"key": "pickup_date", "label": "موعد الاستلام", "label_en": "Pickup date", "type": "date"}]},
            "terms": {"item": "قطعة"},
        },
        "themes/fresh/theme.json": {**{k: v for k, v in MIZAN.items() if k != "palette"},
                                    "id": theme_id, "name": "منعش", "name_en": "Fresh", "version": "0.1.0",
                                    "description": "أزرق مخضر هادئ.", "colors": {"light": light, "dark": MIZAN_COLORS["dark"]},
                                    "fonts": {"body": "Manrope"}},
        "seed/orders.json": {"module": orders, "entity": "order",
                             "records": [{"received": "2026-11-01", "ready_on": "2026-11-03", "pieces": 5, "price": "120.00",
                                          "state": "جديد"}]},
    }


def cmd_activity_new(a) -> int:
    if not MODULE_ID.match(a.id):
        print("✘ The id is '<developer>.<activity>' in lower case, e.g. acme.laundry", file=sys.stderr)
        return 2
    folder = Path(a.dir or a.id)
    if folder.exists() and any(folder.iterdir()):
        print(f"✘ {folder} isn't empty", file=sys.stderr)
        return 1
    for rel, body in activity_starter(a.id).items():
        path = folder / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (folder / "README.md").write_text(f"# {a.id}\n\nA Mizan business activity. Docs: https://dev.allmizan.live/docs/activities\n",
                                      encoding="utf-8")
    print(f"✔ Created {folder}: manifest.json, modules/, variants/, themes/, seed/. Next: `mizan check {folder}`.")
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


def _credentials() -> dict | None:
    path = HOME / "credentials.json"
    return json.loads(path.read_text()) if path.exists() else None


def _portal(method: str, path: str, token: str, api: str, body: dict | bytes | None = None) -> dict:
    from mizan_sdk.client import MizanClient

    return MizanClient(token, base_url=f"{api.rstrip('/')}/developers").request(method, path, body)


def cmd_login(a) -> int:
    from mizan_sdk.client import MizanError

    token = a.token or os.environ.get("MIZAN_TOKEN") or getpass.getpass(
        f"CLI token (portal → CLI tokens, {PORTAL}/portal/tokens): ").strip()
    if not token.startswith("mzd_"):
        print("✘ A CLI token starts with mzd_", file=sys.stderr)
        return 2
    api = a.api or PORTAL_API
    try:
        me = _portal("GET", "/me", token, api)
    except (MizanError, OSError) as e:
        print(f"✘ The portal refused the token: {e}", file=sys.stderr)
        return 1
    HOME.mkdir(parents=True, exist_ok=True)
    path = HOME / "credentials.json"
    path.write_text(json.dumps({"token": token, "api": api}) + "\n", encoding="utf-8")
    if os.name != "nt":
        os.chmod(path, 0o600)
    teams = ", ".join(t["handle"] for t in me.get("teams", [])) or "none yet (create one in the portal)"
    print(f"✔ Signed in as {me['email']}. Teams: {teams}")
    return 0


def cmd_logout(a) -> int:
    path = HOME / "credentials.json"
    if path.exists():
        path.unlink()
    print("✔ Signed out (revoke the token in the portal if it may have leaked)")
    return 0


def cmd_whoami(a) -> int:
    from mizan_sdk.client import MizanError

    creds = _credentials()
    if not creds:
        print("Not signed in. Run `mizan login`.")
        return 1
    try:
        me = _portal("GET", "/me", creds["token"], creds["api"])
    except (MizanError, OSError) as e:
        print(f"✘ {e}", file=sys.stderr)
        return 1
    print(f"{me['full_name']} <{me['email']}>")
    for t in me.get("teams", []):
        print(f"  {t['handle']}  ({t['role']})  {t['name']}")
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
    creds = _credentials()
    if creds and a.team:
        from mizan_sdk.client import MizanError

        try:
            cert = _portal("POST", f"/teams/{a.team}/keys", creds["token"], creds["api"],
                           {"public_key": public, "name": a.name})
        except (MizanError, OSError) as e:
            print(f"✘ Couldn't register it with team {a.team}: {e}", file=sys.stderr)
            return 1
        (HOME / f"{a.name}.cert").write_text(cert["certificate"] + "\n", encoding="utf-8")
        print(f"✔ Certified for team {a.team} as {cert['key_id']}; certificate saved to {HOME / (a.name + '.cert')}")
        return 0
    print(f"Register this public key in the developer portal ({PORTAL}/portal → your team → Keys), then save the")
    print(f"certificate it gives you as {HOME / (a.name + '.cert')}  (or `mizan login` and use --team):")
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
    out = Path(a.out or package_name(manifest))
    out.write_bytes(data)
    if manifest.get("kind") == "activity":
        print(f"✔ {out} ({len(data) // 1024 + 1} KB), a signed activity package. `mizan publish` sends it for review; then workspaces can change to it.")
        return 0
    where = ("Themes (المظاهر) → Install a theme from file" if manifest.get("kind") == "theme"
             else "Developer modules (وحدات المطورين) → Install from file")
    print(f"✔ {out} ({len(data) // 1024 + 1} KB). Owners install it from the app's module centre: {where}.")
    return 0


def cmd_publish(a) -> int:
    """Send a signed package to the marketplace: the Mizan team reviews it, then workspaces can
    install it from their store. A folder is packaged first (with the same key options)."""
    import io
    import zipfile

    from mizan_sdk.client import MizanError

    creds = _credentials()
    if not creds:
        print("✘ Not signed in. Run `mizan login` first.", file=sys.stderr)
        return 1
    target = Path(a.target)
    if target.is_dir():
        a.dir, a.out = str(target), None
        if cmd_package(a):
            return 1
        manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
        target = Path(package_name(manifest))
    if not target.is_file():
        print(f"✘ {target} isn't a folder or a Mizan package file (.mzmo, .mzba, .mzth or .mzm)", file=sys.stderr)
        return 1
    data = target.read_bytes()
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            manifest = json.loads(z.read("manifest.json"))
    except (zipfile.BadZipFile, KeyError, ValueError):
        print(f"✘ {target} isn't a Mizan package", file=sys.stderr)
        return 1
    team = a.team or str(manifest.get("id", "")).split(".", 1)[0]
    try:
        out = _portal("POST", f"/teams/{team}/packages", creds["token"], creds["api"], data)
    except (MizanError, OSError) as e:
        print(f"✘ The marketplace refused it: {e}", file=sys.stderr)
        return 1
    print(f"✔ Sent {out['item_id']} {out['version']} for review. Follow it in the portal: {PORTAL}/portal/teams/{team}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="mizan", description="Build Mizan community modules (https://dev.allmizan.live/docs).")
    p.add_argument("--version", action="version", version=f"mizan-sdk {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    login = sub.add_parser("login", help="sign in with a CLI token from the developer portal")
    login.add_argument("--token", help="the mzd_ token (default: asked, or MIZAN_TOKEN)")
    login.add_argument("--api", help=argparse.SUPPRESS)
    login.set_defaults(func=cmd_login)
    sub.add_parser("logout", help="forget the saved token").set_defaults(func=cmd_logout)
    sub.add_parser("whoami", help="who you're signed in as, and your teams").set_defaults(func=cmd_whoami)

    module = sub.add_parser("module", help="create modules").add_subparsers(dest="action", required=True)
    new = module.add_parser("new", help="a starter module")
    new.add_argument("id", help="<developer>.<module>, e.g. acme.visits")
    new.add_argument("--dir", help="folder (default: the id)")
    new.set_defaults(func=cmd_new)

    theme = sub.add_parser("theme", help="create theme packs").add_subparsers(dest="action", required=True)
    tn = theme.add_parser("new", help="a starter theme")
    tn.add_argument("id", help="<developer>.<theme>, e.g. acme.sunrise")
    tn.add_argument("--dir", help="folder (default: the id)")
    tn.set_defaults(func=cmd_theme_new)

    activity = sub.add_parser("activity", help="create business activities").add_subparsers(dest="action", required=True)
    an = activity.add_parser("new", help="a starter activity")
    an.add_argument("id", help="<developer>.<activity>, e.g. acme.laundry")
    an.add_argument("--dir", help="folder (default: the id)")
    an.set_defaults(func=cmd_activity_new)

    check = sub.add_parser("check", help="check a module, theme or activity against Mizan's rules")
    check.add_argument("dir", nargs="?", default=".")
    check.set_defaults(func=cmd_check)

    keys = sub.add_parser("keys", help="signing keys").add_subparsers(dest="action", required=True)
    kn = keys.add_parser("new", help="create a signing key")
    kn.add_argument("--name", default="default")
    kn.add_argument("--force", action="store_true")
    kn.add_argument("--team", help="register it with this team and save its certificate (needs `mizan login`)")
    kn.set_defaults(func=cmd_keys_new)

    pkg = sub.add_parser("package", help="build a signed package (.mzmo, .mzba or .mzth by kind)")
    pkg.add_argument("dir", nargs="?", default=".")
    pkg.add_argument("--key", help="private key file (default ~/.mizan/default.key)")
    pkg.add_argument("--certificate", help="certificate file (default: next to the key, .cert)")
    pkg.add_argument("--out", help="output file")
    pkg.set_defaults(func=cmd_package)

    pub = sub.add_parser("publish", help="send a module or theme to the marketplace for review")
    pub.add_argument("target", nargs="?", default=".", help="a package file, or a folder to package first (default: .)")
    pub.add_argument("--team", help="the team (default: the package id's prefix)")
    pub.add_argument("--key", help="private key file, when packaging a folder (default ~/.mizan/default.key)")
    pub.add_argument("--certificate", help="certificate file (default: next to the key, .cert)")
    pub.set_defaults(func=cmd_publish)

    a = p.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
