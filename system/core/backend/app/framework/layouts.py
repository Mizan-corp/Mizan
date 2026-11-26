"""What the screen builder saves (ADR-006 D4, phase 5), per workspace (workspace_layouts):

- kind 'role', target = a role's id: the role's home, menu and dashboard (framework/screens.py).
  Standard roles are platform rows shared by every workspace, so their layout lives here.
- kind 'form', target = a record (product, customer, supplier): the record's form.

A form arranges the record's fields in sections: the built-in ones its module declares in the
manifest ("forms": {"product": {"label", "fields": [{"key", "label", "locked"?, "hidden"?}]}})
and the record's custom fields (framework/fields.py). Layout: {"sections": [{"id", "label",
"fields": [keys]}], "hidden": [keys]}. Locked fields and required custom fields can't be hidden;
a field placed nowhere goes to the first section (built-in) or the last (custom), so fields added
later show up.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from functools import lru_cache

from fastapi import HTTPException
from sqlalchemy import DateTime, String, UniqueConstraint, func, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.framework import fields as F
from app.framework.screens import GROUP_ID
from app.platform.tenancy.context import TenantScoped

KINDS = ("role", "form")


class WorkspaceLayout(TenantScoped, Base):
    __tablename__ = "workspace_layouts"
    __table_args__ = (UniqueConstraint("tenant_id", "kind", "target", name="uq_workspace_layouts_target"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    target: Mapped[str] = mapped_column(String(64), nullable=False)
    layout: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


async def get(db: AsyncSession, kind: str, target: str) -> dict:
    row = await db.scalar(select(WorkspaceLayout.layout).where(WorkspaceLayout.kind == kind, WorkspaceLayout.target == target))
    return row or {}


async def save(db: AsyncSession, kind: str, target: str, layout: dict, user_id) -> None:
    row = (await db.execute(select(WorkspaceLayout).where(WorkspaceLayout.kind == kind,
                                                          WorkspaceLayout.target == target))).scalar_one_or_none()
    if row is None:
        row = WorkspaceLayout(kind=kind, target=target)
        db.add(row)
    row.layout, row.updated_by = layout, user_id


async def reset(db: AsyncSession, kind: str, target: str) -> None:
    row = (await db.execute(select(WorkspaceLayout).where(WorkspaceLayout.kind == kind,
                                                          WorkspaceLayout.target == target))).scalar_one_or_none()
    if row is not None:
        await db.delete(row)


# ── Forms ─────────────────────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def forms() -> dict[str, dict]:
    """Every record's form as modules declare it: {record: {"label", "module", "fields"}}."""
    from app.framework.loader import manifest_index

    out = {}
    for module_id, m in manifest_index().items():
        if m.get("status") == "planned":
            continue
        for record, form in (m.get("forms") or {}).items():
            out[record] = {"label": form.get("label") or record, "module": module_id, "fields": form.get("fields") or []}
    return out


def _form(record: str) -> dict:
    form = forms().get(record)
    if form is None or record not in F.RECORDS:
        raise HTTPException(404, "نموذج غير معروف")
    return form


async def _fields(db: AsyncSession, record: str, activity_id: str | None) -> dict[str, dict]:
    """The form's fields by key: built-in, then custom (visible ones), in their default order."""
    out = {}
    for f in _form(record)["fields"]:
        out[f["key"]] = {"key": f["key"], "label": f.get("label") or f["key"], "builtin": True,
                         "locked": bool(f.get("locked")), "default_hidden": bool(f.get("hidden"))}
    for f in await F.fields_for(db, record, activity_id):
        if f["key"] in out:
            continue  # a custom field can't take a built-in field's key (refused when it's added)
        out[f["key"]] = {**f, "builtin": False, "locked": bool(f.get("required")), "default_hidden": False}
    return out


def _default_layout(fields: dict[str, dict]) -> dict:
    builtin = [k for k, f in fields.items() if f["builtin"] and not f["default_hidden"]]
    custom = [k for k, f in fields.items() if not f["builtin"]]
    sections = [{"id": "main", "label": "البيانات الأساسية", "fields": builtin}]
    if custom:
        sections.append({"id": "extra", "label": "بيانات إضافية", "fields": custom})
    return {"sections": sections, "hidden": [k for k, f in fields.items() if f["default_hidden"]]}


async def form_for(db: AsyncSession, record: str, activity_id: str | None) -> dict:
    """The record's form for this workspace: sections of fields, hidden ones left out."""
    fields = await _fields(db, record, activity_id)
    saved = await get(db, "form", record)
    layout = saved or _default_layout(fields)
    in_layout = {k for s in layout.get("sections") or [] for k in s.get("fields") or []}
    hidden = {k for k in layout.get("hidden") or [] if k in fields and not fields[k]["locked"]}
    hidden |= {k for k, f in fields.items() if f["default_hidden"] and k not in in_layout and not f["locked"]}
    placed: set[str] = set()
    sections = []
    for s in layout.get("sections") or []:
        keys = [k for k in s.get("fields") or [] if k in fields and k not in hidden and k not in placed]
        placed.update(keys)
        sections.append({"id": s.get("id"), "label": s.get("label"), "fields": keys})
    if not sections:
        sections = [{"id": "main", "label": "البيانات الأساسية", "fields": []}]
    # Fields placed nowhere (added since the layout was saved): built-in first, custom last.
    for k, f in fields.items():
        if k in placed or k in hidden:
            continue
        (sections[0] if f["builtin"] else sections[-1])["fields"].append(k)
        placed.add(k)
    return {
        "record": record,
        "label": _form(record)["label"],
        "custom": bool(saved),
        "sections": [{**s, "fields": [fields[k] for k in s["fields"]]} for s in sections if s["fields"]],
        "hidden": [fields[k] for k in fields if k not in placed],
    }


async def check_form(db: AsyncSession, record: str, activity_id: str | None, layout: dict) -> dict:
    """A form layout from the builder, cleaned."""
    fields = await _fields(db, record, activity_id)
    sections, seen_ids, placed = [], set(), set()
    for s in (layout.get("sections") or [])[:12]:
        sid = str(s.get("id") or "").strip()
        label = str(s.get("label") or "").strip()[:64]
        if not GROUP_ID.match(sid) or sid in seen_ids:
            raise HTTPException(422, f"معرّف قسم غير صالح: {sid or '—'}")
        if not label:
            raise HTTPException(422, "اسم القسم مطلوب")
        seen_ids.add(sid)
        keys = []
        for k in s.get("fields") or []:
            if k not in fields:
                raise HTTPException(422, f"حقل غير معروف: {k}")
            if k in placed:
                raise HTTPException(422, f"الحقل مكرر: {fields[k]['label']}")
            placed.add(k)
            keys.append(k)
        sections.append({"id": sid, "label": label, "fields": keys})
    if not sections:
        raise HTTPException(422, "النموذج يحتاج قسمًا واحدًا على الأقل")
    hidden = []
    for k in layout.get("hidden") or []:
        if k not in fields or k in placed:
            continue
        if fields[k]["locked"]:
            raise HTTPException(422, f"لا يمكن إخفاء «{fields[k]['label']}»: حقل أساسي أو مطلوب")
        hidden.append(k)
    return {"sections": sections, "hidden": hidden}
