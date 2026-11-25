"""Atomic additive Help Desk migration for the existing Python-migration route.

No catch-and-mark-applied behavior. Any DDL, RLS or privilege failure raises and
rolls this savepoint back; the caller may record migration success only on return.

Boot order: services create_all their models before manage.py migrate runs, so on
a fresh stack the table can already exist untracked. An existing table is adopted
only when its columns match the expected schema exactly (name + type); anything
else still raises for manual inspection. After adoption the same idempotent DDL
brings indexes, RLS, policy and grants to the tracked state and every invariant
is verified below, so an adopted table is never assumed migrated.
"""
from pathlib import Path
from sqlalchemy import text
from app.db.migrations import split_statements

EXPECTED_COLUMNS = {
    ('id', 'uuid'),
    ('tenant_id', 'uuid'),
    ('name', 'character varying'),
    ('description', 'text'),
    ('starting_amount', 'numeric'),
    ('currency', 'character varying'),
    ('is_active', 'boolean'),
    ('created_at', 'timestamp with time zone'),
    ('updated_at', 'timestamp with time zone'),
}


async def migrate(db):
    sql = '\n'.join(line for line in (Path(__file__).parent/'migrations/001_offerings.sql').read_text().splitlines()
                    if not line.lstrip().startswith('--'))
    async with db.begin_nested():
        exists = await db.scalar(text("SELECT to_regclass('public.helpdesk_offerings')"))
        if exists:
            rows = (await db.execute(text(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='helpdesk_offerings'"))).all()
            if {(r.column_name, r.data_type) for r in rows} != EXPECTED_COLUMNS:
                # Do not reinterpret a pre-existing unknown schema as successfully migrated.
                raise RuntimeError('Help Desk table already exists with an unexpected schema; inspect before proceeding')
        for statement in split_statements(sql):
            await db.execute(text(statement))
        if not await db.scalar(text("SELECT 1 FROM pg_roles WHERE rolname='mizan_app'")):
            raise RuntimeError('Required application role is missing')
        await db.execute(text('GRANT SELECT,INSERT,UPDATE,DELETE ON helpdesk_offerings TO mizan_app'))
        flags = (await db.execute(text("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='public.helpdesk_offerings'::regclass"))).one()
        if not all(flags):
            raise RuntimeError('Help Desk row security was not enforced')
        if not await db.scalar(text("SELECT has_table_privilege('mizan_app','helpdesk_offerings','SELECT,INSERT,UPDATE,DELETE')")):
            raise RuntimeError('Help Desk application grants are incomplete')
