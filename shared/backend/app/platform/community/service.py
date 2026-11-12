"""Community modules (ADR-007): what's installed in the workspace, their permissions and menus, and
their records, validated against the module's entities.

Who may use an entity's screens: the permission its menu item declares (held by the role the user
acts as); none declared means every signed-in user of the workspace. The standard admin holds
every permission declared in the workspace, community ones included (access.load_acting).
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException
from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.community.models import CommunityModule, ExtRecord

# Built-in records an entity may reference: table and the column shown for them.
BUILT_IN = {"customers": ("customers", "name"), "suppliers": ("suppliers", "name"), "products": ("products", "name"),
            "employees": ("hr_employees", "name"), "branches": ("warehouses", "name")}
PAGE = 50


async def installed(db: AsyncSession) -> list[CommunityModule]:
    return list((await db.execute(select(CommunityModule).where(CommunityModule.status == "active")
                                  .order_by(CommunityModule.installed_at))).scalars())


async def workspace_permissions(db: AsyncSession) -> list[dict]:
    """Permissions the workspace's community modules declare: [{"id", "name", "name_en", "module"}]."""
    out = []
    for m in await installed(db):
        for p in m.manifest.get("permissions") or []:
            out.append({**p, "module": m.module_id})
    return out


def entity_permission(module: CommunityModule, entity: str) -> str | None:
    for item in module.manifest.get("menu") or []:
        if item.get("entity") == entity and item.get("permission"):
            return item["permission"]
    return None


def may_use(user, module: CommunityModule, entity: str) -> bool:
    from app.platform.permissions.access import can

    needed = entity_permission(module, entity)
    return needed is None or can(user, needed)


async def menu_items(db: AsyncSession, user) -> list[dict]:
    """The installed modules' screens this user may open, for the app's menu."""
    out = []
    for m in await installed(db):
        for item in m.manifest.get("menu") or []:
            if may_use(user, m, item["entity"]):
                out.append({"id": f"{m.module_id}.{item['entity']}", "path": f"/x/{m.module_id}/{item['entity']}",
                            "label": item["label"], "icon": item.get("icon") or m.manifest.get("icon") or "Blocks",
                            "module": m.module_id, "module_name": m.manifest.get("name")})
    return out


async def module_entity(db: AsyncSession, user, module_id: str, entity: str) -> tuple[CommunityModule, dict]:
    m = await db.scalar(select(CommunityModule).where(CommunityModule.module_id == module_id,
                                                      CommunityModule.status == "active"))
    if m is None or entity not in (m.entities or {}):
        raise HTTPException(404, "الشاشة غير موجودة")
    if not may_use(user, m, entity):
        raise HTTPException(403, "لا تملك صلاحية هذه الشاشة")
    return m, m.entities[entity]


# ── Records ───────────────────────────────────────────────────────────────────

async def clean(db: AsyncSession, module: CommunityModule, entity: dict, values: dict, partial: bool = False) -> dict:
    """`values` checked and converted against the entity's fields (Arabic messages)."""
    if not isinstance(values, dict):
        raise HTTPException(422, "بيانات غير صالحة")
    fields = {f["key"]: f for f in entity["fields"]}
    unknown = set(values) - set(fields)
    if unknown:
        raise HTTPException(422, f"حقول غير معروفة: {'، '.join(sorted(unknown))}")
    out: dict = {}
    for key, value in values.items():
        f = fields[key]
        if value in (None, ""):
            out[key] = None
            continue
        kind, label = f.get("type", "text"), f.get("label") or key
        try:
            if kind == "text":
                value = str(value).strip()[:2000]
            elif kind == "number":
                value = float(value)
            elif kind == "money":
                value = str(Decimal(str(value)).quantize(Decimal("0.01")))
            elif kind == "date":
                value = date.fromisoformat(str(value)[:10]).isoformat()
            elif kind == "boolean":
                value = value if isinstance(value, bool) else str(value).lower() in ("1", "true", "yes", "نعم")
            elif kind == "select":
                if value not in f.get("options", []):
                    raise ValueError
            elif kind == "reference":
                value = str(uuid.UUID(str(value)))
                if not await _reference_exists(db, module, f["to"], value):
                    raise HTTPException(422, f"«{label}»: السجل المختار غير موجود")
        except (ValueError, TypeError, InvalidOperation):
            raise HTTPException(422, f"«{label}»: قيمة غير صالحة") from None
        out[key] = value
    if not partial:
        missing = [f.get("label") or k for k, f in fields.items() if f.get("required") and out.get(k) in (None, "")]
        if missing:
            raise HTTPException(422, f"حقول مطلوبة: {'، '.join(missing)}")
    return out


async def _reference_exists(db: AsyncSession, module: CommunityModule, to: str, ref: str) -> bool:
    if to in BUILT_IN:
        table, _ = BUILT_IN[to]
        return bool(await db.scalar(text(f"SELECT 1 FROM {table} WHERE id = CAST(:i AS uuid)"), {"i": ref}))  # noqa: S608 (fixed names)
    return bool(await db.scalar(select(ExtRecord.id).where(
        ExtRecord.id == uuid.UUID(ref), ExtRecord.module_id == module.module_id, ExtRecord.entity == to,
        ExtRecord.deleted_at.is_(None))))


async def labels_for(db: AsyncSession, module: CommunityModule, entity: dict, rows: list[dict], depth: int = 0) -> dict[str, str]:
    """Display names for the references in `rows` ({id: name})."""
    wanted: dict[str, set[str]] = {}
    for f in entity["fields"]:
        if f.get("type") == "reference":
            ids = {r["data"].get(f["key"]) for r in rows if r["data"].get(f["key"])}
            if ids:
                wanted.setdefault(f["to"], set()).update(ids)
    out: dict[str, str] = {}
    for to, ids in wanted.items():
        if to in BUILT_IN:
            table, col = BUILT_IN[to]
            res = await db.execute(text(f"SELECT id::text, {col} FROM {table} WHERE id = ANY(CAST(:ids AS uuid[]))"),  # noqa: S608
                                   {"ids": list(ids)})
            out.update({i: n for i, n in res.all()})
        else:
            target = module.entities.get(to) or {}
            title = target.get("title")
            recs = list((await db.execute(select(ExtRecord).where(ExtRecord.id.in_([uuid.UUID(i) for i in ids])))).scalars())
            title_field = next((f for f in target.get("fields", []) if f["key"] == title), {})
            nested: dict[str, str] = {}
            if title_field.get("type") == "reference" and depth < 1:
                # Titled by another reference (a visit by its customer): show that one's name.
                nested = await labels_for(db, module, target, [{"data": r.data} for r in recs], depth + 1)
            for r in recs:
                value = r.data.get(title) if title else None
                out[str(r.id)] = nested.get(str(value), str(value)) if value else str(r.id)[:8]
    return out


async def reference_options(db: AsyncSession, module: CommunityModule, entity: dict, key: str, q: str | None) -> list[dict]:
    """Choices for a reference field: [{"id", "label"}] (first 30 matching)."""
    f = next((f for f in entity["fields"] if f["key"] == key and f.get("type") == "reference"), None)
    if f is None:
        raise HTTPException(404, "حقل غير موجود")
    like = f"%{(q or '').strip()}%"
    if f["to"] in BUILT_IN:
        table, col = BUILT_IN[f["to"]]
        res = await db.execute(text(f"SELECT id::text, {col} FROM {table} WHERE {col} ILIKE :q ORDER BY {col} LIMIT 30"),  # noqa: S608
                               {"q": like})
        return [{"id": i, "label": n} for i, n in res.all()]
    target = module.entities.get(f["to"]) or {}
    title = target.get("title")
    stmt = select(ExtRecord).where(ExtRecord.module_id == module.module_id, ExtRecord.entity == f["to"],
                                   ExtRecord.deleted_at.is_(None))
    if q and title:
        stmt = stmt.where(ExtRecord.data[title].astext.ilike(like))
    rows = list((await db.execute(stmt.order_by(ExtRecord.created_at.desc()).limit(30))).scalars())
    # The title may itself be a reference (a visit titled by its customer): show the name.
    labels = await labels_for(db, module, target, [{"data": r.data} for r in rows]) if title else {}
    out = []
    for r in rows:
        value = r.data.get(title) if title else None
        out.append({"id": str(r.id), "label": labels.get(str(value), str(value)) if value else str(r.id)[:8]})
    return out


def record_out(r: ExtRecord) -> dict:
    return {"id": str(r.id), "data": r.data, "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None}


async def list_records(db: AsyncSession, module: CommunityModule, entity: dict, q: str | None, page: int) -> dict:
    base = select(ExtRecord).where(ExtRecord.module_id == module.module_id, ExtRecord.entity == entity["id"],
                                   ExtRecord.deleted_at.is_(None))
    if q:
        like = f"%{q.strip()}%"
        texts = [f["key"] for f in entity["fields"] if f.get("type", "text") in ("text", "select")]
        if texts:
            base = base.where(or_(*[ExtRecord.data[k].astext.ilike(like) for k in texts]))
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    rows = [record_out(r) for r in (await db.execute(base.order_by(ExtRecord.created_at.desc())
                                                    .offset((page - 1) * PAGE).limit(PAGE))).scalars()]
    return {"items": rows, "total": total, "page": page, "pages": max(1, -(-total // PAGE)),
            "labels": await labels_for(db, module, entity, rows)}


async def get_record(db: AsyncSession, module: CommunityModule, entity: dict, record_id: uuid.UUID) -> ExtRecord:
    r = await db.scalar(select(ExtRecord).where(ExtRecord.id == record_id, ExtRecord.module_id == module.module_id,
                                                ExtRecord.entity == entity["id"], ExtRecord.deleted_at.is_(None)))
    if r is None:
        raise HTTPException(404, "السجل غير موجود")
    return r


async def create_record(db: AsyncSession, module: CommunityModule, entity: dict, values: dict, user_id) -> ExtRecord:
    r = ExtRecord(module_id=module.module_id, entity=entity["id"], data=await clean(db, module, entity, values),
                  created_by=user_id)
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return r


async def update_record(db: AsyncSession, module: CommunityModule, entity: dict, r: ExtRecord, values: dict) -> ExtRecord:
    merged = {**r.data, **await clean(db, module, entity, values, partial=True)}
    await clean(db, module, entity, merged)  # still complete
    r.data = merged
    r.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(r)
    return r


async def delete_record(db: AsyncSession, r: ExtRecord) -> None:
    r.deleted_at = datetime.now(UTC)
    await db.commit()


# ── Installing ───────────────────────────────────────────────────────────────

async def install(db: AsyncSession, package, user_id, approved_scopes: list[str]) -> CommunityModule:
    """Install (or update) a verified package in the bound workspace. Every scope it asks for must
    be in `approved_scopes`."""
    asked = list(package.manifest.get("scopes") or [])
    missing = [s for s in asked if s not in approved_scopes]
    if missing:
        raise HTTPException(409, "يجب الموافقة على صلاحيات الوحدة أولًا")
    mid = package.manifest["id"]
    row = await db.scalar(select(CommunityModule).where(CommunityModule.module_id == mid))
    if row is None:
        row = CommunityModule(module_id=mid)
        db.add(row)
    row.version, row.developer = package.manifest["version"], package.developer
    row.manifest, row.entities, row.scopes = package.manifest, package.entities, asked
    row.package_sha256, row.status, row.installed_by = package.sha256, "active", user_id
    if row.installed_at is not None:  # an update: its records stay
        row.updated_at = datetime.now(UTC)
    await db.commit()
    return row


async def uninstall(db: AsyncSession, module_id: str, delete_records: bool = False) -> None:
    """Remove a module. Its records are kept (hidden) unless `delete_records`; reinstalling brings them back."""
    row = await db.scalar(select(CommunityModule).where(CommunityModule.module_id == module_id))
    if row is None:
        raise HTTPException(404, "الوحدة غير مثبتة")
    if delete_records:
        await db.execute(delete(ExtRecord).where(ExtRecord.module_id == module_id))
        await db.delete(row)
    else:
        row.status = "removed"
    await db.commit()
