"""Offline tests for the module settings flow (framework/loader.py get_settings/save_settings
and setting_problem). A fake db session drives the queries, so no database is needed: the
merge, validation and partial-update semantics are what is under test (saving one key must
never drop the others; a key the manifest dropped is neither shown nor returned)."""

import json
import unittest

from app.framework.loader import ModuleRegistry, SettingsError, setting_problem


class _Result:
    def __init__(self, row):
        self._row = row

    def scalar_one_or_none(self):
        return self._row

    def scalar_one(self):
        assert self._row is not None, "scalar_one with no row (the INSERT should have created it)"
        return self._row


class _FakeDB:
    """Answers every execute() with the same row; save_settings INSERTs first (result unused),
    then selects the row FOR UPDATE, mutates row.value and commits."""

    def __init__(self, row=None):
        self.row = row
        self.commits = 0

    async def execute(self, stmt, params=None):
        return _Result(self.row)

    async def commit(self):
        self.commits += 1


class _Row:
    def __init__(self, value):
        self.value = value


def _registry() -> ModuleRegistry:
    reg = ModuleRegistry()
    reg.discover_modules()
    assert "helpdesk" in reg.get_all_manifests() or reg.get_manifest("helpdesk"), "helpdesk manifest missing"
    return reg


class SettingProblemTests(unittest.TestCase):
    def setUp(self):
        self.fields = {f.key: f for f in _registry().get_manifest("helpdesk").settings_schema}

    def test_unknown_key_rejected(self):
        self.assertIsNotNone(setting_problem(None, "nope", 1))

    def test_null_always_passes(self):
        self.assertIsNone(setting_problem(self.fields["service_catalog"], "service_catalog", None))

    def test_boolean_requires_bool(self):
        self.assertIsNone(setting_problem(self.fields["service_catalog"], "service_catalog", True))
        self.assertIsNotNone(setting_problem(self.fields["service_catalog"], "service_catalog", "true"))
        self.assertIsNotNone(setting_problem(self.fields["service_catalog"], "service_catalog", 1))


class GetSettingsTests(unittest.IsolatedAsyncioTestCase):
    async def test_defaults_when_nothing_saved(self):
        reg = _registry()
        data = await reg.get_settings(_FakeDB(), "helpdesk")
        manifest_defaults = {f.key: f.default for f in reg.get_manifest("helpdesk").settings_schema}
        self.assertEqual(data["values"], manifest_defaults)
        self.assertEqual(data["values"]["service_catalog"], False)
        self.assertEqual([f["key"] for f in data["schema"]],
                         ["service_catalog", "work_completion", "work_intake", "work_actuals"])

    async def test_saved_merges_over_defaults_and_unknown_keys_stay_hidden(self):
        row = _Row(json.dumps({"service_catalog": True, "dropped_key": "x"}))
        data = await _registry().get_settings(_FakeDB(row), "helpdesk")
        self.assertEqual(data["values"]["service_catalog"], True)
        self.assertNotIn("dropped_key", data["values"])

    async def test_unknown_module_raises(self):
        with self.assertRaises(KeyError):
            await _registry().get_settings(_FakeDB(), "no_such_module")


class SaveSettingsTests(unittest.IsolatedAsyncioTestCase):
    async def test_partial_update_keeps_other_saved_values(self):
        row = _Row(json.dumps({"service_catalog": True}))
        db = _FakeDB(row)
        updated = await _registry().save_settings(db, "helpdesk", {"work_completion": True})
        self.assertEqual(updated["values"]["service_catalog"], True)
        self.assertEqual(updated["values"]["work_completion"], True)
        self.assertEqual(json.loads(row.value), {"service_catalog": True, "work_completion": True})
        self.assertEqual(db.commits, 1)

    async def test_null_resets_key_to_default(self):
        row = _Row(json.dumps({"service_catalog": True}))
        updated = await _registry().save_settings(_FakeDB(row), "helpdesk", {"service_catalog": None})
        self.assertEqual(updated["values"]["service_catalog"], False)
        self.assertEqual(json.loads(row.value), {})

    async def test_invalid_value_rejected_before_any_write(self):
        row = _Row(json.dumps({"service_catalog": True}))
        db = _FakeDB(row)
        with self.assertRaises(SettingsError):
            await _registry().save_settings(db, "helpdesk", {"service_catalog": "yes"})
        self.assertEqual(row.value, json.dumps({"service_catalog": True}))
        self.assertEqual(db.commits, 0)

    async def test_unknown_key_rejected(self):
        with self.assertRaises(SettingsError):
            await _registry().save_settings(_FakeDB(), "helpdesk", {"nope": 1})


if __name__ == "__main__":
    unittest.main()
