"""Helpers for the route security sweep (test_route_security_sweep.py).

- `classify(route)`: how a route is protected, read from its dependency tree.
- `build_request(route, ...)`: a plausible request for any route, from the OpenAPI schema: random UUIDs
  for ids, today for dates, the first value of an enum, required fields only.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from fastapi.routing import APIRoute

from app import dependencies as deps


def dependency_calls(dependant) -> list:
    out = []
    for d in dependant.dependencies:
        out.append(d.call)
        out += dependency_calls(d)
    return out


def _name(call) -> str:
    return getattr(call, "__qualname__", type(call).__name__)


def classify(route: APIRoute) -> str:
    """"signed_in" (an ERP session), "print" (a print token), "installation" (an installed module's
    server token), or "none"."""
    calls = dependency_calls(route.dependant)
    if deps.get_current_user in calls:
        return "signed_in"
    if deps.get_print_user in calls:
        return "print"
    if any(_name(c) == "installation" for c in calls):
        return "installation"
    return "none"


def has_perm_check(route: APIRoute) -> bool:
    """A permission (or platform staff) check in the dependency tree."""
    names = {_name(c) for c in dependency_calls(route.dependant)}
    return any(n.startswith(("require_perm.", "_clinic_guard.")) or n in ("require_superadmin", "require_is_manager",
                                                                          "require_finance_or_manager")
               for n in names)


def api_routes(app) -> list[APIRoute]:
    return [r for r in app.routes if isinstance(r, APIRoute)]


def operations(app) -> list[tuple[str, APIRoute]]:
    """(method, route) for every method of every route, sorted for stable output."""
    out = [(m, r) for r in api_routes(app) for m in sorted(r.methods - {"HEAD", "OPTIONS"})]
    return sorted(out, key=lambda x: (x[1].path, x[0]))


# ── request builder ────────────────────────────────────────────────────────────────────────────

class Builder:
    def __init__(self, openapi: dict, marker: str = "sweep"):
        self.spec = openapi
        self.marker = marker
        self.components = openapi.get("components", {}).get("schemas", {})

    def _resolve(self, schema: dict) -> dict:
        seen = 0
        while "$ref" in schema and seen < 20:
            schema = self.components.get(schema["$ref"].rsplit("/", 1)[-1], {})
            seen += 1
        return schema

    def example(self, schema: dict | None, depth: int = 0, name: str = ""):
        schema = self._resolve(schema or {})
        if depth > 6:
            return None
        if "const" in schema:
            return schema["const"]
        if "enum" in schema and schema["enum"]:
            return schema["enum"][0]
        if "default" in schema and schema["default"] is not None:
            return schema["default"]
        for key in ("anyOf", "oneOf"):
            if key in schema:
                options = [self._resolve(o) for o in schema[key]]
                options = [o for o in options if o.get("type") != "null"] or options
                return self.example(options[0], depth + 1, name)
        if "allOf" in schema:
            merged: dict = {}
            for part in schema["allOf"]:
                merged.update(self._resolve(part))
            return self.example(merged, depth + 1, name)
        t = schema.get("type")
        if isinstance(t, list):
            t = next((x for x in t if x != "null"), "string")
        if t == "object" or "properties" in schema:
            props = schema.get("properties", {})
            required = schema.get("required", [])
            return {k: self.example(props.get(k, {}), depth + 1, k) for k in required}
        if t == "array":
            n = schema.get("minItems", 0)
            return [self.example(schema.get("items", {}), depth + 1, name) for _ in range(n)]
        if t == "integer":
            return max(int(schema.get("minimum", schema.get("exclusiveMinimum", 0) + 1)), 1) \
                if "maximum" not in schema else int(schema.get("minimum", 1))
        if t == "number":
            lo = schema.get("minimum", schema.get("exclusiveMinimum", 0))
            return max(float(lo) + 1, 1.0) if "maximum" not in schema else float(schema.get("minimum", 1))
        if t == "boolean":
            return False
        return self._string(schema, name)

    def _string(self, schema: dict, name: str) -> str:
        fmt = schema.get("format")
        if fmt == "uuid" or name == "id" or name.endswith("_id"):
            return str(uuid.uuid4())
        if fmt == "date" or name.endswith("date") or name in ("date_from", "date_to", "start", "end"):
            return date.today().isoformat()
        if fmt == "date-time":
            return datetime.now(UTC).isoformat()
        if fmt == "email" or "email" in name:
            return "sweep@example.com"
        if name in ("month",) or name.endswith("_month"):
            return date.today().strftime("%Y-%m")
        if name in ("year",):
            return str(date.today().year)
        if name == "time" or name.endswith("_time"):
            return "10:00"
        if "phone" in name or "mobile" in name:
            return "01012345678"
        n = max(int(schema.get("minLength", 1)), 1)
        s = self.marker
        return (s * (n // len(s) + 1))[:max(n, len(s))][: schema.get("maxLength", 64)]

    def build(self, method: str, route: APIRoute, path_values: dict | None = None) -> dict:
        """{"url", "params", "json"} for one call."""
        op = self.spec["paths"].get(route.path_format, {}).get(method.lower(), {})
        path_values = path_values or {}
        url = route.path_format
        params: dict = {}
        for p in op.get("parameters", []):
            where, pname, schema = p.get("in"), p["name"], p.get("schema", {})
            if where == "path":
                value = path_values.get(pname)
                if value is None:
                    value = self.example(schema, name=pname)
                url = url.replace("{" + pname + "}", str(value))
            elif where == "query" and p.get("required"):
                params[pname] = self.example(schema, name=pname)
        body = None
        rb = op.get("requestBody")
        if rb:
            content = rb.get("content", {})
            if "application/json" in content:
                body = self.example(content["application/json"].get("schema", {}))
                if body is None:
                    body = {}
            else:
                body = {}
        return {"url": url, "params": params, "json": body, "multipart": rb is not None and
                "application/json" not in rb.get("content", {})}
