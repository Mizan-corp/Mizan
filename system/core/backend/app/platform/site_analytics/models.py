"""The public website's visit counters (ADR-016). Platform rows (no workspace); migration v108.

One row per day, page, event, language and referring site, holding a count: no visitor, IP,
browser or cookie is ever stored, so there is nothing personal to keep or delete."""
from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SiteAnalyticsDaily(Base):
    __tablename__ = "site_analytics_daily"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), primary_key=True)  # pageview | event
    name: Mapped[str] = mapped_column(String(32), primary_key=True)  # page_view, whatsapp_click…
    path: Mapped[str] = mapped_column(String(160), primary_key=True)
    lang: Mapped[str] = mapped_column(String(2), primary_key=True)
    ref_host: Mapped[str] = mapped_column(String(100), primary_key=True, default="", server_default=text("''"))
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
