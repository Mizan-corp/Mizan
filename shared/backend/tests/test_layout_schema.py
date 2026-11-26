"""Layout schema v1 (migration step 3): the schema matches what the code produces today."""
import pytest
from pydantic import ValidationError

from app.framework import screens
from app.framework.layout_schema import ResolvedScreensV1, RoleLayoutV1, SCHEMA_VERSION, resolved_screens, role_layout

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
