"""The opening entry (ADR-014 D10): starting the ledger from today's operational balances.

When a workspace turns accounting on, the owner or accountant posts ONE opening entry on a start
date. It is built from the balances the screens already keep:

- each customer with a balance: receivables (party: the customer), debit when they owe us;
- each supplier with a balance: payables (party: the supplier), credit when we owe them;
- each safe, bank, wallet: its money account, debit for the balance;
- each branch's cashier drawer: the cash expected in its open shifts (initial amount plus the cash
  movements), debit;
- the stock: Σ on-hand quantity × average cost, per branch, debit inventory (a product with no cost
  is skipped and listed);
- the difference goes to opening balance equity (role `opening_equity`).

Each figure is the operational balance **less what the ledger already holds** for that same account
or party. On a ledger that is still empty (the normal case) that is the balance itself; if documents
were already posted since the module was turned on, the entry only adds what is missing, so
ledger and operational balances agree after it. Past documents are never re-posted.

Employee advances are not carried: HR keeps no open-advance balance (each month's advances are
recovered through that month's payroll).

It is posted through `posting.post` as source `opening`, event `opening`: the same call twice
returns the same entry, and a second opening is refused while one is in force. It is reversed only by
the normal reversal; after that a new one can be posted.
"""
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.accounting.services import chart as chart_service
from app.activities.general.modules.accounting.services import posting, reports
from app.activities.general.modules.accounting.services import settings as acc_settings
from app.activities.general.modules.accounting.services.posting import dr, cr
from app.core.exceptions import BusinessError

ZERO = Decimal("0")
CENT = Decimal("0.01")
SOURCE = "opening"
NOTES = ["أرصدة الموظفين (السلف) لا تُرحَّل: لا يوجد رصيد سلف مفتوح في الموارد البشرية، وتُسترد السلف عبر مسير الرواتب."]


def _q(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(CENT)


def _item(section: str, label: str, label_en: str, delta: Decimal, *, account: dict | None, debit_side: bool = True,
          party_type: str | None = None, party_id=None, warehouse_id=None, ref: dict | None = None,
          operational: Decimal = ZERO, ledger: Decimal = ZERO) -> dict:
    """One line. `delta` is positive on the account's normal side (debit for assets)."""
    amount = abs(delta)
    on_debit = (delta > 0) == debit_side
    return {"section": section, "label": label, "label_en": label_en, "account": account, "party_type": party_type,
            "party_id": party_id, "warehouse_id": warehouse_id, "ref": ref, "operational": float(operational),
            "ledger": float(ledger), "debit": float(amount) if on_debit else 0.0, "credit": 0.0 if on_debit else float(amount)}


def _account(a: dict) -> dict:
    return {"id": a["id"], "code": a["code"], "name": a["name"], "name_en": a["name_en"]}


async def blockers(db: AsyncSession, tenant_id: uuid.UUID, on: date) -> tuple[list[str], dict | None]:
    """Why an opening entry can't be posted on `on` now, and the one in force if any."""
    out: list[str] = []
    entry, _ = await posting.active_source(db, tenant_id, SOURCE, "opening", SOURCE)
    if entry is not None:
        out.append(f"القيد الافتتاحي مسجل بالفعل ({entry.number}). لا يُنشأ إلا مرة واحدة، ويلزم عكسه أولاً قبل إنشاء قيد جديد")
    if on > posting.today():
        out.append("تاريخ القيد الافتتاحي لا يمكن أن يكون في المستقبل")
    first = await db.scalar(text(
        "SELECT MIN(date) FROM acc_entries WHERE tenant_id = :t AND source_type <> :s"), {"t": tenant_id, "s": SOURCE})
    if first is not None and on > first:
        out.append(f"يجب أن يكون تاريخ القيد الافتتاحي في أو قبل تاريخ أول قيد في الدفاتر ({first.isoformat()})")
    if await posting.period_closed(db, tenant_id, on):
        out.append(f"الفترة المحاسبية {on.strftime('%Y-%m')} مغلقة — اختر تاريخاً في فترة مفتوحة")
    existing = None if entry is None else {"id": entry.id, "number": entry.number, "date": entry.date}
    return out, existing


async def plan(db: AsyncSession, tenant_id: uuid.UUID, on: date) -> dict:
    """The lines the opening entry would have, and the products it skips. Writes nothing (apart from
    copying the standard chart the first time)."""
    chart = await reports.load_chart(db, tenant_id)
    role = lambda r: chart.by_id[chart.by_role[r]]  # noqa: E731
    receivables, payables = role("receivables"), role("payables")
    inventory, equity = role("inventory"), role("opening_equity")
    lines: list[dict] = []

    # Customers and suppliers: the operational balance less the ledger's balance of that party.
    for party_type, table, acc, sign, label, label_en in (
            ("customer", "customers", receivables, 1, "رصيد العميل", "Customer balance"),
            ("supplier", "suppliers", payables, -1, "رصيد المورد", "Supplier balance")):
        rows = (await db.execute(text(f"""
            WITH led AS (
                SELECT l.party_id, SUM(l.debit - l.credit) * :sign AS bal
                FROM acc_lines l WHERE l.tenant_id = :t AND l.account_id = :acc AND l.party_type = :pt GROUP BY l.party_id),
            p AS (SELECT id, name, COALESCE(balance, 0) AS bal FROM {table} WHERE tenant_id = :t)
            SELECT COALESCE(p.id, led.party_id) AS id, COALESCE(p.name, '—') AS name, COALESCE(p.bal, 0) AS operational,
                   COALESCE(led.bal, 0) AS ledger
            FROM p FULL JOIN led ON led.party_id = p.id
            WHERE COALESCE(p.bal, 0) <> COALESCE(led.bal, 0) ORDER BY 2
        """), {"t": tenant_id, "acc": acc["id"], "pt": party_type, "sign": sign})).all()  # noqa: S608
        for r in rows:
            delta = _q(r.operational) - _q(r.ledger)
            if delta:
                lines.append(_item(party_type + "s", f"{label} — {r.name}", f"{label_en} — {r.name}", delta,
                                   account=_account(acc), debit_side=sign > 0, party_type=party_type, party_id=r.id,
                                   operational=_q(r.operational), ledger=_q(r.ledger)))

    # Safes, banks and wallets: each one's money account.
    ledger_by_account = {a: _q(d) - _q(c) for a, (d, c) in (await reports.account_sums(db, tenant_id)).items()}
    for kind, table, section in (("safe", "safes", "safes"), ("wallet", "payment_wallets", "wallets")):
        rows = (await db.execute(text(f"""
            SELECT s.id, COALESCE(s.balance, 0) AS balance, m.account_id FROM {table} s
            LEFT JOIN acc_money_accounts m ON m.tenant_id = :t AND m.kind = :kind AND m.ref_id = s.id
            WHERE s.tenant_id = :t ORDER BY s.name, s.id
        """), {"t": tenant_id, "kind": kind})).all()  # noqa: S608
        for r in rows:
            ledger = ledger_by_account.get(r.account_id, ZERO)
            delta = _q(r.balance) - ledger
            if not delta:
                continue
            _, name, name_en = await chart_service._money_name(db, kind, r.id)
            lines.append(_item(section, name, name_en, delta, ref={"kind": kind, "id": r.id},
                               account=_account(chart.by_id[r.account_id]) if r.account_id else None,
                               operational=_q(r.balance), ledger=ledger))

    # Each branch's cashier drawer: the cash the open shifts should hold now.
    drawers = (await db.execute(text("""
        SELECT s.warehouse_id, w.name AS warehouse, SUM(s.initial_amount + COALESCE(t.net, 0)) AS cash
        FROM shifts s LEFT JOIN warehouses w ON w.id = s.warehouse_id
        LEFT JOIN (
            SELECT shift_id, SUM(CASE WHEN type::text IN ('sale', 'deposit') THEN amount ELSE -amount END) AS net
            FROM drawer_transactions WHERE tenant_id = :t AND cancelled_at IS NULL AND COALESCE(payment_method, 'cash') <> 'wallet'
            GROUP BY shift_id) t ON t.shift_id = s.id
        WHERE s.tenant_id = :t AND s.status::text = 'open' AND s.warehouse_id IS NOT NULL
        GROUP BY s.warehouse_id, w.name ORDER BY w.name
    """), {"t": tenant_id})).all()
    for r in drawers:
        row = (await db.execute(text(
            "SELECT account_id FROM acc_money_accounts WHERE tenant_id = :t AND kind = 'drawer' AND ref_id = :r"),
            {"t": tenant_id, "r": r.warehouse_id})).scalar_one_or_none()
        ledger = ledger_by_account.get(row, ZERO)
        delta = _q(r.cash) - ledger
        if delta:
            lines.append(_item("drawers", f"درج كاشير — {r.warehouse or ''}".strip(" —"), f"Cashier drawer — {r.warehouse or ''}".strip(" —"),
                               delta, ref={"kind": "drawer", "id": r.warehouse_id}, warehouse_id=r.warehouse_id,
                               account=_account(chart.by_id[row]) if row else None, operational=_q(r.cash), ledger=ledger))

    # Stock at average cost, per branch, and the products that have stock but no cost.
    stock = (await db.execute(text("""
        SELECT sb.warehouse_id, w.name AS warehouse, SUM(sb.qty * COALESCE(NULLIF(p.avg_cost, 0), p.cost_price, 0)) AS value
        FROM stock_balances sb JOIN products p ON p.id = sb.product_id LEFT JOIN warehouses w ON w.id = sb.warehouse_id
        WHERE sb.tenant_id = :t AND p.tenant_id = :t AND sb.qty > 0 GROUP BY sb.warehouse_id, w.name
    """), {"t": tenant_id})).all()
    ledger_stock = {r.warehouse_id: _q(r.bal) for r in (await db.execute(text(
        "SELECT warehouse_id, SUM(debit - credit) AS bal FROM acc_lines WHERE tenant_id = :t AND account_id = :a "
        "GROUP BY warehouse_id"), {"t": tenant_id, "a": inventory["id"]})).all()}
    seen = set()
    for r in sorted(stock, key=lambda r: r.warehouse or ""):
        seen.add(r.warehouse_id)
        ledger = ledger_stock.get(r.warehouse_id, ZERO)
        delta = _q(r.value) - ledger
        if delta:
            lines.append(_item("inventory", f"مخزون بمتوسط التكلفة — {r.warehouse or ''}".strip(" —"),
                               f"Stock at average cost — {r.warehouse or ''}".strip(" —"), delta, account=_account(inventory),
                               warehouse_id=r.warehouse_id, operational=_q(r.value), ledger=ledger))
    for wh, ledger in ledger_stock.items():  # the ledger holds stock where the shelves hold none
        if wh not in seen and ledger:
            lines.append(_item("inventory", "تسوية مخزون الدفاتر", "Ledger stock adjustment", -ledger, account=_account(inventory),
                               warehouse_id=wh, operational=ZERO, ledger=ledger))
    no_cost = [{"product_id": r.id, "name": r.name, "code": r.code, "qty": float(r.qty)} for r in (await db.execute(text("""
        SELECT p.id, p.name, p.code, SUM(sb.qty) AS qty FROM stock_balances sb JOIN products p ON p.id = sb.product_id
        WHERE sb.tenant_id = :t AND p.tenant_id = :t AND sb.qty > 0 AND COALESCE(NULLIF(p.avg_cost, 0), p.cost_price, 0) = 0
        GROUP BY p.id, p.name, p.code ORDER BY p.name
    """), {"t": tenant_id})).all()]

    debit = sum((Decimal(str(i["debit"])) for i in lines), ZERO)
    credit = sum((Decimal(str(i["credit"])) for i in lines), ZERO)
    plug = debit - credit
    if plug:
        lines.append(_item("equity", "رصيد أول المدة (فرق التوازن)", "Opening balance equity (balancing difference)",
                           plug, account=_account(equity), debit_side=False))
    total_debit = sum((Decimal(str(i["debit"])) for i in lines), ZERO)
    total_credit = sum((Decimal(str(i["credit"])) for i in lines), ZERO)
    sections: dict[str, dict] = {}
    for i in lines:
        sec = sections.setdefault(i["section"], {"count": 0, "debit": ZERO, "credit": ZERO})
        sec["count"] += 1
        sec["debit"] += Decimal(str(i["debit"]))
        sec["credit"] += Decimal(str(i["credit"]))
    return {"date": on, "lines": lines, "total_debit": float(total_debit), "total_credit": float(total_credit),
            "balanced": total_debit == total_credit,
            "equity": {"debit": float(max(-plug, ZERO)), "credit": float(max(plug, ZERO))},
            "sections": {k: {"count": v["count"], "debit": float(v["debit"]), "credit": float(v["credit"])}
                         for k, v in sections.items()},
            "skipped_no_cost": no_cost, "notes": NOTES}


async def preview(db: AsyncSession, tenant_id: uuid.UUID, on: date) -> dict:
    why, existing = await blockers(db, tenant_id, on)
    out = await plan(db, tenant_id, on)
    return {**out, "can_post": not why, "blockers": why, "opening_entry": existing,
            "settings": await acc_settings.get(db, tenant_id)}


async def create(db: AsyncSession, tenant_id: uuid.UUID, on: date, user_id: uuid.UUID | None) -> dict:
    """Post the opening entry (once per workspace, unless reversed) and record the start date. Runs in
    the caller's transaction."""
    await reports.load_chart(db, tenant_id)
    why, _ = await blockers(db, tenant_id, on)
    if why:
        raise BusinessError(why[0])
    out = await plan(db, tenant_id, on)
    post_lines = []
    for i in out["lines"]:
        account_id = i["account"]["id"] if i["account"] else None
        if account_id is None:
            account_id = await chart_service.money_account(db, tenant_id, i["ref"]["kind"], i["ref"]["id"])
        make = dr if i["debit"] else cr
        post_lines.append(make(account_id, i["debit"] or i["credit"], party_type=i["party_type"], party_id=i["party_id"],
                               warehouse_id=i["warehouse_id"]))
    _, source_id = await posting.active_source(db, tenant_id, SOURCE, "opening", SOURCE)
    entry = await posting.post(db, tenant_id, SOURCE, source_id, SOURCE, on, post_lines,
                               memo=f"قيد افتتاحي بأرصدة {on.isoformat()}", user_id=user_id)
    await acc_settings.update(db, tenant_id, start_date=on)
    return {**out, "entry": None if entry is None else {"id": entry.id, "number": entry.number, "date": entry.date},
            "settings": await acc_settings.get(db, tenant_id)}
