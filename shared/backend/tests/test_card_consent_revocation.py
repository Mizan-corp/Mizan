"""Proposed revocation semantics (pending owner decision, prepared only).

A section's explicit product selection is filtered by the current website
card consent: revoked products drop out of the rendered rows, still-consented
selections keep rendering, and an empty remainder hides the card row through
the existing zero-row projection path. Protective errors are unchanged:
tenant/module violations, malformed selections, invalid policy shapes and
unavailable sources still fail closed with SourceUnavailable.
"""
import json
import unittest
import uuid
from sqlalchemy import BindParameter
from unittest.mock import AsyncMock, MagicMock

import app.models.registry  # noqa: F401
from app.activities.general.modules.inventory.storefront import cards as c
from app.framework.storefront_runtime import SourceContext, SourceUnavailable
from app.platform.tenancy.context import current_tenant_id

A = uuid.UUID('a1b975ac-32ac-4813-9b35-e43069616c5f')
P1 = uuid.UUID('b2c075bd-43bd-5924-a645-d53079717d60')
P2 = uuid.UUID('c3d186ce-54ce-6a35-b756-e64180828e71')


def policy(products):
    return json.dumps({'schema': c.SCHEMA, 'products': [str(p) for p in products], 'show_price': False, 'show_image': False, 'currency': None})


class Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.t = current_tenant_id.set(A)
        self.ctx = SourceContext(A, 'en', frozenset({'inventory'}))
        self.db = AsyncMock()

    async def asyncTearDown(self):
        current_tenant_id.reset(self.t)

    async def test_partially_revoked_selection_keeps_consented_products(self):
        self.db.scalar.return_value = policy([P1])
        r = MagicMock(); r.all.return_value = [(P1, 'Kept name')]; self.db.execute.return_value = r
        rows = await c.read_cards(self.db, self.ctx, 6, products=[str(P1), str(P2)])
        self.assertEqual(rows, [{'item_key': str(P1), 'name': 'Kept name', 'price': None, 'image': None}])
        stmt = self.db.execute.call_args.args[0]
        in_values = [c.right.value for c in stmt._where_criteria
                     if getattr(getattr(c, 'left', None), 'name', None) == 'id' and isinstance(getattr(c, 'right', None), BindParameter)]
        assert in_values == [[P1]], in_values

    async def test_fully_revoked_selection_returns_no_rows_without_query(self):
        self.db.scalar.return_value = policy([P2])
        self.assertEqual(await c.read_cards(self.db, self.ctx, 6, products=[str(P1)]), [])
        self.db.execute.assert_not_awaited()

    async def test_protective_errors_still_fail_closed(self):
        self.db.scalar.return_value = policy([P1])
        for bad in (['bad-uuid'], [str(P1), str(P1)], 'not-a-list', [str(P1)] * 7, [42]):
            with self.assertRaises(SourceUnavailable):
                await c.read_cards(self.db, self.ctx, 6, products=bad)
        with self.assertRaises(SourceUnavailable):
            await c.read_cards(self.db, SourceContext(uuid.uuid4(), 'en', frozenset({'inventory'})), 6, products=[str(P1)])
        with self.assertRaises(SourceUnavailable):
            await c.read_cards(self.db, SourceContext(A, 'en', frozenset()), 6, products=[str(P1)])
        self.db.execute.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
