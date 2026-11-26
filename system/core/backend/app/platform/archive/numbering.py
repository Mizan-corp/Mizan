"""Document numbers per workspace (PLAT-6): INV-000001, RET-000001, DEP-000001… each workspace
counts its own, under a row lock on its counter (doc_counters), so two documents never get the
same number and one workspace's numbers say nothing about another's. The formats are the ones
the global invoice_seq gave."""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.tenancy.context import current_tenant_id

# Where numbers of each kind were already given (before the counter existed, or by the demo data):
# a workspace's first counter starts after the highest of them.
_SOURCES = {
    "DEP": ("sales", "archived_documents", "safe_deposits"),
}
_DEFAULT_SOURCES = ("sales", "archived_documents")
_COLUMN = {"sales": "invoice_number", "archived_documents": "doc_number", "safe_deposits": "doc_number"}


async def _highest_given(db: AsyncSession, prefix: str) -> int:
    pattern = f"^{prefix}-([0-9]{{1,18}})$"
    parts = " UNION ALL ".join(
        f"SELECT substring({_COLUMN[t]} from :pat)::bigint AS n FROM {t} WHERE {_COLUMN[t]} LIKE :like"
        for t in _SOURCES.get(prefix, _DEFAULT_SOURCES))
    return int((await db.execute(text(f"SELECT COALESCE(MAX(n), 0) FROM ({parts}) x"),
                                 {"pat": pattern, "like": f"{prefix}-%"})).scalar() or 0)


async def next_value(db: AsyncSession, prefix: str) -> int:
    """The next number of `prefix` in the bound workspace (in the caller's transaction: a rolled
    back document gives its number back)."""
    tid = current_tenant_id.get()
    params = {"tid": tid, "t": prefix}
    value = (await db.execute(text(
        "UPDATE doc_counters SET last_value = last_value + 1, updated_at = now() "
        "WHERE tenant_id = COALESCE(CAST(:tid AS uuid), NULLIF(current_setting('app.tenant_id', true), '')::uuid) "
        "AND doc_type = :t RETURNING last_value"), params)).scalar()
    if value is None:
        start = await _highest_given(db, prefix)
        value = (await db.execute(text(
            "INSERT INTO doc_counters (tenant_id, doc_type, last_value) "
            "VALUES (COALESCE(CAST(:tid AS uuid), NULLIF(current_setting('app.tenant_id', true), '')::uuid), :t, :v) "
            "ON CONFLICT (tenant_id, doc_type) DO UPDATE SET last_value = doc_counters.last_value + 1, updated_at = now() "
            "RETURNING last_value"), {**params, "v": start + 1})).scalar()
    return int(value)


async def next_number(db: AsyncSession, prefix: str) -> str:
    """`INV-000123`: the prefix and the workspace's next number, six digits at least."""
    return f"{prefix}-{await next_value(db, prefix):06d}"
