"""Fields on shared records, fully customisable (ADR-006 D1, phase 4).

Records that variants extend (a product, a sale line, a customer…) keep extra values in an
`extra` JSON column. Which fields exist is data:
1. each active variant declares defaults in variant.json: "fields": {"product": [{...}]};
2. the workspace overrides them (label, required, hidden, options) or adds its own
   (workspace_fields). The screen builder (phase 5) edits the same rows.

A field: {"key", "label", "label_en", "type": text|number|date|boolean|select, "required",
"options": [...] (select), "hidden", "searchable"}.
"""
from __future__ import annotations

import re
import uuid
from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint, func, select, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.framework import variants
from app.platform.tenancy.context import TenantScoped

RECORDS = ("product", "sale", "sale_line", "customer", "supplier", "purchase_line")
TYPES = ("text", "number", "date", "boolean", "select")
KEY = re.compile(r"^[a-z][a-z0-9_]{0,47}$")


class WorkspaceField(TenantScoped, Base):
    """A workspace's own field, or its change to a variant's field (same key)."""
    __tablename__ = "workspace_fields"
    __table_args__ = (UniqueConstraint("tenant_id", "record", "key", name="uq_workspace_fields_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    record: Mapped[str] = mapped_column(String(32), nullable=False)
    key: Mapped[str] = mapped_column(String(48), nullable=False)
    definition: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def variant_fields(record: str, activity_id: str | None) -> list[dict]:
    """The fields the workspace's variants add to a record, in order."""
    out: list[dict] = []
    for module_id in variants.variants_for(activity_id):
        for f in (variants.variant(module_id, activity_id).get("fields") or {}).get(record, []):
            if isinstance(f, dict) and f.get("key"):
                out.append({**f, "source": f"{module_id}.{variants.variant_of(module_id, activity_id)}"})
    return out


async def fields_for(db: AsyncSession, record: str, activity_id: str | None, include_hidden: bool = False) -> list[dict]:
    """Variant fields with the workspace's changes, then the workspace's own fields."""
    merged = {f["key"]: {**f, "hidden": bool(f.get("hidden"))} for f in variant_fields(record, activity_id)}
    order = list(merged)
    rows = (await db.execute(select(WorkspaceField).where(WorkspaceField.record == record)
                             .order_by(WorkspaceField.position, WorkspaceField.created_at))).scalars().all()
    for row in rows:
        base = merged.get(row.key, {"key": row.key, "source": "workspace"})
        merged[row.key] = {**base, **(row.definition or {}), "key": row.key, "hidden": row.hidden}
        if row.key not in order:
            order.append(row.key)
    out = [merged[k] for k in order]
    return out if include_hidden else [f for f in out if not f["hidden"]]


def _coerce(field: dict, value):
    kind = field.get("type", "text")
    label = field.get("label") or field["key"]
    try:
        if kind == "number":
            if isinstance(value, bool):
                raise ValueError
            return float(value) if not isinstance(value, int) else value
        if kind == "boolean":
            if isinstance(value, bool):
                return value
            if str(value).lower() in ("true", "1", "yes"):
                return True
            if str(value).lower() in ("false", "0", "no"):
                return False
            raise ValueError
        if kind == "date":
            return date.fromisoformat(str(value)[:10]).isoformat()
        if kind == "select":
            if value not in (field.get("options") or []):
                raise ValueError
            return value
        return str(value).strip()[:500]
    except (TypeError, ValueError):
        raise HTTPException(422, f"قيمة غير صالحة للحقل «{label}»") from None


async def clean_extra(db: AsyncSession, record: str, extra: dict | None, activity_id: str | None,
                      *, partial: bool = False, current: dict | None = None, system: bool = False) -> dict:
    """Validate a record's extra values against its fields. Unknown keys are refused; read-only
    fields are set by rules only (`system`); required visible fields must be set (unless
    `partial`, e.g. an update that doesn't touch them)."""
    fields = {f["key"]: f for f in await fields_for(db, record, activity_id, include_hidden=True)}
    out = dict(current or {})
    for key, value in (extra or {}).items():
        field = fields.get(key)
        if field is None:
            raise HTTPException(422, f"حقل غير معروف: {key}")
        if field.get("readonly") and not system:
            continue  # filled by the variant's rules, not by the client
        if value is None or value == "":
            out.pop(key, None)
            continue
        out[key] = _coerce(field, value)
    if not partial:
        missing = [f.get("label") or k for k, f in fields.items()
                   if f.get("required") and not f.get("hidden") and out.get(k) in (None, "")]
        if missing:
            raise HTTPException(422, f"حقول مطلوبة: {'، '.join(missing)}")
    return out


def check_definition(definition: dict) -> dict:
    """A workspace field definition, cleaned."""
    kind = definition.get("type", "text")
    if kind not in TYPES:
        raise HTTPException(422, f"نوع حقل غير معروف: {kind}")
    out = {"type": kind}
    for k in ("label", "label_en"):
        if definition.get(k):
            out[k] = str(definition[k]).strip()[:128]
    out["required"] = bool(definition.get("required"))
    out["searchable"] = bool(definition.get("searchable"))
    if kind == "select":
        options = [str(o).strip()[:64] for o in definition.get("options") or [] if str(o).strip()]
        if not options:
            raise HTTPException(422, "حقل الاختيار يحتاج خيارات")
        out["options"] = options
    return out
