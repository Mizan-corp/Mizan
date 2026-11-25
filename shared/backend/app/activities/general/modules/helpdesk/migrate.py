"""Atomic additive Help Desk migration for the existing Python-migration route.

No catch-and-mark-applied behavior. Any DDL, RLS or privilege failure raises and
rolls this savepoint back; the caller may record migration success only on return.

Boot order: services create_all their models before manage.py migrate runs, so on
a fresh stack the table can already exist untracked. Adoption is never assumed:
the existing table must match the tracked contract exactly — columns (name, type,
nullability, required defaults), the primary key, the tenant foreign key with
ON DELETE CASCADE, the check constraints and no unexpected ones — then the
idempotent DDL brings indexes, RLS, policy and grants to the tracked state and
every invariant below is re-verified, including that no broader policy survives.
"""
from pathlib import Path
from sqlalchemy import text
from app.db.migrations import split_statements

EXPECTED_COLUMNS = {
    # name, type, nullable, default required (None = must have no default)
    ('id', 'uuid', False, True),
    ('tenant_id', 'uuid', False, True),
    ('name', 'character varying', False, None),
    ('description', 'text', False, True),
    ('starting_amount', 'numeric', False, None),
    ('currency', 'character varying', False, None),
    ('is_active', 'boolean', False, True),
    ('created_at', 'timestamp with time zone', False, True),
    ('updated_at', 'timestamp with time zone', False, True),
}
EXPECTED_CHECK_MARKERS = ('starting_amount >=', 'currency')
EXPECTED_CHECK_COUNT = 2


async def _verify_contract(db, *, converging: bool = False):
    rows = (await db.execute(text(
        "SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='helpdesk_offerings'"))).all()
    found = {(r.column_name, r.data_type, r.is_nullable == 'YES', (r.column_default is not None) or None)
             for r in rows}
    expected = EXPECTED_COLUMNS
    if converging:
        # The ORM mixin cannot declare the tenant server default; adoption
        # converges it with the ALTER below, so it is exempt only here.
        normalize = lambda s: {(n, t, nn, None if n == 'tenant_id' else d) for n, t, nn, d in s}
        found, expected = normalize(found), normalize(EXPECTED_COLUMNS)
    if found != expected:
        raise RuntimeError('Help Desk table columns do not match the tracked contract; inspect before proceeding')
    if not converging:
        # The ORM mixin cannot declare this server default; the ALTER below
        # converges it on adopted tables, so it is required only after that.
        tenant_default = next((r.column_default for r in rows if r.column_name == 'tenant_id'), None)
        if not tenant_default or 'app.tenant_id' not in tenant_default:
            raise RuntimeError('Help Desk tenant default is missing; inspect before proceeding')
    pk = await db.scalar(text(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conrelid='public.helpdesk_offerings'::regclass AND contype='p'"))
    if pk != 'PRIMARY KEY (id)':
        raise RuntimeError('Help Desk primary key does not match the tracked contract')
    fk = await db.scalar(text(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conrelid='public.helpdesk_offerings'::regclass AND contype='f'"))
    if not fk or 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)' not in fk or 'ON DELETE CASCADE' not in fk:
        raise RuntimeError('Help Desk tenant foreign key does not match the tracked contract')
    checks = [d for d in (await db.scalars(text(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conrelid='public.helpdesk_offerings'::regclass AND contype='c'"))).all()]
    if len(checks) != EXPECTED_CHECK_COUNT or not all(
            any(marker in d for d in checks) for marker in EXPECTED_CHECK_MARKERS):
        raise RuntimeError('Help Desk check constraints do not match the tracked contract')


async def migrate(db):
    sql = '\n'.join(line for line in (Path(__file__).parent/'migrations/001_offerings.sql').read_text().splitlines()
                    if not line.lstrip().startswith('--'))
    async with db.begin_nested():
        if await db.scalar(text("SELECT to_regclass('public.helpdesk_offerings')")):
            # A pre-existing table must already match the tracked contract in full;
            # unknown or broader schemas are never reinterpreted as migrated.
            await _verify_contract(db, converging=True)
        for statement in split_statements(sql):
            await db.execute(text(statement))
        # Converge the tenant default on adopted tables (IF NOT EXISTS create skips it).
        await db.execute(text(
            "ALTER TABLE helpdesk_offerings ALTER COLUMN tenant_id "
            "SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid"))
        await _verify_contract(db)
        if not await db.scalar(text("SELECT 1 FROM pg_roles WHERE rolname='mizan_app'")):
            raise RuntimeError('Required application role is missing')
        await db.execute(text('GRANT SELECT,INSERT,UPDATE,DELETE ON helpdesk_offerings TO mizan_app'))
        flags = (await db.execute(text("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='public.helpdesk_offerings'::regclass"))).one()
        if not all(flags):
            raise RuntimeError('Help Desk row security was not enforced')
        policies = set((await db.scalars(text(
            "SELECT polname FROM pg_policy WHERE polrelid='public.helpdesk_offerings'::regclass"))).all())
        if policies != {'tenant_isolation'}:
            raise RuntimeError('Help Desk policies are broader than the tracked contract')
        if not await db.scalar(text("SELECT has_table_privilege('mizan_app','helpdesk_offerings','SELECT,INSERT,UPDATE,DELETE')")):
            raise RuntimeError('Help Desk application grants are incomplete')
