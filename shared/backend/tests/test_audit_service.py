"""Audit service writes only columns the canonical model/migrations guarantee.

Fresh databases are provisioned from the model + migration suite, which carry
action_type / details / reason (never the legacy action / changes / note names
the raw SQL once targeted). These tests pin the repair: the INSERT must use
exactly the model-guaranteed columns, with the public log() arguments mapped
onto them, so every audited write (product deactivate, stock ops, ...) works
on any correctly provisioned database.
"""
import json
import re
import unittest
import uuid
from unittest.mock import AsyncMock

from app.platform.audit import service
from app.platform.audit.models import AuditLog
from app.platform.tenancy.context import current_tenant_id

A = uuid.UUID('a1b975ac-32ac-4813-9b35-e43069616c5f')
UID = uuid.UUID('b2c075bd-43bd-5924-a645-d53079717d60')
EID = uuid.UUID('c3d186ce-54ce-6a35-b756-e64180828e71')

MODEL_COLUMNS = {c.name for c in AuditLog.__table__.columns}


def insert_columns(sql):
    m = re.search(r'INSERT INTO audit_log\s*\(([^)]*)\)', sql)
    assert m, sql
    return {c.strip() for c in m.group(1).split(',')}


class Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.t = current_tenant_id.set(A)
        self.db = AsyncMock()

    async def asyncTearDown(self):
        current_tenant_id.reset(self.t)

    async def test_write_uses_only_model_guaranteed_columns(self):
        await service.log(self.db, 'product', 'deactivate', UID, 'Owner', EID, {'name': 'X'}, 'note')
        sql = self.db.execute.call_args.args[0].text
        cols = insert_columns(sql)
        assert cols <= MODEL_COLUMNS, (cols - MODEL_COLUMNS)
        assert {'tenant_id', 'entity_type', 'entity_id', 'action_type', 'user_id', 'user_name', 'details', 'reason'} == cols

    async def test_arguments_map_onto_canonical_columns(self):
        await service.log(self.db, 'product', 'deactivate', UID, 'Owner', EID, {'name': 'X'}, 'sp')
        params = self.db.execute.call_args.args[1]
        assert params['tid'] == A and params['etype'] == 'product' and params['eid'] == EID
        assert params['atype'] == 'deactivate' and params['uid'] == UID and params['uname'] == 'Owner'
        assert json.loads(params['det']) == {'name': 'X'} and params['why'] == 'sp'

    async def test_empty_changes_write_null_details_not_json_null(self):
        for changes in (None, {}):
            self.db.reset_mock()
            await service.log(self.db, 'product', 'update')
            params = self.db.execute.call_args.args[1]
            assert params['det'] is None and params['why'] is None

    async def test_without_tenant_writes_model_columns_only(self):
        current_tenant_id.reset(self.t)
        self.t = current_tenant_id.set(None)
        await service.log(self.db, 'product', 'deactivate', UID, 'Owner', EID)
        sql = self.db.execute.call_args.args[0].text
        cols = insert_columns(sql)
        assert cols <= MODEL_COLUMNS and 'tenant_id' not in cols
        params = self.db.execute.call_args.args[1]
        assert 'tid' not in params and params['atype'] == 'deactivate'

    def test_model_columns_match_migration_suite(self):
        from app.db import migrations
        src = open(migrations.__file__, encoding='utf8').read()
        for col in ('action_type', 'reason', 'details'):
            assert f'ADD COLUMN IF NOT EXISTS {col} text' in src, col


if __name__ == '__main__':
    unittest.main()
