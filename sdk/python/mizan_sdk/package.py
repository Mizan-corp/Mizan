"""Building a signed .mzm package from a module folder (the format Mizan verifies:
system/core/backend/app/framework/package.py, ADR-007 D1/D5)."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import zipfile
from pathlib import Path, PurePosixPath

from mizan_sdk.manifest import activity_package_problems, community_manifest_problems, entity_problems, theme_problems

FORMAT = 2  # format 2 signs the package kind too (step 9c); Mizan still reads format 1
# The file extension says the kind (same table as the server, framework/package.py). `.mzm`, the
# older name for every kind, is still accepted by Mizan.
EXTENSIONS = {"community": ".mzmo", "activity": ".mzba", "theme": ".mzth"}
MAX_BYTES = 4 * 1024 * 1024
ALLOWED = (".json", ".png", ".svg", ".webp", ".jpg", ".md", ".txt", ".woff2", ".woff", ".ttf", ".otf")
TOP = ("manifest.json", "README.md", "CHANGELOG.md")
FOLDERS = ("entities", "i18n", "assets", "modules", "variants", "themes", "seed")  # the last four: activities


class PackageError(Exception):
    pass


def package_name(manifest: dict) -> str:
    """`<id>-<version>` plus the extension of the manifest's kind (a module by default)."""
    ext = EXTENSIONS.get(manifest.get("kind", "community"), ".mzmo")
    return f"{manifest['id']}-{manifest['version']}{ext}"


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def module_files(folder: Path) -> dict[str, bytes]:
    """The files of a module, theme or activity folder that go into its package (others, such as
    __pycache__ or .git, are ignored)."""
    files: dict[str, bytes] = {}
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        rel = PurePosixPath(path.relative_to(folder).as_posix())
        if len(rel.parts) == 1 and rel.name in TOP:
            files[str(rel)] = path.read_bytes()
        elif rel.parts[0] in FOLDERS and rel.suffix.lower() in ALLOWED and not any(x.startswith(".") for x in rel.parts):
            files[str(rel)] = path.read_bytes()
    if "manifest.json" not in files:
        raise PackageError(f"No manifest.json in {folder}")
    return files


def problems(files: dict[str, bytes]) -> list[str]:
    """Everything Mizan would refuse in these files (a module or a theme); [] when it's fine."""
    try:
        manifest = json.loads(files["manifest.json"])
        entities = {PurePosixPath(n).stem: json.loads(b) for n, b in files.items()
                    if n.startswith("entities/") and n.endswith(".json")}
    except ValueError as e:
        return [f"Invalid JSON: {e}"]
    if isinstance(manifest, dict) and manifest.get("kind") == "activity":  # a whole activity (ADR-010 D2)
        return activity_package_problems(files)
    stray = [n for n in files if n.split("/")[0] in ("modules", "variants", "themes", "seed")]
    if stray:
        return [f"Only an activity holds {stray[0].split('/')[0]}/ ({stray[0]})"]
    if isinstance(manifest, dict) and manifest.get("kind") == "theme":  # a theme package (ADR-010 D3)
        found = theme_problems(manifest, package=True)
        found += [f"A theme package holds no {n}" for n in files if n.startswith(("entities/", "i18n/"))]
        srcs = [f.get("src") for f in (manifest.get("fonts") or {}).get("files") or [] if isinstance(f, dict)]
        return found + [f"fonts.files: {f} isn't in the folder" for f in srcs if f not in files]
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
    kind = manifest.get("kind", "community")
    canonical = json.dumps({"format": FORMAT, "kind": kind, "module": module, "version": version, "files": hashes},
                           sort_keys=True, separators=(",", ":")).encode()
    signature = Ed25519PrivateKey.from_private_bytes(private_key).sign(canonical)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(files):
            z.writestr(name, files[name])
        z.writestr("SIGNATURE", json.dumps({"format": FORMAT, "kind": kind, "module": module, "version": version,
                                            "files": hashes, "certificate": certificate.strip(), "signature": _b64e(signature)}, indent=2))
    data = out.getvalue()
    if len(data) > MAX_BYTES:
        raise PackageError(f"The package is {len(data) // 1024} KB; Mizan accepts up to {MAX_BYTES // 1024} KB")
    return data
