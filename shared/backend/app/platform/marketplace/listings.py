"""The marketplace (ADR-007 milestone 2, #105): listings of developers' modules and themes.

- A developer team **submits** a signed package (portal or `mizan publish`): it is verified like a
  private install (signature, Mizan's certificate, key not revoked, the team's namespace, the
  validator), must be a newer version than the last approved one, and waits for review.
- The Mizan team **reviews** it in the admin panel: approving **countersigns** it (`MZP1`: item,
  version, package SHA-256, signed with the platform key) and lists that version; rejecting gives
  the developer a reason. A listing can be delisted (hidden from the store; installs stay).
- Workspaces **install** listed versions from the store (the app's module centre): the stored
  package is verified again, countersignature included, then installed exactly as from a file.

Free listings only for now; paid ones come with Paymob (#65). Activities are listed too, but a
workspace takes one through an activity change (#107, ADR-012), not an install from the store.
Platform tables (no workspace).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from packaging.version import InvalidVersion, Version
from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, Text, func, or_, select, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

COUNTERSIGN_PREFIX = "MZP1"
KINDS = ("community", "theme", "activity")
STORE_KINDS = ("community", "theme")  # installed from the store; activities are switched to


class MarketplaceVersion(Base):
    __tablename__ = "marketplace_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
                                          server_default=text("gen_random_uuid()"))
    item_id: Mapped[str] = mapped_column(String(80), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    team_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("developer_teams.id", ondelete="CASCADE"), nullable=False)
    package: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    manifest: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="in_review", server_default=text("'in_review'"))
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("developer_users.id", ondelete="SET NULL"), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    countersignature: Mapped[str | None] = mapped_column(Text, nullable=True)


class MarketplaceItem(Base):
    __tablename__ = "marketplace_items"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    team_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("developer_teams.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    name_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="listed", server_default=text("'listed'"))
    status_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    installs: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def _version(v: str) -> Version:
    try:
        return Version(v)
    except InvalidVersion:
        raise HTTPException(422, f"Version {v!r} isn't a valid version number (e.g. 1.2.0)") from None


# ─── Developers: submit, list, withdraw ─────────────────────────────────────────────────────


async def submit(db: AsyncSession, team, user_id, data: bytes, say=lambda en, ar: en) -> MarketplaceVersion:
    """Verify and store a package for review. `say(en, ar)` picks the developer's language."""
    from app.framework import package as mzm
    from app.platform.developers.service import key_revoked

    if len(data) > mzm.MAX_BYTES:
        raise HTTPException(413, say("The package is larger than 4 MB", "حجم الحزمة أكبر من 4 ميجابايت"))
    try:
        pkg = mzm.verify(data)
    except mzm.PackageError as e:
        raise HTTPException(422, say(f"The package was refused: {e}", f"رُفضت الحزمة: {e}")) from None
    if await key_revoked(db, pkg.key_id):
        raise HTTPException(422, say("The package is signed with a revoked key", "الحزمة موقّعة بمفتاح أُلغي"))
    if pkg.developer != team.handle:
        raise HTTPException(403, say(f"This package belongs to team {pkg.developer}", f"هذه الحزمة تخص فريق {pkg.developer}"))
    if pkg.kind not in KINDS:
        raise HTTPException(422, say("Only modules, themes and activities can be published",
                                     "يمكن نشر الوحدات والمظاهر والأنشطة فقط"))
    item_id, version = pkg.manifest["id"], pkg.manifest["version"]
    if await db.scalar(select(MarketplaceVersion.id).where(MarketplaceVersion.item_id == item_id, MarketplaceVersion.version == version)):
        raise HTTPException(409, say(f"{item_id} {version} was already submitted: raise the version",
                                     f"سبق إرسال {item_id} {version}: ارفع رقم الإصدار"))
    item = await db.get(MarketplaceItem, item_id)
    if item and _version(version) <= _version(item.current_version):
        raise HTTPException(409, say(f"The listed version is {item.current_version}: submit a newer one",
                                     f"الإصدار المنشور {item.current_version}: أرسل إصدارًا أحدث"))
    _version(version)
    row = MarketplaceVersion(item_id=item_id, version=version, kind=pkg.kind, team_id=team.id, package=data,
                             sha256=pkg.sha256, size=len(data), manifest=pkg.manifest, submitted_by=user_id)
    db.add(row)
    await db.flush()
    return row


def version_out(v: MarketplaceVersion) -> dict:
    return {
        "id": str(v.id), "item_id": v.item_id, "version": v.version, "kind": v.kind, "status": v.status,
        "name": v.manifest.get("name"), "name_en": v.manifest.get("name_en"), "size": v.size, "sha256": v.sha256,
        "submitted_at": v.submitted_at.isoformat() if v.submitted_at else None,
        "reviewed_at": v.reviewed_at.isoformat() if v.reviewed_at else None, "review_note": v.review_note,
    }


def item_out(i: MarketplaceItem, team_handle: str | None = None) -> dict:
    return {
        "id": i.id, "kind": i.kind, "name": i.name, "name_en": i.name_en, "description": i.description,
        "version": i.current_version, "status": i.status, "status_note": i.status_note, "installs": i.installs,
        "developer": team_handle, "updated_at": i.updated_at.isoformat() if i.updated_at else None,
    }


async def team_submissions(db: AsyncSession, team) -> dict:
    versions = (await db.execute(select(MarketplaceVersion).where(MarketplaceVersion.team_id == team.id)
                                 .order_by(MarketplaceVersion.submitted_at.desc()).limit(200))).scalars().all()
    items = (await db.execute(select(MarketplaceItem).where(MarketplaceItem.team_id == team.id)
                              .order_by(MarketplaceItem.id))).scalars().all()
    return {"items": [item_out(i, team.handle) for i in items], "versions": [version_out(v) for v in versions]}


async def withdraw(db: AsyncSession, team, item_id: str, version: str, say=lambda en, ar: en) -> None:
    row = await db.scalar(select(MarketplaceVersion).where(MarketplaceVersion.team_id == team.id,
                                                           MarketplaceVersion.item_id == item_id, MarketplaceVersion.version == version))
    if not row:
        raise HTTPException(404, say("Submission not found", "الإرسال غير موجود"))
    if row.status != "in_review":
        raise HTTPException(409, say("Only a submission in review can be withdrawn", "يمكن سحب الإرسال قيد المراجعة فقط"))
    row.status = "withdrawn"


# ─── The Mizan team: review ─────────────────────────────────────────────────────────────────


def countersign(v: MarketplaceVersion) -> str:
    from app.platform.licensing import keys

    return keys.sign({"item": v.item_id, "version": v.version, "sha256": v.sha256, "kind": v.kind,
                      "approved_at": datetime.now(UTC).isoformat()}, prefix=COUNTERSIGN_PREFIX)


async def approve(db: AsyncSession, v: MarketplaceVersion, admin_id, note: str | None = None) -> MarketplaceItem:
    if v.status != "in_review":
        raise HTTPException(409, "This submission was already decided")
    now = datetime.now(UTC)
    v.status, v.reviewed_by, v.reviewed_at, v.review_note = "approved", admin_id, now, note
    v.countersignature = countersign(v)
    m = v.manifest
    item = await db.get(MarketplaceItem, v.item_id)
    if item is None:
        item = MarketplaceItem(id=v.item_id, kind=v.kind, team_id=v.team_id, name=m.get("name") or v.item_id,
                               current_version=v.version, status="listed")
        db.add(item)
    item.name, item.name_en = m.get("name") or v.item_id, m.get("name_en")
    item.description = m.get("description")
    item.current_version, item.updated_at = v.version, now
    return item


async def reject(db: AsyncSession, v: MarketplaceVersion, admin_id, note: str) -> None:
    if v.status != "in_review":
        raise HTTPException(409, "This submission was already decided")
    if not (note or "").strip():
        raise HTTPException(422, "Say why, for the developer")
    v.status, v.reviewed_by, v.reviewed_at, v.review_note = "rejected", admin_id, datetime.now(UTC), note.strip()


async def set_listed(db: AsyncSession, item_id: str, listed: bool, note: str | None) -> MarketplaceItem:
    item = await db.get(MarketplaceItem, item_id)
    if not item:
        raise HTTPException(404, "Listing not found")
    item.status, item.status_note, item.updated_at = ("listed" if listed else "delisted"), note, datetime.now(UTC)
    return item


# ─── Workspaces: the store ──────────────────────────────────────────────────────────────────


async def store(db: AsyncSession, kind: str | None = None, q: str | None = None) -> list[dict]:
    from app.platform.developers.models import DeveloperTeam

    stmt = (select(MarketplaceItem, DeveloperTeam.handle).join(DeveloperTeam, DeveloperTeam.id == MarketplaceItem.team_id)
            .where(MarketplaceItem.status == "listed").order_by(MarketplaceItem.installs.desc(), MarketplaceItem.name))
    stmt = stmt.where(MarketplaceItem.kind == kind) if kind else stmt.where(MarketplaceItem.kind.in_(STORE_KINDS))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(MarketplaceItem.name.ilike(like), MarketplaceItem.name_en.ilike(like),
                              MarketplaceItem.description.ilike(like), MarketplaceItem.id.ilike(like)))
    return [item_out(i, handle) for i, handle in (await db.execute(stmt.limit(200))).all()]


async def listed_package(db: AsyncSession, item_id: str):
    """The listed version's package, verified again: the developer's signature and certificate,
    the key not revoked since, and Mizan's countersignature over exactly these bytes."""
    from app.framework import package as mzm
    from app.platform.developers.service import key_revoked
    from app.platform.licensing import keys

    item = await db.get(MarketplaceItem, item_id)
    if not item or item.status != "listed" or item.kind not in STORE_KINDS:
        raise HTTPException(404, "هذه الإضافة غير متاحة في المتجر")
    v = await db.scalar(select(MarketplaceVersion).where(MarketplaceVersion.item_id == item_id,
                                                         MarketplaceVersion.version == item.current_version,
                                                         MarketplaceVersion.status == "approved"))
    if not v:
        raise HTTPException(404, "هذه الإضافة غير متاحة في المتجر")
    try:
        pkg = mzm.verify(v.package)
        seal = keys.verify(v.countersignature or "", prefix=COUNTERSIGN_PREFIX)
    except (mzm.PackageError, keys.LicenceError):
        raise HTTPException(409, "تعذر التحقق من هذه الإضافة؛ تواصل مع الدعم") from None
    if seal.get("sha256") != pkg.sha256 or seal.get("item") != item_id or seal.get("version") != v.version:
        raise HTTPException(409, "تعذر التحقق من هذه الإضافة؛ تواصل مع الدعم")
    if await key_revoked(db, pkg.key_id):
        raise HTTPException(409, "أُلغي مفتاح توقيع مطوّر هذه الإضافة؛ لا يمكن تثبيتها")
    return item, pkg


async def count_install(db: AsyncSession, item_id: str) -> None:
    await db.execute(text("UPDATE marketplace_items SET installs = installs + 1 WHERE id = :i"), {"i": item_id})
