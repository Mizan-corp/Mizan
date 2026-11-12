"""Community module packages (.mzm, ADR-007 D1/D5): build, sign and verify.

A package is a zip of manifest.json, entities/*.json, optional i18n/ and assets/, and SIGNATURE:

  {"format": 1, "module": "acme.visits", "version": "1.0.0",
   "files": {"manifest.json": "<sha256>", ...},
   "certificate": "MZD1.<payload>.<sig>",     # Mizan certifies the developer's key
   "signature": "<base64url Ed25519 over the canonical JSON of format/module/version/files>"}

Trust: the certificate is verified with Mizan's platform keys (app.platform.licensing.keys, prefix
MZD1: {developer, key_id, public_key, issued_at}); the signature with the certified key. Every
install can do this offline. Only the files a declarative module may contain are accepted.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from app.framework.manifest import community_manifest_problems, entity_problems

FORMAT = 1
CERT_PREFIX = "MZD1"
MAX_BYTES = 10 * 1024 * 1024
MAX_FILES = 200
ALLOWED = (".json", ".png", ".svg", ".webp", ".jpg", ".md", ".txt")
TOP = ("manifest.json", "SIGNATURE", "README.md", "CHANGELOG.md")
FOLDERS = ("entities", "i18n", "assets")


class PackageError(Exception):
    pass


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _canonical(module: str, version: str, files: dict[str, str]) -> bytes:
    return json.dumps({"format": FORMAT, "module": module, "version": version, "files": files},
                      sort_keys=True, separators=(",", ":")).encode()


def _check_path(name: str) -> None:
    path = PurePosixPath(name)
    if name.startswith("/") or "\\" in name or ".." in path.parts or not path.parts:
        raise PackageError(f"Unsafe path in package: {name}")
    if len(path.parts) == 1:
        if name not in TOP:
            raise PackageError(f"Unexpected file at the top of the package: {name}")
    elif path.parts[0] not in FOLDERS or path.suffix.lower() not in ALLOWED:
        raise PackageError(f"Files a declarative module can't contain: {name}")


@dataclass
class Package:
    manifest: dict
    entities: dict[str, dict]
    files: dict[str, bytes] = field(repr=False)
    developer: str = ""
    key_id: str = ""
    sha256: str = ""


def read_unverified(data: bytes) -> tuple[dict[str, bytes], dict]:
    """The package's files and its SIGNATURE, checking only its shape."""
    if len(data) > MAX_BYTES:
        raise PackageError(f"Packages are limited to {MAX_BYTES // (1024 * 1024)} MB")
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise PackageError("This isn't a Mizan module package (.mzm)") from None
    infos = [i for i in z.infolist() if not i.is_dir()]
    if len(infos) > MAX_FILES:
        raise PackageError(f"At most {MAX_FILES} files in a package")
    total = 0
    files: dict[str, bytes] = {}
    for info in infos:
        _check_path(info.filename)
        if (info.external_attr >> 16) & 0o170000 == 0o120000:
            raise PackageError(f"Links aren't allowed: {info.filename}")
        total += info.file_size
        if total > 4 * MAX_BYTES:
            raise PackageError("The package unpacks too large")
        files[info.filename] = z.read(info)
    if "SIGNATURE" not in files or "manifest.json" not in files:
        raise PackageError("The package has no manifest.json or no SIGNATURE")
    try:
        signature = json.loads(files.pop("SIGNATURE"))
    except ValueError:
        raise PackageError("SIGNATURE isn't valid JSON") from None
    return files, signature


def verify(data: bytes) -> Package:
    """A genuine, well-formed package (PackageError with a plain reason otherwise)."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    from app.platform.licensing import keys

    files, sig = read_unverified(data)
    try:
        cert = keys.verify(sig.get("certificate") or "", prefix=CERT_PREFIX)
    except keys.LicenceError:
        raise PackageError("The developer's certificate isn't from Mizan") from None
    hashes = {name: hashlib.sha256(body).hexdigest() for name, body in files.items()}
    if sig.get("format") != FORMAT or sig.get("files") != hashes:
        raise PackageError("The package's files don't match its signature (changed after signing?)")
    try:
        public = Ed25519PublicKey.from_public_bytes(_b64d(cert["public_key"]))
        public.verify(_b64d(sig.get("signature") or ""), _canonical(sig.get("module", ""), sig.get("version", ""), hashes))
    except (InvalidSignature, KeyError, ValueError):
        raise PackageError("The package's signature doesn't match the developer's key") from None

    package = parse(files)
    if package.manifest.get("id") != sig.get("module") or package.manifest.get("version") != sig.get("version"):
        raise PackageError("The signature is for another module or version")
    if not package.manifest["id"].startswith(cert["developer"] + "."):
        raise PackageError(f"Developer {cert['developer']} can only sign modules named {cert['developer']}.…")
    package.developer, package.key_id = cert["developer"], cert.get("key_id", "")
    package.sha256 = hashlib.sha256(data).hexdigest()
    return package


def parse(files: dict[str, bytes]) -> Package:
    """Manifest and entities from a package's files, validated (no signature check)."""
    try:
        manifest = json.loads(files["manifest.json"])
        entities = {PurePosixPath(n).stem: json.loads(b) for n, b in files.items()
                    if n.startswith("entities/") and n.endswith(".json")}
    except (KeyError, ValueError) as e:
        raise PackageError(f"Invalid JSON in the package: {e}") from None
    problems = community_manifest_problems(manifest, set(entities))
    scopes = set(manifest.get("scopes") or []) if isinstance(manifest, dict) else set()
    for name, entity in entities.items():
        problems += entity_problems(entity, set(entities), scopes)
        if isinstance(entity, dict) and entity.get("id") != name:
            problems.append(f"entities/{name}.json has id {entity.get('id')!r}")
    if problems:
        raise PackageError("; ".join(problems[:12]))
    return Package(manifest=manifest, entities=entities, files=files)


def build(files: dict[str, bytes], private_key: bytes, certificate: str) -> bytes:
    """Sign and zip a module's files (what `mizan package` does). `private_key`: raw Ed25519 bytes."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    for name in files:
        _check_path(name)
    package = parse(files)
    hashes = {name: hashlib.sha256(body).hexdigest() for name, body in files.items()}
    module, version = package.manifest["id"], package.manifest["version"]
    signature = Ed25519PrivateKey.from_private_bytes(private_key).sign(_canonical(module, version, hashes))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(files):
            z.writestr(name, files[name])
        z.writestr("SIGNATURE", json.dumps({"format": FORMAT, "module": module, "version": version, "files": hashes,
                                            "certificate": certificate, "signature": _b64e(signature)}, indent=2))
    return out.getvalue()


def certify(developer: str, key_id: str, public_key: bytes) -> str:
    """Mizan's certificate for a developer's public key (the portal issues it, ADR-007 D5)."""
    from datetime import UTC, datetime

    from app.platform.licensing import keys

    return keys.sign({"developer": developer, "key_id": key_id, "public_key": _b64e(public_key),
                      "issued_at": datetime.now(UTC).isoformat()}, prefix=CERT_PREFIX)
