"""Real-model checks that the card consent writer stamps schema v1.

Covers what the read-side checks cannot: PUT /cards must write
mizan.inventory-website-cards.experimental.v1 on both first save and re-save
over an existing v0 row (consent upgrade happens only through the v1-worded
UI). DB is mocked; the stored StoreSetting payload is parsed and asserted.
"""
import os, sys, json, unittest
from pathlib import Path
from uuid import UUID
from unittest.mock import AsyncMock, patch
os.environ.setdefault('DATABASE_URL', 'postgresql+asyncpg://unused:unused@127.0.0.1/unused')
os.environ.setdefault('SECRET_KEY', 'offline-test-not-used-for-signing')
os.environ['VERCEL'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.models.registry import load_all_models
load_all_models()
from app.activities.general.modules.inventory.storefront import cards, router
from app.platform.tenancy.context import current_tenant_id

A = UUID('00000000-0000-4000-8000-000000000001')


def data(**patch):
    payload = {'expected_token': '', 'products': [], 'show_price': False,
               'show_image': False, 'currency': None}
    payload.update(patch)
    return router.CardPublicationIn(**payload)


class WriterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.t = current_tenant_id.set(A)
        self.db = AsyncMock()

    async def asyncTearDown(self):
        current_tenant_id.reset(self.t)

    async def _put(self, raw):
        # Bypass only the read chain; the writer logic under test runs for real.
        row = None if raw is None else type('Row', (), {'value': raw})()
        with patch.object(router, 'card_read', new=AsyncMock(return_value=(row, raw))):
            return await router.put_cards(data(expected_token=router.token(raw)), db=self.db)

    async def test_first_save_stamps_v2(self):
        await self._put(None)
        added = self.db.add.call_args.args[0]
        stored = json.loads(added.value)
        self.assertEqual(stored['schema'], cards.SCHEMA_V2)
        self.assertEqual(stored['products'], [])
        self.assertEqual(stored['show_price'], False)
        self.db.commit.assert_awaited()

    async def test_resave_over_v0_upgrades_to_v2(self):
        v0 = json.dumps({'schema': cards.SCHEMA, 'products': [], 'show_price': False,
                         'show_image': False, 'currency': None}, sort_keys=True)
        await self._put(v0)
        self.db.add.assert_not_called()  # existing row updated in place
        # The in-place update target is the row object returned by card_read;
        # verify via a second pass capturing it directly.
        row = type('Row', (), {'value': v0})()
        with patch.object(router, 'card_read', new=AsyncMock(return_value=(row, v0))):
            await router.put_cards(data(expected_token=router.token(v0)), db=AsyncMock())
        self.assertEqual(json.loads(row.value)['schema'], cards.SCHEMA_V2)

    async def test_stale_token_refused_before_any_write(self):
        with patch.object(router, 'card_read', new=AsyncMock(return_value=(None, None))):
            with self.assertRaises(Exception) as cm:
                await router.put_cards(data(expected_token='wrong'), db=self.db)
        self.assertEqual(getattr(cm.exception, 'status_code', None), 409)
        self.db.add.assert_not_called()
        self.db.commit.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
