"""Atomic additive actuals migration. Fail closed on an unknown existing table.

Services create_all their models before manage.py migrate runs, so an existing
untracked table is adopted only on an exact column match (name + type); any
other schema still raises. The idempotent DDL then brings RLS, grants and the
append-only triggers to the tracked state, verified below on every run.
"""
from pathlib import Path
from sqlalchemy import text
from app.db.migrations import split_statements

EXPECTED_COLUMNS = {
    ('id', 'uuid'),
    ('tenant_id', 'uuid'),
    ('source_module', 'character varying'),
    ('source_id', 'character varying'),
    ('revision', 'integer'),
    ('user_id', 'uuid'),
    ('fingerprint', 'character varying'),
    ('payload', 'jsonb'),
    ('resource_labels', 'jsonb'),
    ('created_at', 'timestamp with time zone'),
}


async def migrate(db):
    sql='\n'.join(x for x in (Path(__file__).parent/'migrations/002_execution_actuals.sql').read_text().splitlines() if not x.lstrip().startswith('--'))
    async with db.begin_nested():
        if await db.scalar(text("SELECT to_regclass('public.helpdesk_execution_revisions')")):
            rows = (await db.execute(text(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='helpdesk_execution_revisions'"))).all()
            if {(r.column_name, r.data_type) for r in rows} != EXPECTED_COLUMNS:
                raise RuntimeError('Actuals table exists with an unexpected schema, inspect instead of assuming migration success')
        for statement in split_statements(sql):await db.execute(text(statement))
        flags=(await db.execute(text("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='public.helpdesk_execution_revisions'::regclass"))).one()
        if not all(flags):raise RuntimeError('Forced RLS required')
        if not await db.scalar(text("SELECT has_table_privilege('mizan_app','helpdesk_execution_revisions','SELECT,INSERT')")):raise RuntimeError('Actuals read/append grants missing')
        if await db.scalar(text("SELECT has_table_privilege('mizan_app','helpdesk_execution_revisions','UPDATE') OR has_table_privilege('mizan_app','helpdesk_execution_revisions','DELETE')")):raise RuntimeError('Actuals history must be append-only for application role')
