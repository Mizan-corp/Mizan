"""Atomic additive actuals migration. Fail closed on an unknown existing table.

Services create_all their models before manage.py migrate runs, so an existing
untracked table is adopted only when it matches the tracked contract exactly:
columns (name, type, nullability, defaults), primary key, tenant foreign key
with ON DELETE CASCADE, the source-revision unique constraint and the check
constraints, with nothing unexpected. The idempotent DDL then brings RLS,
grants and the append-only triggers to the tracked state, and no broader
policy or trigger may survive.
"""
from pathlib import Path
from sqlalchemy import text
from app.db.migrations import split_statements

EXPECTED_COLUMNS = {
    ('id', 'uuid', False, None),
    ('tenant_id', 'uuid', False, None),
    ('source_module', 'character varying', False, None),
    ('source_id', 'character varying', False, None),
    ('revision', 'integer', False, None),
    ('user_id', 'uuid', False, None),
    ('fingerprint', 'character varying', False, None),
    ('payload', 'jsonb', False, None),
    ('resource_labels', 'jsonb', False, None),
    ('created_at', 'timestamp with time zone', False, True),
}
EXPECTED_CHECK_MARKERS = ('source_module', 'revision > 0')
EXPECTED_CHECK_COUNT = 2
EXPECTED_TRIGGERS = {'helpdesk_actuals_no_rewrite', 'helpdesk_actuals_no_truncate'}


async def _verify_contract(db):
    rows = (await db.execute(text(
        "SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='helpdesk_execution_revisions'"))).all()
    found = {(r.column_name, r.data_type, r.is_nullable == 'YES', (r.column_default is not None) or None)
             for r in rows}
    if found != EXPECTED_COLUMNS:
        raise RuntimeError('Actuals table columns do not match the tracked contract, inspect instead of assuming migration success')
    pk = await db.scalar(text(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conrelid='public.helpdesk_execution_revisions'::regclass AND contype='p'"))
    if pk != 'PRIMARY KEY (id)':
        raise RuntimeError('Actuals primary key does not match the tracked contract')
    fk = await db.scalar(text(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conrelid='public.helpdesk_execution_revisions'::regclass AND contype='f'"))
    if not fk or 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)' not in fk or 'ON DELETE CASCADE' not in fk:
        raise RuntimeError('Actuals tenant foreign key does not match the tracked contract')
    uq = await db.scalar(text(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conrelid='public.helpdesk_execution_revisions'::regclass AND contype='u'"))
    if uq != 'UNIQUE (tenant_id, source_module, source_id, revision)':
        raise RuntimeError('Actuals unique constraint does not match the tracked contract')
    checks = [d for d in (await db.scalars(text(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conrelid='public.helpdesk_execution_revisions'::regclass AND contype='c'"))).all()]
    if len(checks) != EXPECTED_CHECK_COUNT or not all(
            any(marker in d for d in checks) for marker in EXPECTED_CHECK_MARKERS):
        raise RuntimeError('Actuals check constraints do not match the tracked contract')


async def migrate(db):
    sql='\n'.join(x for x in (Path(__file__).parent/'migrations/002_execution_actuals.sql').read_text().splitlines() if not x.lstrip().startswith('--'))
    async with db.begin_nested():
        if await db.scalar(text("SELECT to_regclass('public.helpdesk_execution_revisions')")):
            await _verify_contract(db)
        for statement in split_statements(sql):await db.execute(text(statement))
        await _verify_contract(db)
        flags=(await db.execute(text("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='public.helpdesk_execution_revisions'::regclass"))).one()
        if not all(flags):raise RuntimeError('Forced RLS required')
        policies = set((await db.scalars(text(
            "SELECT polname FROM pg_policy WHERE polrelid='public.helpdesk_execution_revisions'::regclass"))).all())
        if policies != {'tenant_isolation'}:raise RuntimeError('Actuals policies are broader than the tracked contract')
        triggers = set((await db.scalars(text(
            "SELECT tgname FROM pg_trigger WHERE tgrelid='public.helpdesk_execution_revisions'::regclass AND NOT tgisinternal"))).all())
        if triggers != EXPECTED_TRIGGERS:raise RuntimeError('Actuals append-only triggers do not match the tracked contract')
        if not await db.scalar(text("SELECT has_table_privilege('mizan_app','helpdesk_execution_revisions','SELECT,INSERT')")):raise RuntimeError('Actuals read/append grants missing')
        if await db.scalar(text("SELECT has_table_privilege('mizan_app','helpdesk_execution_revisions','UPDATE') OR has_table_privilege('mizan_app','helpdesk_execution_revisions','DELETE')")):raise RuntimeError('Actuals history must be append-only for application role')
