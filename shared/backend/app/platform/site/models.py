"""Site pages and their publish revisions (ADR-015 step S2, docs/builder/page-engine.md).

A page is a JSON tree (block type, per-device settings, content per language, children).
The draft is what the studio edits and autosaves; the published tree is what the public
renderer serves. Publish copies the draft to the published tree and writes an immutable
revision; rollback copies a revision back into the draft. Nothing reaches the public site
until publish. Pages are archived, not deleted (docs/MODULE_STANDARD.md).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.platform.tenancy.context import TenantScoped


class SitePage(TenantScoped, Base):
    __tablename__ = "site_pages"
    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_site_pages_slug"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    # Titles per language, e.g. {"ar": "…", "en": "…"} (ADR-015 D7).
    titles: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    # draft (studio only) | published (public) | archived (kept, not served; never hard-deleted)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    draft_tree: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    published_tree: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Language offering of the PUBLISHED page: copied from titles by publish, never by
    # draft save, so adding/editing a language in the draft never mutates the live
    # page's languages (or its title) before an explicit publish. NULL on legacy rows
    # predating the split; public serving coalesces to titles.
    published_titles: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())


class SitePageRevision(TenantScoped, Base):
    """An immutable snapshot written at publish. Rollback copies one back into the draft;
    nothing ever updates or deletes a revision row."""

    __tablename__ = "site_page_revisions"
    __table_args__ = (UniqueConstraint("page_id", "number", name="uq_site_page_revisions_number"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("site_pages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    tree: Mapped[dict] = mapped_column(JSONB, nullable=False)
    titles: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SiteFormSubmission(TenantScoped, Base):
    """One visitor submission of a published form block. Written only by the
    public form endpoint after the activation gate, rate limit, honeypot and
    exact-key payload validation; read by the owning workspace in the Website
    tab. The block id pins which form on the page sent it; payload holds only
    the fields that block had enabled at render time."""

    __tablename__ = "site_form_submissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("site_pages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    block_id: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class SiteSettings(TenantScoped, Base):
    """One row per workspace: the site's durable theme and chrome (ADR-015 D4/D5).

    The value is the validated theme document the renderer consumes (colors,
    typography, shape) plus the header and footer chrome. Until now theme and chrome
    were synthesized per preview call; this record makes them survive reloads.
    """

    __tablename__ = "site_settings"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_site_settings_tenant"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())
