"""Layout schema v1 (migration step 3): the schema matches what the code produces today."""
import pytest
from pydantic import ValidationError

from app.framework import screens
from app.framework.layout_schema import ResolvedScreensV1, SCHEMA_VERSION, resolved_screens, role_layout

ALL_PERMS = frozenset({"*"})


def _activities():
    from app.catalog import activities

    return [None, *sorted(activities())]


def test_schema_version_is_one():
    assert SCHEMA_VERSION == 1


@pytest.mark.parametrize("activity", _activities())
def test_activity_defaults_fit_the_stored_layout_schema(activity):
    for role in (None, "owner", "manager", "cashier"):
        d = screens.defaults(activity, role)
        # The builder form {"home", "menu", "dashboard"}: validates as a stored role layout.
        stored = {"home": d["home"], "menu": d["menu"], "dashboard": d["dashboard"]}
        role_layout(stored)


@pytest.mark.parametrize("activity", _activities())
def test_resolve_output_fits_the_response_schema(activity):
    for role in (None, "owner", "cashier"):
        out = screens.resolve({}, activity, role, ALL_PERMS, ["core"])
        parsed = resolved_screens(out)
        assert isinstance(parsed, ResolvedScreensV1)


def test_check_layout_output_is_a_valid_stored_layout():
    cat_screens, cat_widgets = screens.catalogue()
    sid = next(iter(cat_screens))
    wid = next(iter(cat_widgets), None)
    layout = {"home": sid, "menu": [{"id": "main", "label": "Main", "items": [{"screen": sid}]}]}
    if wid:
        layout["dashboard"] = [{"id": wid, "size": "m"}]
    cleaned = screens.check_layout(layout)
    role_layout(cleaned)


def test_schema_rejects_bad_layouts():
    with pytest.raises(ValidationError):
        role_layout({"menu": [{"id": "Bad Id", "label": "x", "items": []}]})
    with pytest.raises(ValidationError):
        role_layout({"menu": [{"id": "a", "label": "x", "items": []}, {"id": "a", "label": "y", "items": []}]})
    with pytest.raises(ValidationError):
        role_layout({"menu": [{"id": "a", "label": "x", "items": [{"screen": "s"}]}, {"id": "b", "label": "y", "items": [{"screen": "s"}]}]})
    with pytest.raises(ValidationError):
        role_layout({"unknown_key": 1})
    with pytest.raises(ValidationError):
        role_layout({"dashboard": [{"id": "w", "size": "xl"}]})


# ---- step 4: activity layouts as data (layout.json) ----
import json
from pathlib import Path

BASELINE = Path(__file__).with_name("activity_layouts.baseline.json")


def test_activity_layouts_resolve_exactly_as_before_the_move():
    """tests/activity_layouts.baseline.json was captured from activity.json BEFORE retail and
    general moved their home/menu/dashboard/roles into layout.json. Resolution must not change."""
    from app.catalog import activities
    from app.framework import variants

    now = {}
    for a in [None, *activities()]:
        act = variants.activity(a)
        now[str(a)] = {k: act.get(k) for k in ("home", "menu", "dashboard", "roles")}
    assert json.loads(json.dumps(now, sort_keys=True, ensure_ascii=False)) == json.loads(BASELINE.read_text(encoding="utf-8"))


def test_layout_files_are_schema_v1_and_validate():
    from app.catalog import ACTIVITIES_DIR

    files = sorted(ACTIVITIES_DIR.glob("*/layout.json"))
    assert {f.parent.name for f in files} >= {"retail", "general"}
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        assert data.pop("schema") == 1
        roles = data.pop("roles", {})
        # dashboard is a list of widget ids here (the schema's widget objects are the resolved form)
        assert all(isinstance(w, str) for w in data.get("dashboard", []))
        for body in [data, *roles.values()]:
            role_layout({k: body[k] for k in ("home", "menu") if k in body})


def test_layout_json_wins_over_activity_json_and_bad_schema_is_refused(tmp_path):
    from app.catalog import layout_of

    (tmp_path / "layout.json").write_text(json.dumps({"schema": 1, "menu": [], "extra": 1}))
    assert layout_of(tmp_path) == {"menu": []}
    (tmp_path / "layout.json").write_text(json.dumps({"schema": 2}))
    with pytest.raises(ValueError):
        layout_of(tmp_path)
    assert layout_of(tmp_path / "missing") == {}


# ---- step 5: an activity's default shell ----
def test_shell_defaults_to_classic_and_passes_valid_ids_only():
    from unittest.mock import patch
    from app.framework import variants

    real = variants.activity

    def with_shell(value):
        def fake(activity_id=None):
            return {**real(activity_id), "shell": value}
        return fake

    def resolved(activity="general"):
        return screens.resolve(None, activity, "owner", ALL_PERMS, [])

    assert resolved()["shell"] is None  # no activity sets one today: the look is unchanged
    assert resolved("retail")["shell"] is None
    with patch.object(variants, "activity", with_shell("rail")):
        assert resolved()["shell"] == "rail"
        assert resolved_screens(resolved()).shell == "rail"
    with patch.object(variants, "activity", with_shell("sparkly")):
        assert resolved()["shell"] is None  # unknown ids fall back to classic
