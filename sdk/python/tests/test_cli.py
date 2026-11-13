"""The mizan CLI and helpers, without a Mizan server."""
import hashlib
import hmac
import json
import time
import zipfile

import pytest

from mizan_sdk import WebhookError, verify_webhook
from mizan_sdk.cli import main


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    import mizan_sdk.cli as cli

    monkeypatch.setattr(cli, "HOME", tmp_path / ".mizan")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_new_check_keys_package(home, capsys):
    assert main(["module", "new", "acme.visits"]) == 0
    assert main(["check", "acme.visits"]) == 0
    assert main(["module", "new", "Visits"]) == 2  # not <developer>.<module>

    assert main(["keys", "new"]) == 0
    assert main(["package", "acme.visits"]) == 1  # no certificate yet
    (home / ".mizan" / "default.cert").write_text("MZD1.x.y")
    assert main(["package", "acme.visits"]) == 0
    with zipfile.ZipFile(home / "acme.visits-0.1.0.mzm") as z:
        names = set(z.namelist())
        sig = json.loads(z.read("SIGNATURE"))
    assert {"manifest.json", "entities/item.json", "README.md", "SIGNATURE"} <= names
    assert sig["module"] == "acme.visits" and sig["certificate"] == "MZD1.x.y" and set(sig["files"]) == names - {"SIGNATURE"}


def test_check_explains_problems(home, capsys):
    main(["module", "new", "acme.visits"])
    path = home / "acme.visits" / "manifest.json"
    m = json.loads(path.read_text())
    m["scopes"] = ["money:steal"]
    path.write_text(json.dumps(m))
    assert main(["check", "acme.visits"]) == 1
    assert "unknown scope: money:steal" in capsys.readouterr().out


def test_webhooks_verify():
    secret, body, ts = "s3cret", b'{"event":"sale.confirmed"}', str(int(time.time()))
    good = "sha256=" + hmac.new(secret.encode(), ts.encode() + b"." + body, hashlib.sha256).hexdigest()
    assert verify_webhook(secret, body, ts, good)["event"] == "sale.confirmed"
    with pytest.raises(WebhookError):
        verify_webhook(secret, body + b" ", ts, good)
    with pytest.raises(WebhookError, match="too old"):
        verify_webhook(secret, body, str(int(time.time()) - 3600), good)


def test_login_and_certified_keys(home, monkeypatch, capsys):
    import mizan_sdk.cli as cli

    calls = []

    def portal(method, path, token, api, body=None):
        calls.append((method, path, token, body))
        if path == "/me":
            return {"email": "dev@example.com", "full_name": "Dev", "teams": [{"handle": "acme", "role": "owner", "name": "Acme"}]}
        return {"key_id": "acme-1234", "certificate": "MZD1.cert.sig"}

    monkeypatch.setattr(cli, "_portal", portal)
    assert main(["login", "--token", "nope"]) == 2
    assert main(["login", "--token", "mzd_abc"]) == 0
    assert "Teams: acme" in capsys.readouterr().out
    assert json.loads((home / ".mizan" / "credentials.json").read_text())["token"] == "mzd_abc"
    assert main(["keys", "new", "--team", "acme"]) == 0
    assert (home / ".mizan" / "default.cert").read_text().strip() == "MZD1.cert.sig"
    method, path, token, body = calls[-1]
    assert (method, path, token) == ("POST", "/teams/acme/keys", "mzd_abc") and len(body["public_key"]) == 43
    assert main(["logout"]) == 0 and not (home / ".mizan" / "credentials.json").exists()


def test_theme_new_check_package(home, capsys):
    assert main(["theme", "new", "acme.sunrise"]) == 0
    assert main(["check", "acme.sunrise"]) == 0
    path = home / "acme.sunrise" / "manifest.json"
    t = json.loads(path.read_text())
    t["colors"]["light"]["foreground"] = "#F5F5F5"  # unreadable on a light background
    t["fonts"] = {"body": "Sunrise", "files": [{"family": "Sunrise", "src": "assets/sunrise.woff2"}]}
    path.write_text(json.dumps(t))
    assert main(["check", "acme.sunrise"]) == 1
    out = capsys.readouterr().out
    assert "contrast" in out and "assets/sunrise.woff2 isn't in the folder" in out
    t["colors"]["light"]["foreground"] = "#262321"
    path.write_text(json.dumps(t))
    (home / "acme.sunrise" / "assets" / "sunrise.woff2").write_bytes(b"wOF2")
    assert main(["check", "acme.sunrise"]) == 0
    assert main(["keys", "new"]) == 0
    (home / ".mizan" / "default.cert").write_text("MZD1.x.y")
    assert main(["package", "acme.sunrise"]) == 0
    with zipfile.ZipFile(home / "acme.sunrise-0.1.0.mzm") as z:
        assert {"manifest.json", "assets/sunrise.woff2", "SIGNATURE"} <= set(z.namelist())
    assert "Themes" in capsys.readouterr().out


def test_activity_new_check_package(home, capsys):
    assert main(["activity", "new", "acme.laundry"]) == 0
    assert main(["check", "acme.laundry"]) == 0, capsys.readouterr().out
    folder = home / "acme.laundry"
    assert {p.relative_to(folder).parts[0] for p in folder.rglob("*")} >= {"manifest.json", "modules", "variants", "themes", "seed"}
    variant = folder / "variants" / "pos" / "variant.json"
    v = json.loads(variant.read_text())
    v["hooks"] = "rules.py"  # no code in a package's variant
    variant.write_text(json.dumps(v))
    assert main(["check", "acme.laundry"]) == 1
    assert "'hooks' isn't allowed" in capsys.readouterr().out
    del v["hooks"]
    variant.write_text(json.dumps(v))
    assert main(["keys", "new"]) == 0
    (home / ".mizan" / "default.cert").write_text("MZD1.x.y")
    assert main(["package", "acme.laundry"]) == 0
    with zipfile.ZipFile(home / "acme.laundry-0.1.0.mzm") as z:
        names = set(z.namelist())
    assert "modules/acme.laundry_orders/entities/order.json" in names and "themes/fresh/theme.json" in names


def test_publish(home, monkeypatch, capsys):
    import mizan_sdk.cli as cli

    calls = []

    def portal(method, path, token, api, body=None):
        calls.append((method, path, body))
        return {"item_id": "acme.visits", "version": "0.1.0", "status": "in_review"}

    monkeypatch.setattr(cli, "_portal", portal)
    assert main(["module", "new", "acme.visits"]) == 0
    assert main(["publish", "acme.visits"]) == 1  # not signed in
    (home / ".mizan").mkdir(exist_ok=True)
    (home / ".mizan" / "credentials.json").write_text(json.dumps({"token": "mzd_x", "api": "http://test"}))
    assert main(["keys", "new"]) == 0
    (home / ".mizan" / "default.cert").write_text("MZD1.x.y")

    assert main(["publish", "acme.visits"]) == 0  # a folder: packaged, then sent
    method, path, body = calls[-1]
    assert (method, path) == ("POST", "/teams/acme/packages") and body == (home / "acme.visits-0.1.0.mzm").read_bytes()
    assert "for review" in capsys.readouterr().out

    assert main(["publish", "acme.visits-0.1.0.mzm", "--team", "other"]) == 0  # a file
    assert calls[-1][1] == "/teams/other/packages"
    (home / "junk.mzm").write_bytes(b"nope")
    assert main(["publish", "junk.mzm"]) == 1
