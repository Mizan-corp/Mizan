"""Individually bound elements (v2 consent scope): the single-record reader.

Real models and real SQLAlchemy statements over a mocked session; not a live
database integration. Pins the consent-scope rule: only a v2 policy (written
under wording that names individually bound elements) unlocks scalar reads;
v0/v1 policies, revoked products, inactive products and malformed identities
all fail closed, and optional columns are selected only after the matching
field-level opt-in.
"""
import json
import unittest
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import app.models.registry  # noqa: F401
from app.activities.general.modules.inventory.storefront import cards as c
from app.framework.storefront_runtime import SourceContext, SourceUnavailable
from app.platform.tenancy.context import current_tenant_id

A = uuid.UUID('a1b975ac-32ac-4813-9b35-e43069616c5f')
P1 = uuid.UUID('b2c075bd-43bd-5924-a645-d53079717d60')
P2 = uuid.UUID('c3d186ce-54ce-6a35-b756-e64180828e71')


def policy(schema, products, show_price=False, show_image=False, currency=None):
    return json.dumps({'schema': schema, 'products': [str(p) for p in products],
                       'show_price': show_price, 'show_image': show_image, 'currency': currency})


def rows(*values):
    r = MagicMock()
    r.first.return_value = values
    return r


class ScopedItemConsentTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.t = current_tenant_id.set(A)
        self.ctx = SourceContext(A, 'en', frozenset({'inventory'}))
        self.db = AsyncMock()

    async def asyncTearDown(self):
        current_tenant_id.reset(self.t)

    async def test_public_audience_requires_v3_for_bound_elements(self):
        # v2 was recorded under previews-only wording: bound elements keep
        # working in previews but the public visitor audience needs the v3
        # wording that names public pages.
        public_ctx = SourceContext(A, 'en', frozenset({'inventory'}), audience='public')
        self.db.scalar.return_value = policy(c.SCHEMA_V2, [P1])
        self.assertIsNone(await c.element_consent(self.db, public_ctx))
        self.assertIsNotNone(await c.element_consent(self.db, self.ctx))
        self.db.scalar.return_value = policy(c.SCHEMA_V3, [P1])
        self.assertIsNotNone(await c.element_consent(self.db, public_ctx))

    async def test_public_audience_requires_v3_for_list_display_fields(self):
        public_ctx = SourceContext(A, 'en', frozenset({'inventory'}), audience='public')
        for schema in (c.SCHEMA_V1, c.SCHEMA_V2):
            self.db.scalar.return_value = policy(schema, [P1])
            self.assertIsNone(await c.display_consent(self.db, public_ctx), schema)
            self.assertIsNotNone(await c.display_consent(self.db, self.ctx), schema)
        self.db.scalar.return_value = policy(c.SCHEMA_V3, [P1])
        self.assertIsNotNone(await c.display_consent(self.db, public_ctx))

    async def test_v2_happy_path_name_only_selects_no_optional_columns(self):
        self.db.scalar.return_value = policy(c.SCHEMA_V2, [P1])
        self.db.execute.return_value = rows(P1, 'Fixture Card Widget')
        item = await c.read_scoped_item(self.db, self.ctx, str(P1), ('name',))
        self.assertEqual(item, {'name': 'Fixture Card Widget', 'price': None, 'image': None})
        stmt = self.db.execute.call_args.args[0]
        columns = {col.name for col in stmt.selected_columns}
        self.assertEqual(columns, {'id', 'name'})
        where = {getattr(getattr(w, 'left', None), 'name', None) for w in stmt._where_criteria}
        self.assertIn('is_active', where)

    async def test_v1_policy_never_unlocks_scalar_reads(self):
        # A v1 (cards+lists-worded) policy must not be read as element consent.
        self.db.scalar.return_value = policy(c.SCHEMA_V1, [P1])
        item = await c.read_scoped_item(self.db, self.ctx, str(P1), ('name',))
        self.assertIsNone(item)
        self.db.execute.assert_not_called()

    async def test_v0_policy_never_unlocks_scalar_reads(self):
        self.db.scalar.return_value = policy(c.SCHEMA, [P1])
        item = await c.read_scoped_item(self.db, self.ctx, str(P1), ('name',))
        self.assertIsNone(item)
        self.db.execute.assert_not_called()

    async def test_revoked_product_drops_out_without_a_product_query(self):
        self.db.scalar.return_value = policy(c.SCHEMA_V2, [P2])
        item = await c.read_scoped_item(self.db, self.ctx, str(P1), ('name',))
        self.assertIsNone(item)
        self.db.execute.assert_not_called()

    async def test_malformed_identity_fails_closed_before_any_read(self):
        for bad in ['not-a-uuid', str(P1).upper(), str(P1)[:-1] + 'x', 'x' * 65, 42]:
            db = AsyncMock()
            with self.assertRaises(SourceUnavailable):
                await c.read_scoped_item(db, self.ctx, bad, ('name',))
            db.scalar.assert_not_called()
            db.execute.assert_not_called()

    async def test_inactive_or_missing_product_resolves_to_none(self):
        self.db.scalar.return_value = policy(c.SCHEMA_V2, [P1])
        empty = MagicMock()
        empty.first.return_value = None
        self.db.execute.return_value = empty
        item = await c.read_scoped_item(self.db, self.ctx, str(P1), ('name',))
        self.assertIsNone(item)

    async def test_price_column_selected_only_after_price_opt_in(self):
        self.db.scalar.return_value = policy(c.SCHEMA_V2, [P1], show_price=True, currency='EGP')
        self.db.execute.return_value = rows(P1, 'Fixture Card Widget', Decimal('42.50'))
        item = await c.read_scoped_item(self.db, self.ctx, str(P1), ('name', 'price'))
        self.assertEqual(item['price'], {'schema': 'mizan.money.experimental.v0', 'amount': '42.50', 'currency': 'EGP'})
        columns = {col.name for col in self.db.execute.call_args.args[0].selected_columns}
        self.assertEqual(columns, {'id', 'name', 'retail_price'})

    async def test_requested_price_without_opt_in_stays_hidden(self):
        self.db.scalar.return_value = policy(c.SCHEMA_V2, [P1])
        self.db.execute.return_value = rows(P1, 'Fixture Card Widget')
        item = await c.read_scoped_item(self.db, self.ctx, str(P1), ('name', 'price'))
        self.assertIsNone(item['price'])
        columns = {col.name for col in self.db.execute.call_args.args[0].selected_columns}
        self.assertEqual(columns, {'id', 'name'})

    async def test_image_requires_workspace_file_provenance(self):
        url = '/uploads/t/%s/product_image/img.png' % A
        self.db.scalar.side_effect = [policy(c.SCHEMA_V2, [P1], show_image=True), uuid.uuid4()]
        self.db.execute.return_value = rows(P1, 'Fixture Card Widget', url)
        item = await c.read_scoped_item(self.db, self.ctx, str(P1), ('name', 'image'))
        self.assertEqual(item['image']['src'], url)
        self.assertEqual(item['image']['alt'], 'Fixture Card Widget')

    async def test_image_without_provenance_fails_closed(self):
        self.db.scalar.side_effect = [policy(c.SCHEMA_V2, [P1], show_image=True), None]
        self.db.execute.return_value = rows(P1, 'Fixture Card Widget', '/uploads/t/%s/product_image/img.png' % A)
        with self.assertRaises(SourceUnavailable):
            await c.read_scoped_item(self.db, self.ctx, str(P1), ('name', 'image'))

    async def test_invalid_bound_field_selection_fails_closed(self):
        for fields in [(), ('cost',), ('name', 'name', 'name', 'name'), 'name']:
            with self.assertRaises(SourceUnavailable):
                await c.read_scoped_item(self.db, self.ctx, str(P1), fields)

    async def test_invalid_record_name_fails_closed(self):
        self.db.scalar.return_value = policy(c.SCHEMA_V2, [P1])
        self.db.execute.return_value = rows(P1, '   ')
        with self.assertRaises(SourceUnavailable):
            await c.read_scoped_item(self.db, self.ctx, str(P1), ('name',))


if __name__ == '__main__':
    unittest.main()
