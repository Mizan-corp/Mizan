"""Offline tests for the declared Help Desk source-adapter registry (sources.py):
both existing sources stay declared with their exact projection keys (the registry
must not change today's behavior), lazy model resolution works for installed
sources, and an absent source resolves to None (diagnostic, never a crash)."""

import unittest

from app.activities.general.modules.helpdesk.sources import SOURCES, SourceAdapter, load_model


class SourceRegistryTests(unittest.TestCase):
    def test_declares_exactly_the_two_existing_sources_with_unchanged_keys(self):
        declared = {a.id: a for a in SOURCES}
        self.assertEqual(set(declared), {"field_service", "real_estate"})
        self.assertEqual(declared["field_service"].keys,
                         ("id", "tenant_id", "order_ref", "issue_description", "status"))
        self.assertEqual(declared["real_estate"].keys,
                         ("id", "tenant_id", "ticket_ref", "description", "status"))

    def test_installed_sources_resolve_to_their_models(self):
        models = {a.id: load_model(a) for a in SOURCES}
        self.assertEqual(models["field_service"].__name__, "FsmWorkOrder")
        self.assertEqual(models["real_estate"].__name__, "RecMaintenanceTicket")

    def test_absent_source_module_resolves_to_none(self):
        missing = SourceAdapter("hotel_engineering", "app.activities.hotel.modules.pms.models:NoSuchModel", ())
        self.assertIsNone(load_model(missing))
        absent_pkg = SourceAdapter("equipment", "app.activities.general.modules.assets.models:AssetMaintenance", ())
        self.assertIsNone(load_model(absent_pkg))


if __name__ == "__main__":
    unittest.main()
