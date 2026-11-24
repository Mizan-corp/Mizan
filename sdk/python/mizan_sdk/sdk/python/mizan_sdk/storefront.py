"""Experimental declarative storefront contracts. Offline validation only.

No module import, provider lookup, data access, permission grant, install or execution.
Copy-identical with app.framework.storefront. Not accepted by the page-tree runtime.
"""
from __future__ import annotations

import json
import re

SCHEMA = "mizan.storefront.experimental.v0"
ID = re.compile(r"^[a-z][a-z0-9_]{0,47}(?:\.[a-z][a-z0-9_]{0,47})?$")
KEY = re.compile(r"^[a-z][a-z0-9_]{0,47}$")
# Type alone is never compatibility. Semantics are finite and cannot carry private cost.
PRESENTATIONS = {
    ("text", "plain_text"): ("text", "heading"),
    ("image", "media"): ("image",),
    ("money", "sale_price"): ("price",),
    ("url", "destination"): ("link",),
    ("number", "quantity"): ("quantity",),
    ("boolean", "flag"): ("indicator",),
    ("date", "calendar_date"): ("date",),
}


def _key(value) -> bool:
    return isinstance(value, str) and KEY.fullmatch(value) is not None


def _label(value) -> bool:
    return isinstance(value, str) and 0 < len(value.strip()) <= 120


def _shape(value, required: set[str], optional: set[str], where: str, errors: list[str]) -> bool:
    if not isinstance(value, dict):
        errors.append(f"{where}: must be an object")
        return False
    if required - value.keys():
        errors.append(f"{where}: missing required fields")
    if value.keys() - required - optional:
        errors.append(f"{where}: unknown fields")
    return True


def storefront_contract_problems(contract, module_id: str | None = None) -> list[str]:
    """Validate untrusted metadata, not its truth, access policy or provider implementation.

    Each source is public-projection metadata explicitly supplied by its owning module.
    Only a future trusted runtime may decide if the module is installed/enabled and if
    that provider actually enforces tenant, publication and field-access restrictions.
    """
    errors: list[str] = []
    try:
        encoded = json.dumps(contract, allow_nan=False).encode("utf-8")
        if len(encoded) > 65536:
            return ["contract: maximum 64 KiB"]
    except (TypeError, ValueError, RecursionError):
        return ["contract: must be finite JSON data"]
    if not _shape(contract, {"schema", "module", "sources", "pages"}, set(), "contract", errors):
        return errors
    if contract.get("schema") != SCHEMA:
        errors.append("contract: unsupported experimental schema")
    owner = contract.get("module")
    if not isinstance(owner, str) or not ID.fullmatch(owner):
        errors.append("contract: invalid module identity")
    if module_id is not None and owner != module_id:
        errors.append("contract: module identity differs from owning module")
    sources = contract.get("sources")
    if not isinstance(sources, list) or len(sources) > 32:
        errors.append("sources: must be a list of at most 32 entries")
        sources = []
    source_ids: set[str] = set()
    source_map: dict[str, dict] = {}
    for source in sources:
        if not _shape(source, {"id", "label", "exposure", "cardinality", "fields"}, set(), "source", errors):
            continue
        sid = source.get("id")
        if not _key(sid) or sid in source_ids:
            errors.append("source: invalid or duplicate identity")
        else:
            source_ids.add(sid)
            source_map[sid] = source
        if not _label(source.get("label")):
            errors.append("source: label is required")
        if source.get("exposure") != "public_projection":
            errors.append("source: only explicit public projections are modeled")
        if source.get("cardinality") not in ("one", "many"):
            errors.append("source: cardinality must be one or many")
        fields = source.get("fields")
        if not isinstance(fields, list) or not 1 <= len(fields) <= 60:
            errors.append("source: 1 to 60 fields required")
            fields = []
        field_ids: set[str] = set()
        for field in fields:
            if not _shape(field, {"id", "label", "type", "semantic", "nullable", "exposure", "elements"}, set(), "field", errors):
                continue
            fid = field.get("id")
            if not _key(fid) or fid in field_ids:
                errors.append("field: invalid or duplicate identity")
            else:
                field_ids.add(fid)
            if not _label(field.get("label")):
                errors.append("field: label is required")
            if type(field.get("nullable")) is not bool:
                errors.append("field: nullable must be boolean")
            if field.get("exposure") != "public":
                errors.append("field: only explicit public fields are modeled")
            kind, semantic = field.get("type"), field.get("semantic")
            presentations = PRESENTATIONS.get((kind, semantic), ()) if isinstance(kind, str) and isinstance(semantic, str) else ()
            if not presentations:
                errors.append("field: unsupported type/semantic pair")
            elements = field.get("elements")
            if (not isinstance(elements, list) or not 1 <= len(elements) <= 4
                    or any(not isinstance(e, str) or e not in presentations for e in elements)
                    or len(set(e for e in elements if isinstance(e, str))) != len(elements)):
                errors.append("field: incompatible or duplicate element recommendations")
    pages = contract.get("pages")
    if not isinstance(pages, list) or len(pages) > 32:
        errors.append("pages: must be a list of at most 32 requirements")
        pages = []
    page_ids: set[str] = set()
    for page in pages:
        if not _shape(page, {"id", "label", "requirement", "source"}, set(), "page", errors):
            continue
        pid = page.get("id")
        if not _key(pid) or pid in page_ids:
            errors.append("page: invalid or duplicate identity")
        else:
            page_ids.add(pid)
        if not _label(page.get("label")) or page.get("requirement") not in ("required", "optional"):
            errors.append("page: label and required/optional requirement needed")
        if not isinstance(page.get("source"), str) or page["source"] not in source_map:
            errors.append("page: source must name a declared source")
    return errors


def storefront_binding_problems(binding, contract, target) -> list[str]:
    """Offline compatibility only. No runtime resolution and no page-tree persistence.

    The caller must supply a target from a trusted block registry, not from a module's
    self-declared recommendations. Exact type, meaning and cardinality are required.
    Collections need a real collection target; item fields require a future scoped-item
    contract, so they cannot be laundered into a scalar target here.
    """
    errors = storefront_contract_problems(contract)
    if errors:
        return ["binding: source contract is invalid"]
    if not _shape(binding, {"mode", "module", "source", "field", "on_missing"}, set(), "binding", errors):
        return errors
    if not _shape(target, {"type", "semantic", "cardinality", "element"}, set(), "target", errors):
        return errors
    # These declarations are identifiers, never embedded expressions or nested JSON.
    if any(not isinstance(binding.get(key), str) or len(binding[key]) > 120
           for key in ("mode", "module", "source", "field", "on_missing")):
        return errors + ["binding: fields must be bounded strings"]
    if any(not isinstance(target.get(key), str) or len(target[key]) > 120
           for key in ("type", "semantic", "cardinality", "element")):
        return errors + ["target: fields must be bounded strings"]
    if binding.get("mode") != "dynamic":
        errors.append("binding: only dynamic declarations are modeled; static content is unchanged")
    if binding.get("module") != contract["module"]:
        errors.append("binding: module mismatch")
    if binding.get("on_missing") not in ("hide", "empty"):
        errors.append("binding: explicit hide/empty behavior required")
    source = next((s for s in contract["sources"] if s["id"] == binding.get("source")), None)
    field = next((f for f in source["fields"] if f["id"] == binding.get("field")), None) if source else None
    if not field:
        return errors + ["binding: unknown source or field"]
    if target.get("type") != field["type"] or target.get("semantic") != field["semantic"]:
        errors.append("binding: type and semantic must both match")
    if target.get("cardinality") != source["cardinality"]:
        errors.append("binding: collection/item scope mismatch")
    if target.get("element") not in field["elements"]:
        errors.append("binding: incompatible target element")
    return errors
