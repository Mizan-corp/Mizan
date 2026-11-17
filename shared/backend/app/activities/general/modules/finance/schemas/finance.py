from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

class FinancialCategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    type: Literal["income", "expense"] = "expense"
    color: str = Field("#64748b", pattern=r"^#[0-9a-fA-F]{6}$")


class FinancialCategoryUpdate(BaseModel):
    """Only the fields sent change. The type is fixed: the ledger account it maps to depends on it."""
    name: str | None = Field(None, min_length=1, max_length=128)
    color: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    is_active: bool | None = None


class PermissionsUpdate(BaseModel):
    # Checked against the platform's and the workspace's declared permissions by the route.
    permissions: list[str] = Field(default_factory=list, max_length=500)
    is_manager: bool = False
