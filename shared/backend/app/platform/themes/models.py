"""Theme packages installed in a workspace (ADR-010 D3; migration v73). Mizan's themes
(app/themes/) and activities' (activities/<activity>/themes/) are files, not rows. The workspace's
chosen theme is tenants.palette["name"]."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.platform.tenancy.context import TenantScoped


class WorkspaceTheme(TenantScoped, Base):
    __tablename__ = "workspace_themes"

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
                                                 primary_key=True)
    theme_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    developer: Mapped[str] = mapped_column(String(32), nullable=False)
    theme: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Font and preview files: {"assets/x.woff2": "<base64>"} (packages are at most 4 MB).
    assets: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    package_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    installed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    installed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
