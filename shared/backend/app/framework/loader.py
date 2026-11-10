"""Pluggable Module Loader & Auto-Discovery Engine for Mizan ERP.
 
Scans the `modules/` directory, discovers self-contained modules via `manifest.json`,
manages module-level configuration schemas & persistence, and dynamically registers
API routers.
"""
from __future__ import annotations

import importlib
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog import GENERAL, activities, families, family_of
from app.platform.settings.models import StoreSetting

logger = logging.getLogger("mizan.modules")

APP_DIR = Path(__file__).resolve().parents[1]
# Where modules live (ADR-006): modules/<home_activity>/<module_id>/, plus the platform's own
# modules and the connectors to outside systems.
MODULES_DIR = APP_DIR / "modules"
PLATFORM_DIR = APP_DIR / "platform"
INTEGRATIONS_DIR = APP_DIR / "integrations"


@dataclass
class SettingField:
    key: str
    label: str
    type: str  # "boolean", "number", "string", "select"
    default: Any
    description: str = ""
    options: list[str] | None = None


@dataclass
class ModuleManifest:
    id: str
    name: str
    name_en: str
    category: str
    version: str
    icon: str
    description: str
    target_business_types: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    is_core: bool = False
    is_installed: bool = False
    badge: str | None = None
    nav_items: list[dict[str, Any]] = field(default_factory=list)
    settings_schema: list[SettingField] = field(default_factory=list)
    activity: str = GENERAL
    kind: str = "business"


# Manifest v2 (ADR-006): the module's home activity (its family comes from it) and its kind.
MODULE_KINDS = ("business", "platform", "integration")
MODULE_ID = re.compile(r"^[a-z][a-z0-9_]*$")


def manifest_problems(data: dict[str, Any]) -> list[str]:
    """What's wrong with a manifest against schema v2 (empty when valid)."""
    problems = []
    for key in ("id", "name", "version", "activity"):
        if not isinstance(data.get(key), str) or not data.get(key):
            problems.append(f"'{key}' is required")
    if isinstance(data.get("id"), str) and not MODULE_ID.match(data["id"]):
        problems.append(f"id '{data['id']}' must be lowercase letters, digits and underscores")
    if data.get("activity") and data["activity"] not in activities():
        problems.append(f"unknown activity '{data['activity']}'")
    if data.get("kind", "business") not in MODULE_KINDS:
        problems.append(f"kind must be one of {MODULE_KINDS}")
    if data.get("status", "active") not in ("active", "planned"):
        problems.append("status must be 'active' or 'planned'")
    if not isinstance(data.get("srs", []), list):
        problems.append("'srs' must be a list of SRS requirement ids")
    if "category" in data:
        problems.append("'category' is replaced by 'activity' (the family comes from it)")
    for key in ("permissions", "screens", "widgets", "variants"):
        if not isinstance(data.get(key, []), list):
            problems.append(f"'{key}' must be a list")
    if data.get("kind", "business") == "business" and "standard" not in data.get("variants", ["standard"]):
        problems.append("'variants' must include 'standard'")
    deps = data.get("dependencies", [])
    if not isinstance(deps, list) or not all(isinstance(d, str) for d in deps):
        problems.append("'dependencies' must be a list of module ids")
    return problems


def manifest_files() -> list[Path]:
    """Every module's manifest.json: modules/<activity>/<module>/, platform/<module>/ and
    integrations/<module>/."""
    def dirs(root: Path) -> list[Path]:
        if not root.exists():
            return []
        return sorted(d for d in root.iterdir() if d.is_dir() and not d.name.startswith(("_", ".")))

    def manifests_in(root: Path) -> list[Path]:
        return [m / "manifest.json" for m in dirs(root) if (m / "manifest.json").exists()]

    # Mount order: the platform's modules, the general modules (the core ERP), every other
    # activity's modules, then integrations.
    activities = sorted(dirs(MODULES_DIR), key=lambda a: (a.name != "general", a.name))
    files = manifests_in(PLATFORM_DIR)
    for activity in activities:
        files += manifests_in(activity)
    return files + manifests_in(INTEGRATIONS_DIR)


def module_dirs() -> dict[str, Path]:
    """Module id → its folder."""
    return {mid: Path(data["_dir"]) for mid, data in manifest_index().items()}


@lru_cache(maxsize=1)
def manifest_index() -> dict[str, dict[str, Any]]:
    """Module id → raw manifest, read from the files only (no module code is imported).
    For callers that need the catalogue without loading every module (admin API, dependency
    resolution); the registry reads the same files."""
    index: dict[str, dict[str, Any]] = {}
    for f in manifest_files():
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue  # reported by the registry (registry.errors)
        if data.get("status") == "planned":
            continue  # laid out, not built: not part of the catalogue
        data["_dir"] = str(f.parent)
        index.setdefault(data.get("id", f.parent.name), data)
    return index


class ModuleRegistry:
    def __init__(self) -> None:
        self.modules_dir = MODULES_DIR
        self._manifests: dict[str, ModuleManifest] = {}
        self._routers: dict[str, APIRouter] = {}
        self._discovered = False
        # Problems found while discovering modules. The API still starts without the broken
        # module, but tests/CI fail on any entry (see tests/test_module_registry.py).
        self.errors: list[str] = []

    def _load_module_from_dir(self, entry: Path) -> None:
        """Parse manifest.json and mount router for a module directory."""
        manifest_file = entry / "manifest.json"
        if not manifest_file.exists():
            return

        try:
            data = json.loads(manifest_file.read_text(encoding="utf-8"))
            problems = manifest_problems(data)
            if problems:
                self.errors.append(f"{manifest_file}: " + "; ".join(problems))
                return
            if data.get("status") == "planned":
                return  # described and laid out, not built: never mounted or offered
            fields_raw = data.get("settings_schema", [])
            settings_schema = [
                SettingField(
                    key=f["key"],
                    label=f.get("label", f["key"]),
                    type=f.get("type", "string"),
                    default=f.get("default"),
                    description=f.get("description", ""),
                    options=f.get("options"),
                )
                for f in fields_raw
            ]

            manifest = ModuleManifest(
                id=data["id"],
                name=data["name"],
                name_en=data.get("name_en", data["name"]),
                category=family_of(data["activity"]) or GENERAL,
                activity=data["activity"],
                kind=data.get("kind", "business"),
                version=data.get("version", "1.0.0"),
                icon=data.get("icon", "Blocks"),
                description=data.get("description", ""),
                target_business_types=data.get("target_business_types", []),
                dependencies=data.get("dependencies", []),
                is_core=data.get("is_core", False),
                badge=data.get("badge"),
                nav_items=data.get("nav_items", []),
                settings_schema=settings_schema,
            )
            if manifest.id in self._manifests:
                self.errors.append(f"{entry}: module id '{manifest.id}' is already used by another module")
                return
            self._manifests[manifest.id] = manifest
            logger.info("Discovered module: %s v%s (path: %s)", manifest.id, manifest.version, entry)

            # The module's router.py, if it has one (modules/<activity>/<module>/router.py).
            pkg_prefix = "app." + ".".join(entry.relative_to(APP_DIR).parts)
            if (entry / "router.py").exists():
                try:
                    mod = importlib.import_module(f"{pkg_prefix}.router")
                    if hasattr(mod, "router") and isinstance(mod.router, APIRouter):
                        self._routers[manifest.id] = mod.router
                        logger.info("Mounted router for module: %s (%s.router)", manifest.id, pkg_prefix)
                except Exception as err:
                    logger.error("Failed to load router for module %s: %s", manifest.id, err)
                    self.errors.append(f"{entry}: router failed to load: {err!r}")

        except Exception as err:
            logger.error("Failed to parse module manifest at %s: %s", manifest_file, err)
            self.errors.append(f"{manifest_file}: invalid manifest: {err!r}")

    def discover_modules(self) -> dict[str, ModuleManifest]:
        """Load every module that has a manifest.json (top-level or in an activity folder)."""
        if self._discovered:
            return self._manifests

        for manifest_file in manifest_files():
            self._load_module_from_dir(manifest_file.parent)

        for manifest in self._manifests.values():
            for dep in manifest.dependencies:
                if dep not in self._manifests:
                    self.errors.append(f"module '{manifest.id}' depends on unknown module '{dep}'")
        self._discovered = True
        return self._manifests

    def get_categories(self) -> list[dict[str, Any]]:
        """The families modules are grouped by (a module's family is its activity's)."""
        return list(families().values())

    def get_manifest(self, module_id: str) -> ModuleManifest | None:
        if not self._discovered:
            self.discover_modules()
        return self._manifests.get(module_id)

    def get_all_manifests(self) -> list[ModuleManifest]:
        if not self._discovered:
            self.discover_modules()
        return list(self._manifests.values())

    def get_routers(self) -> dict[str, APIRouter]:
        if not self._discovered:
            self.discover_modules()
        return self._routers

    async def get_settings(self, db: AsyncSession, module_id: str) -> dict[str, Any]:
        """Get the schema and current values for a module's settings."""
        manifest = self.get_manifest(module_id)
        if not manifest:
            raise KeyError(f"Module '{module_id}' not found")

        # Build defaults from schema
        defaults = {field.key: field.default for field in manifest.settings_schema}

        # Query database for saved settings
        key = f"mod_settings_{module_id}"
        stmt = select(StoreSetting).where(StoreSetting.key == key)
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()

        saved_values: dict[str, Any] = {}
        if row and row.value:
            try:
                saved_values = json.loads(row.value)
            except Exception:
                saved_values = {}

        # Merge defaults with saved values
        merged_values = {**defaults, **saved_values}

        return {
            "module_id": module_id,
            "module_name": manifest.name,
            "schema": [asdict(f) for f in manifest.settings_schema],
            "values": merged_values,
        }

    async def save_settings(
        self, db: AsyncSession, module_id: str, new_values: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate and persist updated settings for a module."""
        manifest = self.get_manifest(module_id)
        if not manifest:
            raise KeyError(f"Module '{module_id}' not found")

        # Filter and validate against schema keys
        valid_keys = {f.key for f in manifest.settings_schema}
        clean_values = {k: v for k, v in new_values.items() if k in valid_keys}

        key = f"mod_settings_{module_id}"
        stmt = select(StoreSetting).where(StoreSetting.key == key)
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()

        if row:
            row.value = json.dumps(clean_values, ensure_ascii=False)
        else:
            db.add(StoreSetting(key=key, value=json.dumps(clean_values, ensure_ascii=False)))

        await db.commit()
        return await self.get_settings(db, module_id)


# Global registry singleton
registry = ModuleRegistry()
