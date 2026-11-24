"""Atomic additive Help Desk migration for the existing Python-migration route.

No catch-and-mark-applied behavior. Any DDL, RLS or privilege failure raises and
rolls this savepoint back; the caller may record migration success only on return.
"""
from pathlib import Path
from sqlalchemy import text
from app.db.migrations import split_statements

async def migrate(db):
    sql = '\n'.join(line for line in (Path(__file__).parent/'migrations/001_offerings.sql').read_text().splitlines()
                    if not line.lstrip().startswith('--'))
    async with db.begin_nested():
        exists = await db.scalar(text("SELECT to_regclass('public.helpdesk_offerings')"))
        if exists:
            # Do not reinterpret a pre-existing unknown schema as successfully migrated.
            raise RuntimeError('Help Desk table already exists without tracked migration; inspect before proceeding')
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
