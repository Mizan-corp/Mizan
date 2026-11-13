"""Building a signed .mzm package from a module folder (the format Mizan verifies:
shared/backend/app/framework/package.py, ADR-007 D1/D5)."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import zipfile
from pathlib import Path, PurePosixPath

from mizan_sdk.manifest import community_manifest_problems, entity_problems

FORMAT = 1
MAX_BYTES = 4 * 1024 * 1024
ALLOWED = (".json", ".png", ".svg", ".webp", ".jpg", ".md", ".txt")
TOP = ("manifest.json", "README.md", "CHANGELOG.md")
FOLDERS = ("entities", "i18n", "assets")


class PackageError(Exception):
    pass


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def module_files(folder: Path) -> dict[str, bytes]:
    """The files of a module folder that go into its package (others are ignored)."""
    files: dict[str, bytes] = {}
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        rel = PurePosixPath(path.relative_to(folder).as_posix())
        if len(rel.parts) == 1 and rel.name in TOP:
            files[str(rel)] = path.read_bytes()
        elif rel.parts[0] in FOLDERS and rel.suffix.lower() in ALLOWED:
            files[str(rel)] = path.read_bytes()
    if "manifest.json" not in files:
        raise PackageError(f"No manifest.json in {folder}")
    return files


def problems(files: dict[str, bytes]) -> list[str]:
    """Everything Mizan would refuse in these files; [] when the module is fine."""
    try:
        manifest = json.loads(files["manifest.json"])
        entities = {PurePosixPath(n).stem: json.loads(b) for n, b in files.items()
                    if n.startswith("entities/") and n.endswith(".json")}
    except ValueError as e:
        return [f"Invalid JSON: {e}"]
    found = community_manifest_problems(manifest, set(entities))
    scopes = set(manifest.get("scopes") or []) if isinstance(manifest, dict) else set()
    for name, entity in entities.items():
        found += entity_problems(entity, set(entities), scopes)
        if isinstance(entity, dict) and entity.get("id") != name:
            found.append(f"entities/{name}.json has id {entity.get('id')!r}")
    return found


def build(files: dict[str, bytes], private_key: bytes, certificate: str) -> bytes:
    """The signed .mzm bytes. `private_key`: raw Ed25519 (32 bytes); `certificate`: from the portal."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    found = problems(files)
    if found:
        raise PackageError("; ".join(found))
    manifest = json.loads(files["manifest.json"])
    module, version = manifest["id"], manifest["version"]
    hashes = {name: hashlib.sha256(body).hexdigest() for name, body in files.items()}
    canonical = json.dumps({"format": FORMAT, "module": module, "version": version, "files": hashes},
                           sort_keys=True, separators=(",", ":")).encode()
    signature = Ed25519PrivateKey.from_private_bytes(private_key).sign(canonical)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(files):
            z.writestr(name, files[name])
        z.writestr("SIGNATURE", json.dumps({"format": FORMAT, "module": module, "version": version, "files": hashes,
                                            "certificate": certificate.strip(), "signature": _b64e(signature)}, indent=2))
    data = out.getvalue()
    if len(data) > MAX_BYTES:
        raise PackageError(f"The package is {len(data) // 1024} KB; Mizan accepts up to {MAX_BYTES // 1024} KB")
    return data
