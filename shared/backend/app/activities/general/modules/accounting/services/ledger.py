"""Reading the ledger: the chart as a tree and the entries. The reports are in `reports.py`."""
import uuid
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.accounting.services.chart import ensure_chart
from app.core.exceptions import NotFoundError


def _num(v) -> float:
    return float(v or 0)


async def accounts_tree(db: AsyncSession, tenant_id: uuid.UUID) -> list[dict]:
    await ensure_chart(db, tenant_id, complete=True)
    rows = (await db.execute(text(
        "SELECT a.id, a.code, a.name, a.name_en, a.type, a.parent_id, a.is_group, a.role, a.active, m.kind AS money_kind "
        "FROM acc_accounts a LEFT JOIN acc_money_accounts m ON m.account_id = a.id AND m.tenant_id = :t "
        "WHERE a.tenant_id = :t ORDER BY a.code"), {"t": tenant_id})).mappings().all()
    nodes = {r["id"]: {**dict(r), "children": []} for r in rows}
    roots = []
    for node in nodes.values():
        parent = nodes.get(node["parent_id"])
        (parent["children"] if parent else roots).append(node)
    return roots


def _filters(date_from: date | None, date_to: date | None, source_type: str | None, account_id: uuid.UUID | None):
    where, params = ["e.tenant_id = :t"], {}
    if date_from:
        where.append("e.date >= :df")
        params["df"] = date_from
    if date_to:
        where.append("e.date <= :dt")
        params["dt"] = date_to
    if source_type:
        where.append("e.source_type = :st")
        params["st"] = source_type
    if account_id:
        where.append("EXISTS (SELECT 1 FROM acc_lines l WHERE l.entry_id = e.id AND l.account_id = :acc)")
        params["acc"] = account_id
    return " AND ".join(where), params


async def list_entries(db: AsyncSession, tenant_id: uuid.UUID, *, date_from=None, date_to=None, source_type=None,
                       account_id=None, page: int = 1, page_size: int = 50) -> dict:
    where, params = _filters(date_from, date_to, source_type, account_id)
    params.update(t=tenant_id, lim=page_size, off=(page - 1) * page_size)
    total = await db.scalar(text(f"SELECT COUNT(*) FROM acc_entries e WHERE {where}"), params)  # noqa: S608
    rows = (await db.execute(text(f"""
        SELECT e.id, e.number, e.date, e.source_type, e.source_id, e.event, e.memo, e.warehouse_id, e.reverses_id,
               e.created_by, e.created_at,
               (SELECT COALESCE(SUM(debit), 0) FROM acc_lines l WHERE l.entry_id = e.id) AS amount,
               EXISTS (SELECT 1 FROM acc_entries r WHERE r.reverses_id = e.id) AS reversed
        FROM acc_entries e WHERE {where}
        ORDER BY e.date DESC, e.number DESC LIMIT :lim OFFSET :off
    """), params)).mappings().all()  # noqa: S608 (the filters are fixed strings; values are bound)
    return {"items": [{**dict(r), "amount": _num(r["amount"])} for r in rows], "total": total or 0,
            "page": page, "page_size": page_size}


async def get_entry(db: AsyncSession, tenant_id: uuid.UUID, entry_id: uuid.UUID) -> dict:
    entry = (await db.execute(text("SELECT * FROM acc_entries WHERE tenant_id = :t AND id = :id"),
                              {"t": tenant_id, "id": entry_id})).mappings().first()
    if entry is None:
        raise NotFoundError("القيد غير موجود")
    lines = (await db.execute(text("""
        SELECT l.id, l.account_id, a.code AS account_code, a.name AS account_name, l.debit, l.credit,
               l.party_type, l.party_id, l.warehouse_id, COALESCE(pc.name, ps.name, pe.name) AS party_name
        FROM acc_lines l JOIN acc_accounts a ON a.id = l.account_id
        LEFT JOIN customers pc ON l.party_type = 'customer' AND pc.id = l.party_id
        LEFT JOIN suppliers ps ON l.party_type = 'supplier' AND ps.id = l.party_id
        LEFT JOIN hr_employees pe ON l.party_type = 'employee' AND pe.id = l.party_id
        WHERE l.entry_id = :id ORDER BY l.debit DESC, a.code
    """), {"id": entry_id})).mappings().all()
    reversed_by = (await db.execute(text("SELECT id, number, date FROM acc_entries WHERE reverses_id = :id"),
                                    {"id": entry_id})).mappings().first()
    reverses = (await db.execute(text("SELECT id, number, date FROM acc_entries WHERE id = :id"),
                                 {"id": entry["reverses_id"]})).mappings().first() if entry["reverses_id"] else None
    created_by_name = await db.scalar(text("SELECT full_name FROM users WHERE id = :id"), {"id": entry["created_by"]}) \
        if entry["created_by"] else None
    return {**dict(entry), "reversed_by": reversed_by["id"] if reversed_by else None,
            "reversed_by_entry": dict(reversed_by) if reversed_by else None,
            "reverses_entry": dict(reverses) if reverses else None,
            "created_by_name": created_by_name, "source_ref": await source_ref(db, entry["source_type"], entry["source_id"]),
            "lines": [{**dict(r), "debit": _num(r["debit"]), "credit": _num(r["credit"])} for r in lines]}


# The document number (or description) shown with an entry, by its source type.
_SOURCE_REFS = {
    "sale": "SELECT invoice_number FROM sales WHERE id = :id",
    "sale_return": "SELECT invoice_number FROM sales WHERE id = :id",
    "purchase": "SELECT po_number FROM purchase_orders WHERE id = :id",
    "purchase_return": "SELECT return_number FROM purchase_returns WHERE id = :id",
    "expense": "SELECT description FROM expenses WHERE id = :id",
    "supplier_tx": "SELECT COALESCE(reference_doc, notes) FROM supplier_transactions WHERE id = :id",
    "manual": "SELECT memo FROM acc_drafts WHERE id = :id",
}


async def source_ref(db: AsyncSession, source_type: str, source_id) -> str | None:
    sql = _SOURCE_REFS.get(source_type)
    if sql is None:
        return None
    value = await db.scalar(text(sql), {"id": source_id})
    return None if value is None else str(value)


async def trial_balance(db: AsyncSession, tenant_id: uuid.UUID, date_from: date | None = None,
                        date_to: date | None = None) -> dict:
    """The trial balance of the period (kept for callers of step 2): see `reports.trial_balance`."""
    from app.activities.general.modules.accounting.services import reports

    return await reports.trial_balance(db, tenant_id, date_from, date_to)
