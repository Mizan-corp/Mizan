"""Packages (.mzmo module, .mzba activity, .mzth theme; .mzm is the older name for all): community modules (ADR-007 D1/D5), theme packs and activity packages (ADR-010):
build, sign and verify. The manifest's "kind" says which ("community", "theme", "activity").

A module package is a zip of manifest.json, entities/*.json, optional i18n/ and assets/, and
SIGNATURE (a theme's manifest is the theme, with fonts in assets/; an activity adds modules/,
variants/, themes/ and seed/):

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

from app.framework.manifest import (
    activity_package_problems,
    community_manifest_problems,
    entity_problems,
    theme_problems,
)

FORMAT = 1
CERT_PREFIX = "MZD1"
MAX_BYTES = 4 * 1024 * 1024  # Vercel functions accept request bodies up to 4.5 MB
MAX_FILES = 200
ALLOWED = (".json", ".png", ".svg", ".webp", ".jpg", ".md", ".txt", ".woff2", ".woff", ".ttf", ".otf")
TOP = ("manifest.json", "SIGNATURE", "README.md", "CHANGELOG.md")
FOLDERS = ("entities", "i18n", "assets")
ACTIVITY_FOLDERS = ("modules", "variants", "themes", "seed")  # activity packages only (ADR-010 D2)


# The file extension says what a package is (step 9a). One per kind; `.mzm` is the older name for
# all of them and is still read, so existing packages keep working. Only the names the owner chose
# (`.mzmo`, `.mzba`) and the matching theme name are used; website-template and module-UI kinds
# don't exist yet and get no extension until they do.
EXTENSIONS = {"community": ".mzmo", "activity": ".mzba", "theme": ".mzth"}
LEGACY_EXTENSION = ".mzm"


class PackageError(Exception):
    pass


def extension_for(kind: str) -> str:
    """The extension a package of this kind is published with."""
    try:
        return EXTENSIONS[kind]
    except KeyError:
        raise PackageError(f"Unknown package kind: {kind}") from None


def check_filename(filename: str | None, kind: str) -> None:
    """A package file named for one kind but holding another is refused (`.mzmo` holding a theme,
    for instance). `.mzm` and names without a Mizan extension are accepted as before."""
    ext = PurePosixPath((filename or "").lower()).suffix
    if ext in EXTENSIONS.values() and ext != EXTENSIONS.get(kind):
        raise PackageError(f"The file is named {ext} but holds a {kind} package ({EXTENSIONS.get(kind, '?')})")


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
    elif path.parts[0] not in FOLDERS + ACTIVITY_FOLDERS or path.suffix.lower() not in ALLOWED:
        raise PackageError(f"Files a declarative package can't contain: {name}")


@dataclass
class Package:
    manifest: dict
    entities: dict[str, dict]
    files: dict[str, bytes] = field(repr=False)
    developer: str = ""
    key_id: str = ""
    sha256: str = ""

    @property
    def kind(self) -> str:
        """"community" (a module), "theme" (ADR-010 D3) or "activity" (ADR-010 D2)."""
        return self.manifest.get("kind", "community")


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
    kind = manifest.get("kind") if isinstance(manifest, dict) else None
    if kind == "activity":
        problems = activity_package_problems(files, known_catalogue())
        if problems:
            raise PackageError("; ".join(problems[:12]))
        return Package(manifest=manifest, entities={}, files=files)
    stray = [n for n in files if n.split("/")[0] in ACTIVITY_FOLDERS]
    if stray:
        raise PackageError(f"Only an activity package holds {stray[0].split('/')[0]}/ ({stray[0]})")
    if isinstance(manifest, dict) and manifest.get("kind") == "theme":
        # A theme package: its manifest is the theme; besides it only assets (fonts, previews).
        problems = theme_problems(manifest, package=True)
        problems += [f"A theme package holds no {n}" for n in files if n.startswith(("entities/", "i18n/"))]
        srcs = [f.get("src") for f in (manifest.get("fonts") or {}).get("files") or [] if isinstance(f, dict)]
        missing = [f for f in srcs if f not in files]
        problems += [f"fonts.files: {f} isn't in the package" for f in missing]
        if problems:
            raise PackageError("; ".join(problems[:12]))
        return Package(manifest=manifest, entities={}, files=files)
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


def known_catalogue() -> dict:
    """Mizan's own parts an activity package may refer to: modules, screens, widgets, the records
    their variants may add fields to, and Mizan's themes."""
    from app.framework.loader import manifest_index

    index = manifest_index()
    business = {mid: m for mid, m in index.items() if m.get("kind", "business") == "business" and m.get("status") != "planned"}
    screens = {s["id"] for m in business.values() for s in m.get("screens") or [] if isinstance(s, dict)}
    widgets = {w["id"] for m in business.values() for w in m.get("widgets") or [] if isinstance(w, dict)}
    # Records that take extra fields: those the module's forms declare, and those Mizan's own
    # activities already extend through its variants (POS sales).
    from app.framework.variants import all_variants

    records = {mid: set((m.get("forms") or {}).keys()) for mid, m in business.items()}
    for mid, variants in all_variants().items():
        for v in variants.values():
            records.setdefault(mid, set()).update((v.get("fields") or {}).keys())
    try:
        from app.platform.themes.service import file_themes

        themes = {t for t, v in file_themes().items() if v["source"] == "mizan"}
    except Exception:  # noqa: BLE001 (themes engine unavailable: don't block verification)
        themes = None
    return {"modules": set(business), "screens": screens, "widgets": widgets, "records": records, "themes": themes}
