"""Reading the ledger: the chart as a tree, entries, and a simple trial balance (step 4 of
ADR-014 D12 adds the full reports)."""
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.accounting.services.chart import ensure_chart
from app.core.exceptions import NotFoundError


def _num(v) -> float:
    return float(v or 0)


async def accounts_tree(db: AsyncSession, tenant_id: uuid.UUID) -> list[dict]:
    await ensure_chart(db, tenant_id, complete=True)
    rows = (await db.execute(text(
        "SELECT id, code, name, name_en, type, parent_id, is_group, role, active FROM acc_accounts "
        "WHERE tenant_id = :t ORDER BY code"), {"t": tenant_id})).mappings().all()
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
               l.party_type, l.party_id, l.warehouse_id
        FROM acc_lines l JOIN acc_accounts a ON a.id = l.account_id
        WHERE l.entry_id = :id ORDER BY l.debit DESC, a.code
    """), {"id": entry_id})).mappings().all()
    reversed_by = await db.scalar(text("SELECT id FROM acc_entries WHERE reverses_id = :id"), {"id": entry_id})
    return {**dict(entry), "reversed_by": reversed_by,
            "lines": [{**dict(r), "debit": _num(r["debit"]), "credit": _num(r["credit"])} for r in lines]}


async def trial_balance(db: AsyncSession, tenant_id: uuid.UUID, date_from: date | None = None,
                        date_to: date | None = None) -> dict:
    """Debits and credits per postable account in the period, and each account's balance."""
    await ensure_chart(db, tenant_id)
    rows = (await db.execute(text("""
        SELECT a.id, a.code, a.name, a.name_en, a.type,
               COALESCE(SUM(l.debit), 0) AS debit, COALESCE(SUM(l.credit), 0) AS credit
        FROM acc_accounts a
        JOIN acc_lines l ON l.account_id = a.id
        JOIN acc_entries e ON e.id = l.entry_id
        WHERE a.tenant_id = :t
          AND (CAST(:df AS date) IS NULL OR e.date >= CAST(:df AS date))
          AND (CAST(:dt AS date) IS NULL OR e.date <= CAST(:dt AS date))
        GROUP BY a.id, a.code, a.name, a.name_en, a.type
        ORDER BY a.code
    """), {"t": tenant_id, "df": date_from, "dt": date_to})).mappings().all()
    items, total_d, total_c = [], Decimal("0"), Decimal("0")
    for r in rows:
        d, c = Decimal(r["debit"]), Decimal(r["credit"])
        total_d += d
        total_c += c
        items.append({**dict(r), "debit": float(d), "credit": float(c),
                      "balance_debit": float(max(d - c, Decimal("0"))), "balance_credit": float(max(c - d, Decimal("0")))})
    return {"from": date_from, "to": date_to, "accounts": items,
            "total_debit": float(total_d), "total_credit": float(total_c), "balanced": total_d == total_c}
