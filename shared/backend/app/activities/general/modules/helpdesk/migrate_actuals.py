"""Atomic additive actuals migration. Fail closed on an unknown existing table."""
from pathlib import Path
from sqlalchemy import text
from app.db.migrations import split_statements
async def migrate(db):
    sql='\n'.join(x for x in (Path(__file__).parent/'migrations/002_execution_actuals.sql').read_text().splitlines() if not x.lstrip().startswith('--'))
    async with db.begin_nested():
        if await db.scalar(text("SELECT to_regclass('public.helpdesk_execution_revisions')")):raise RuntimeError('Untracked actuals table exists, inspect instead of assuming migration success')
        for statement in split_statements(sql):await db.execute(text(statement))
        flags=(await db.execute(text("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='public.helpdesk_execution_revisions'::regclass"))).one()
        if not all(flags):raise RuntimeError('Forced RLS required')
        if not await db.scalar(text("SELECT has_table_privilege('mizan_app','helpdesk_execution_revisions','SELECT,INSERT')")):raise RuntimeError('Actuals read/append grants missing')
        if await db.scalar(text("SELECT has_table_privilege('mizan_app','helpdesk_execution_revisions','UPDATE') OR has_table_privilege('mizan_app','helpdesk_execution_revisions','DELETE')")):raise RuntimeError('Actuals history must be append-only for application role')
