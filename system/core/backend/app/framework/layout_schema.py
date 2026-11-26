"""Layout schema v1 (docs/modular-core-exploration.md, migration step 3).

Describes, as typed and versioned models, what the screen builder already stores and what
`/settings/screens` already returns. No behaviour change: nothing calls these models at request
time yet. Tests validate every activity's defaults and `resolve()` output against them, so the
schema cannot drift from the code, and later steps (activity layouts as data, workspace
overrides, the layout studio) build on one contract.

Two shapes:
- `RoleLayoutV1`: what is stored (workspace_layouts, kind "role", or an activity's per-role
  defaults): the role's home screen id, its menu groups of screen ids, its dashboard widgets.
- `ResolvedScreensV1`: what the app receives for the acting role, with permissions and active
  modules already applied (paths, labels and icons, no screen ids to look up).
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = 1
GROUP_ID = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
WidgetSize = Literal["s", "m", "l"]
ShellId = Literal["sidebar", "rail", "topnav"]
SHELL_IDS = ("sidebar", "rail", "topnav")  # "sidebar" is the classic look


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MenuEntryV1(_Strict):
    """One menu item: a screen id from the catalogue, with an optional label or icon override."""

    screen: str
    label: str | None = None
    icon: str | None = None


class MenuGroupV1(_Strict):
    id: str
    label: str = Field(min_length=1, max_length=64)
    items: list[MenuEntryV1] = Field(default_factory=list, max_length=60)

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not GROUP_ID.match(v):
            raise ValueError(f"invalid group id: {v}")
        return v


class DashboardEntryV1(_Strict):
    id: str
    size: WidgetSize | None = None


class RoleLayoutV1(_Strict):
    """A role's home, menu and dashboard as stored. Every field is optional: what is missing is
    taken from the activity's default for the role."""

    home: str | None = None
    menu: list[MenuGroupV1] | None = Field(default=None, max_length=12)
    dashboard: list[DashboardEntryV1] | None = None

    @field_validator("menu")
    @classmethod
    def _unique(cls, groups):
        if groups is None:
            return groups
        ids = [g.id for g in groups]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate group id")
        screens = [i.screen for g in groups for i in g.items]
        if len(screens) != len(set(screens)):
            raise ValueError("a screen appears twice in the menu")
        return groups


class ScreenItemV1(_Strict):
    id: str
    path: str
    label: str | None = None
    icon: str | None = None
    module: str | None = None


class ResolvedGroupV1(_Strict):
    id: str | None
    label: str | None
    items: list[ScreenItemV1]


class ResolvedWidgetV1(_Strict):
    id: str
    label: str | None = None
    module: str
    size: WidgetSize | None = None


class ResolvedScreensV1(_Strict):
    """The response of `/settings/screens`."""

    home: str
    menu: list[ResolvedGroupV1]
    dashboard: list[ResolvedWidgetV1]
    screens: list[ScreenItemV1]
    custom: bool
    shell: ShellId | None = None


def role_layout(data: dict) -> RoleLayoutV1:
    return RoleLayoutV1.model_validate(data)


def resolved_screens(data: dict) -> ResolvedScreensV1:
    return ResolvedScreensV1.model_validate(data)
