"""Contract-only tests. No DB, endpoint, migration, permission or UI claim."""
import importlib.util
from dataclasses import asdict
from pathlib import Path
import sys
import unittest

spec = importlib.util.spec_from_file_location(
    "helpdesk_contract_under_test",
    Path(__file__).resolve().parents[1] / "app/framework/helpdesk_contract.py",
)
c = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = c
spec.loader.exec_module(c)


class FeatureContractTests(unittest.TestCase):
    def test_module_level_default_and_enabled_state(self):
        self.assertEqual(c.feature_state(None), {"service_catalog": False})
        saved = {"service_catalog": True}
        # No activity or variation is an input. Both calls leave source intact.
        self.assertEqual(c.feature_state(saved), c.feature_state(saved))
        self.assertEqual(saved, {"service_catalog": True})

    def test_partial_update_and_disable_preserve_original(self):
        saved = {"service_catalog": True}
        self.assertEqual(c.update_features(saved, {}), saved)
        self.assertEqual(c.update_features(saved, {"service_catalog": False}), {"service_catalog": False})
        self.assertTrue(saved["service_catalog"])

    def test_bad_partial_update_fails_without_mutation(self):
        saved = {"service_catalog": True}
        for patch in [None, [], {"unknown": False}, {"service_catalog": 1}]:
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                c.update_features(saved, patch)
        self.assertEqual(saved, {"service_catalog": True})

    def test_strict_boolean(self):
        for value in [1, 0, "true", "false", None, [], {}]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                c.feature_state({"service_catalog": value})

    def test_unknown_or_malformed_state(self):
        for saved in [{"field_only_feature": True}, [], "standard", 1]:
            with self.subTest(saved=saved), self.assertRaises(ValueError):
                c.feature_state(saved)


class SourceProjectionTests(unittest.TestCase):
    def setUp(self):
        self.row = {"id": "legacy-17", "tenant_id": "tenant-a", "ticket_ref": "REC-3",
                    "description": "AC failed", "status": "assigned", "unit_id": "unit-9",
                    "reported_by": "private name", "cost_egp": 43.5,
                    "private_notes": "must not appear"}

    def test_property_identity_status_and_allowlist(self):
        original = dict(self.row)
        item = c.source_work_summary("real_estate", self.row, tenant_id="tenant-a")
        self.assertEqual(item.source_id, "legacy-17")
        self.assertEqual(item.source_table, "rec_maintenance_tickets")
        self.assertEqual(item.source_status, "assigned")
        self.assertEqual(self.row, original)
        self.assertEqual(set(asdict(item)), {"contract_version", "source_module", "source_table",
                                            "source_id", "tenant_id", "reference", "description", "source_status"})
        self.assertNotIn("private name", repr(item))

    def test_fsm_retains_native_status(self):
        row = {"id": "wo-4", "tenant_id": "tenant-a", "order_ref": "WO-4",
               "issue_description": "No cooling", "status": "parts_needed"}
        item = c.source_work_summary("field_service", row, tenant_id="tenant-a")
        self.assertEqual(item.source_status, "parts_needed")
        self.assertEqual(item.source_table, "fsm_work_orders")

    def test_unknown_status_preserved_not_reinterpreted(self):
        self.row["status"] = "legacy_pending_vendor"
        self.assertEqual(c.source_work_summary("real_estate", self.row, tenant_id="tenant-a").source_status,
                         "legacy_pending_vendor")

    def test_tenant_mismatch_or_missing_fails(self):
        for tenant in ["tenant-b", "", None]:
            with self.subTest(tenant=tenant), self.assertRaises(ValueError):
                c.source_work_summary("real_estate", self.row, tenant_id=tenant)
        del self.row["tenant_id"]
        with self.assertRaises(ValueError):
            c.source_work_summary("real_estate", self.row, tenant_id="tenant-a")

    def test_unknown_source_is_not_inferred(self):
        for source in ["salon", "consulting", "hse", "kitchen"]:
            with self.subTest(source=source), self.assertRaises(ValueError):
                c.source_work_summary(source, self.row, tenant_id="tenant-a")

    def test_invalid_required_fields(self):
        for key in ["id", "ticket_ref", "description", "status"]:
            for value in [None, "", " ", 123]:
                row = {**self.row, key: value}
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    c.source_work_summary("real_estate", row, tenant_id="tenant-a")


if __name__ == "__main__":
    unittest.main()
