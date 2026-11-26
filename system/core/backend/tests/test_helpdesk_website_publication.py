"""Offline tests for the Help Desk website publication surface
(app/activities/general/modules/helpdesk/storefront/): the allowlist parser is
fail-closed and exact-key, the collection provider reads only active offerings in
the caller's workspace and projects id+name only, and the settings router guards
concurrency, module activation and selection validity."""

import json
import os
import sys
import unittest
from pathlib import Path
from uuid import UUID, uuid4

os.environ.setdefault('DATABASE_URL', 'postgresql+asyncpg://unused:unused@127.0.0.1/unused')
os.environ.setdefault('SECRET_KEY', 'offline-test-not-used-for-signing')
os.environ['VERCEL'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.registry import load_all_models

load_all_models()

from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException
from app.framework.storefront_collections import CollectionRuntime
from app.framework.storefront_runtime import SourceContext, SourceUnavailable
from app.platform.tenancy.context import current_tenant_id

from app.activities.general.modules.helpdesk.storefront import provider as prov
from app.activities.general.modules.helpdesk.storefront import router as rtr

A = UUID('00000000-0000-4000-8000-000000000001')
B = UUID('00000000-0000-4000-8000-000000000002')
Z = UUID('00000000-0000-4000-8000-000000000003')


class PublicationIdsTests(unittest.TestCase):
    def test_default_no_exposure(self):
        self.assertEqual(prov.publication_ids(None), ())

    def test_exact_keys_and_schema_fail_closed(self):
        for raw in ['{}', 'null',
                    json.dumps({'schema': prov.SCHEMA, 'offerings': [], 'extra': 1}),
                    json.dumps({'schema': 'other', 'offerings': []}),
                    json.dumps({'schema': prov.SCHEMA})]:
            with self.assertRaises(SourceUnavailable):
                prov.publication_ids(raw)

    def test_duplicates_bad_uuid_and_over_limit_rejected(self):
        for ids in [[str(A), str(A)], ['bad'], [str(A)] * 201, [42]]:
            with self.assertRaises(SourceUnavailable):
                prov.publication_ids(json.dumps({'schema': prov.SCHEMA, 'offerings': ids}))

    def test_valid_selection_roundtrips(self):
        self.assertEqual(prov.publication_ids(json.dumps({'schema': prov.SCHEMA, 'offerings': [str(A)]})), (A,))


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_inactive_module_and_tenant_mismatch_before_query(self):
        db = AsyncMock()
        runtime = CollectionRuntime(prov.helpdesk_providers(db))
        token = current_tenant_id.set(A)
        try:
            for ctx in [SourceContext(A, 'en', frozenset()), SourceContext(Z, 'en', frozenset({'helpdesk'}))]:
                with self.assertRaises(SourceUnavailable):
                    await runtime.items(ctx, 'helpdesk', 'services', 8)
            db.scalar.assert_not_awaited()
            db.execute.assert_not_awaited()
        finally:
            current_tenant_id.reset(token)

    async def test_empty_selection_queries_no_rows(self):
        db = AsyncMock()
        db.scalar.return_value = None
        runtime = CollectionRuntime(prov.helpdesk_providers(db))
        token = current_tenant_id.set(A)
        try:
            self.assertEqual(await runtime.items(SourceContext(A, 'en', frozenset({'helpdesk'})), 'helpdesk', 'services', 8), ())
            db.execute.assert_not_awaited()
        finally:
            current_tenant_id.reset(token)

    async def test_query_scoped_tenant_active_and_projects_names_only(self):
        db = AsyncMock()
        db.scalar.return_value = json.dumps({'schema': prov.SCHEMA, 'offerings': [str(A)]})
        result = MagicMock()
        result.all.return_value = [(A, 'صيانة تكييف')]
        db.execute.return_value = result
        runtime = CollectionRuntime(prov.helpdesk_providers(db))
        token = current_tenant_id.set(A)
        try:
            items = await runtime.items(SourceContext(A, 'en', frozenset({'helpdesk'})), 'helpdesk', 'services', 8)
            self.assertEqual(dict(items[0].values), {'name': 'صيانة تكييف', 'description': None, 'starting_price': None})
            sql = str(db.execute.call_args.args[0])
            self.assertIn('helpdesk_offerings.tenant_id', sql)
            self.assertIn('helpdesk_offerings.is_active IS true', sql)
            for forbidden in ['description', 'starting_amount', 'currency']:
                self.assertNotIn(forbidden, sql)
        finally:
            current_tenant_id.reset(token)

    async def test_oversize_name_fails_closed(self):
        db = AsyncMock()
        db.scalar.return_value = json.dumps({'schema': prov.SCHEMA, 'offerings': [str(A)]})
        result = MagicMock()
        result.all.return_value = [(A, 'x' * 201)]
        db.execute.return_value = result
        runtime = CollectionRuntime(prov.helpdesk_providers(db))
        token = current_tenant_id.set(A)
        try:
            with self.assertRaises(SourceUnavailable):
                await runtime.items(SourceContext(A, 'en', frozenset({'helpdesk'})), 'helpdesk', 'services', 8)
        finally:
            current_tenant_id.reset(token)


def _db_for_router(stored_raw, found_ids=()):
    """AsyncMock db: scalar() returns the stored settings row, execute() returns
    the tenant lock then the offering-id lookup."""
    db = AsyncMock()
    row = MagicMock(value=stored_raw) if stored_raw is not None else None
    db.scalar.return_value = row
    lock_result = MagicMock()
    ids_result = MagicMock()
    ids_result.scalars.return_value = list(found_ids)
    db.execute.side_effect = [lock_result, ids_result]
    return db, row


class RouterTests(unittest.IsolatedAsyncioTestCase):
    async def _call_put(self, db, offerings, expected):
        tid = uuid4()
        token = current_tenant_id.set(tid)
        try:
            data = rtr.PublicationIn(expected_token=expected, consent_version=prov.SCHEMA_V1, offerings=offerings, show_description=False, show_starting_price=False)
            # read() inside the endpoint checks activation; patch it out — the
            # activation guard itself is covered by the provider tests above.
            import app.activities.general.modules.helpdesk.storefront.router as _r
            orig = _r.get_active_modules
            _r.get_active_modules = AsyncMock(return_value={'helpdesk'})
            try:
                return await rtr.put_publication(data, db)
            finally:
                _r.get_active_modules = orig
        finally:
            current_tenant_id.reset(token)

    async def test_token_mismatch_409_and_no_write(self):
        stored = json.dumps({'schema': prov.SCHEMA, 'offerings': []})
        db, row = _db_for_router(stored)
        tid = uuid4()
        token = current_tenant_id.set(tid)
        try:
            import app.activities.general.modules.helpdesk.storefront.router as _r
            orig = _r.get_active_modules
            _r.get_active_modules = AsyncMock(return_value={'helpdesk'})
            try:
                with self.assertRaises(HTTPException) as ctx:
                    await rtr.put_publication(rtr.PublicationIn(expected_token='stale', consent_version=prov.SCHEMA_V1, offerings=[], show_description=False, show_starting_price=False), db)
            finally:
                _r.get_active_modules = orig
            self.assertEqual(ctx.exception.status_code, 409)
            self.assertEqual(row.value, stored)
            db.commit.assert_not_awaited()
        finally:
            current_tenant_id.reset(token)

    async def test_unavailable_offering_422_and_no_write(self):
        db, row = _db_for_router(None, found_ids=())  # offering A not found active
        tid = uuid4()
        token = current_tenant_id.set(tid)
        try:
            import app.activities.general.modules.helpdesk.storefront.router as _r
            orig = _r.get_active_modules
            _r.get_active_modules = AsyncMock(return_value={'helpdesk'})
            try:
                expected = rtr.token(None)
                with self.assertRaises(HTTPException) as ctx:
                    await rtr.put_publication(rtr.PublicationIn(expected_token=expected, consent_version=prov.SCHEMA_V1, offerings=[A], show_description=False, show_starting_price=False), db)
            finally:
                _r.get_active_modules = orig
            self.assertEqual(ctx.exception.status_code, 422)
            db.commit.assert_not_awaited()
        finally:
            current_tenant_id.reset(token)

    async def test_happy_path_stamps_schema_and_returns_new_token(self):
        db, row = _db_for_router(None, found_ids=[A])
        tid = uuid4()
        token = current_tenant_id.set(tid)
        try:
            import app.activities.general.modules.helpdesk.storefront.router as _r
            orig = _r.get_active_modules
            _r.get_active_modules = AsyncMock(return_value={'helpdesk'})
            try:
                expected = rtr.token(None)
                out = await rtr.put_publication(rtr.PublicationIn(expected_token=expected, consent_version=prov.SCHEMA_V1, offerings=[A], show_description=False, show_starting_price=False), db)
            finally:
                _r.get_active_modules = orig
            self.assertEqual(out['value'], {'offerings': [str(A)], 'show_description': False, 'show_starting_price': False, 'schema': prov.SCHEMA_V1})
            added = db.add.call_args.args[0]
            saved = json.loads(added.value)
            self.assertEqual(saved, {'schema': prov.SCHEMA_V1, 'offerings': [str(A)], 'show_description': False, 'show_starting_price': False})
            db.commit.assert_awaited_once()
        finally:
            current_tenant_id.reset(token)

    async def test_inactive_module_422(self):
        db = AsyncMock()
        tid = uuid4()
        token = current_tenant_id.set(tid)
        try:
            import app.activities.general.modules.helpdesk.storefront.router as _r
            orig = _r.get_active_modules
            _r.get_active_modules = AsyncMock(return_value=set())
            try:
                with self.assertRaises(HTTPException) as ctx:
                    await rtr.get_publication(db)
            finally:
                _r.get_active_modules = orig
            self.assertEqual(ctx.exception.status_code, 422)
        finally:
            current_tenant_id.reset(token)



class V1ConsentTests(unittest.TestCase):
    def test_v0_rows_read_names_only(self):
        policy = prov.service_policy(json.dumps({'schema': prov.SCHEMA, 'offerings': [str(A)]}))
        self.assertEqual(policy['schema'], prov.SCHEMA)
        self.assertFalse(policy['show_description'])
        self.assertFalse(policy['show_starting_price'])

    def test_v1_exact_keys_and_strict_bools_fail_closed(self):
        base = {'schema': prov.SCHEMA_V1, 'offerings': [],
                'show_description': True, 'show_starting_price': False}
        bad = [json.dumps({**base, 'extra': 1}),
               json.dumps({k: v for k, v in base.items() if k != 'show_description'}),
               json.dumps({**base, 'show_description': 'yes'}),
               json.dumps({**base, 'show_starting_price': 1}),
               json.dumps({**base, 'schema': prov.SCHEMA})]  # flags under v0 shape
        for raw in bad:
            with self.assertRaises(SourceUnavailable):
                prov.service_policy(raw)

    def test_v1_flags_roundtrip(self):
        policy = prov.service_policy(json.dumps({'schema': prov.SCHEMA_V1, 'offerings': [str(A)],
                                                 'show_description': True, 'show_starting_price': True}))
        self.assertEqual(policy['offerings'], (A,))
        self.assertTrue(policy['show_description'])
        self.assertTrue(policy['show_starting_price'])


class V1ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def _run(self, stored, rows):
        db = AsyncMock()
        db.scalar.return_value = stored
        result = MagicMock()
        result.all.return_value = rows
        db.execute.return_value = result
        runtime = CollectionRuntime(prov.helpdesk_providers(db))
        token = current_tenant_id.set(A)
        try:
            return await runtime.items(SourceContext(A, 'en', frozenset({'helpdesk'})), 'helpdesk', 'services', 8), db
        finally:
            current_tenant_id.reset(token)

    async def test_v0_rows_never_select_richer_columns(self):
        stored = json.dumps({'schema': prov.SCHEMA, 'offerings': [str(A)]})
        items, db = await self._run(stored, [(A, 'صيانة تكييف')])
        sql = str(db.execute.call_args.args[0])
        for forbidden in ['description', 'starting_amount', 'currency']:
            self.assertNotIn(forbidden, sql)
        self.assertIsNone(items[0].values['description'])
        self.assertIsNone(items[0].values['starting_price'])

    async def test_v1_unchecked_fields_never_selected(self):
        stored = json.dumps({'schema': prov.SCHEMA_V1, 'offerings': [str(A)],
                             'show_description': False, 'show_starting_price': False})
        items, db = await self._run(stored, [(A, 'تنظيف')])
        sql = str(db.execute.call_args.args[0])
        for forbidden in ['description', 'starting_amount', 'currency']:
            self.assertNotIn(forbidden, sql)

    async def test_v1_checked_fields_selected_and_projected(self):
        from decimal import Decimal
        stored = json.dumps({'schema': prov.SCHEMA_V1, 'offerings': [str(A)],
                             'show_description': True, 'show_starting_price': True})
        items, db = await self._run(stored, [(A, 'دعم فني', 'دعم عن بعد', Decimal('1500.00'), 'EGP')])
        sql = str(db.execute.call_args.args[0])
        for col in ['description', 'starting_amount', 'currency']:
            self.assertIn(col, sql)
        self.assertEqual(dict(items[0].values), {'name': 'دعم فني', 'description': 'دعم عن بعد',
                                                 'starting_price': '1500.00 EGP'})

    async def test_over_bound_description_fails_closed(self):
        from decimal import Decimal
        stored = json.dumps({'schema': prov.SCHEMA_V1, 'offerings': [str(A)],
                             'show_description': True, 'show_starting_price': True})
        from app.framework.storefront_collections import ProjectionInvalid
        with self.assertRaises((SourceUnavailable, ProjectionInvalid)):
            await self._run(stored, [(A, 'دعم فني', 'x' * 201, Decimal('1.00'), 'EGP')])


class V1RouterTests(unittest.IsolatedAsyncioTestCase):
    async def test_stale_consent_version_409_no_write(self):
        stored = json.dumps({'schema': prov.SCHEMA, 'offerings': []})
        db, row = _db_for_router(stored)
        tid = uuid4()
        token = current_tenant_id.set(tid)
        try:
            import app.activities.general.modules.helpdesk.storefront.router as _r
            orig = _r.get_active_modules
            _r.get_active_modules = AsyncMock(return_value={'helpdesk'})
            try:
                with self.assertRaises(HTTPException) as ctx:
                    await rtr.put_publication(rtr.PublicationIn(
                        expected_token=rtr.token(stored), consent_version=prov.SCHEMA,
                        offerings=[], show_description=False, show_starting_price=False), db)
            finally:
                _r.get_active_modules = orig
            self.assertEqual(ctx.exception.status_code, 409)
            self.assertEqual(row.value, stored)
            db.commit.assert_not_awaited()
        finally:
            current_tenant_id.reset(token)

    def test_non_bool_flags_refused_by_model(self):
        with self.assertRaises(Exception):
            rtr.PublicationIn(expected_token='x', consent_version=prov.SCHEMA_V1,
                              offerings=[], show_description='yes', show_starting_price=False)
