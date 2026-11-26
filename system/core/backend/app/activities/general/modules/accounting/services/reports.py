"""The accounting reports (ADR-014 D8). Every figure is computed from `acc_accounts`, `acc_entries`
and `acc_lines` only; the operational balances appear in `reconciliation` alone, as a check.

Each report takes a date range and an optional branch (`warehouse_id` on the lines; lines with no
branch, such as a customer receipt into a safe, are left out of a branch report). Amounts are summed
as `Decimal` and returned as numbers rounded to the piastre.

Signs: a balance is debit minus credit; reports show it in the account's natural direction (assets
and expenses by debit, the others by credit) so a screen never shows a normal balance as negative.

The year-end closing entry (source `year_end`, D7) moves the year's income and expenses into retained
earnings. `include_closing=false` leaves it out, so the profit of a closed year can still be shown;
the income statement leaves it out by default, the other reports include it.
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.accounting.services import settings as acc_settings
from app.activities.general.modules.accounting.services.chart import ensure_chart
from app.activities.general.modules.accounting.services.posting import today
from app.core.exceptions import BusinessError, NotFoundError

ZERO = Decimal("0")
CENT = Decimal("0.01")
DEBIT_TYPES = ("asset", "expense")
PARTY_TYPES = ("customer", "supplier", "employee")


def money(v) -> float:
    return float(Decimal(str(v or 0)).quantize(CENT))


# ── the chart, as a tree ──────────────────────────────────────────────────────────────────────

class Chart:
    """The workspace's accounts in memory: a few dozen rows, loaded once per report."""

    def __init__(self, rows: list[dict]):
        self.by_id = {r["id"]: r for r in rows}
        self.children: dict[uuid.UUID | None, list[uuid.UUID]] = {}
        for r in rows:
            self.children.setdefault(r["parent_id"], []).append(r["id"])
        self.by_role = {r["role"]: r["id"] for r in rows if r["role"]}
        self._depth: dict[uuid.UUID, int] = {}

    def ancestors(self, acc_id) -> list[uuid.UUID]:
        out, cur = [], self.by_id[acc_id]["parent_id"]
        while cur is not None and cur in self.by_id and len(out) < 20:
            out.append(cur)
            cur = self.by_id[cur]["parent_id"]
        return out

    def level(self, acc_id) -> int:
        if acc_id not in self._depth:
            self._depth[acc_id] = len(self.ancestors(acc_id))
        return self._depth[acc_id]

    def subtree(self, acc_id) -> list[uuid.UUID]:
        out, stack = [], [acc_id]
        while stack:
            cur = stack.pop()
            out.append(cur)
            stack.extend(self.children.get(cur, []))
        return out

    def in_subtree_of_role(self, acc_id, role: str) -> bool:
        root = self.by_role.get(role)
        return root is not None and (acc_id == root or root in self.ancestors(acc_id))

    def group_of_role(self, role: str) -> uuid.UUID | None:
        """The group a role account sits in (the "other income" or "operating expenses" group):
        found through the role, so a renumbered chart keeps working."""
        acc = self.by_role.get(role)
        return self.by_id[acc]["parent_id"] if acc else None

    def in_group(self, acc_id, group_id) -> bool:
        return group_id is not None and (acc_id == group_id or group_id in self.ancestors(acc_id))

    def ordered(self) -> list[dict]:
        return sorted(self.by_id.values(), key=lambda r: r["code"])


async def load_chart(db: AsyncSession, tenant_id: uuid.UUID) -> Chart:
    await ensure_chart(db, tenant_id)
    rows = (await db.execute(text(
        "SELECT id, code, name, name_en, type, parent_id, is_group, role, active FROM acc_accounts "
        "WHERE tenant_id = :t ORDER BY code"), {"t": tenant_id})).mappings().all()
    return Chart([dict(r) for r in rows])


def _name(a: dict) -> dict:
    return {"id": a["id"], "code": a["code"], "name": a["name"], "name_en": a["name_en"], "type": a["type"]}


# ── sums over the lines ───────────────────────────────────────────────────────────────────────

def _line_filter(warehouse_id, include_closing: bool, extra: str = "") -> str:
    sql = "l.tenant_id = :t AND e.tenant_id = :t"
    if warehouse_id:
        sql += " AND l.warehouse_id = :wh"
    if not include_closing:
        sql += " AND e.source_type <> 'year_end'"
    return sql + (f" AND {extra}" if extra else "")


async def account_sums(db: AsyncSession, tenant_id: uuid.UUID, *, date_from: date | None = None, date_to: date | None = None,
                       warehouse_id: uuid.UUID | None = None, include_closing: bool = True) -> dict[uuid.UUID, tuple[Decimal, Decimal]]:
    """(debit, credit) per account over the lines in the range (accounts with lines only)."""
    where, params = _line_filter(warehouse_id, include_closing), {"t": tenant_id, "wh": warehouse_id}
    if date_from:
        where += " AND e.date >= :df"
        params["df"] = date_from
    if date_to:
        where += " AND e.date <= :dt"
        params["dt"] = date_to
    if not warehouse_id:
        params.pop("wh")
    rows = (await db.execute(text(
        f"SELECT l.account_id, SUM(l.debit) AS d, SUM(l.credit) AS c FROM acc_lines l "  # noqa: S608 (fixed filters, bound values)
        f"JOIN acc_entries e ON e.id = l.entry_id WHERE {where} GROUP BY l.account_id"), params)).all()
    return {r.account_id: (Decimal(r.d), Decimal(r.c)) for r in rows}


def _natural(acc_type: str, debit: Decimal, credit: Decimal) -> Decimal:
    return debit - credit if acc_type in DEBIT_TYPES else credit - debit


def _rollup(chart: Chart, leaf: dict[uuid.UUID, tuple[Decimal, ...]], width: int) -> dict[uuid.UUID, list[Decimal]]:
    """Each account's figures plus all its descendants' (width: how many numbers per account)."""
    out: dict[uuid.UUID, list[Decimal]] = {}
    for acc_id, vals in leaf.items():
        for target in [acc_id, *chart.ancestors(acc_id)]:
            cur = out.setdefault(target, [ZERO] * width)
            for i in range(width):
                cur[i] += vals[i]
    return out


# ── trial balance ─────────────────────────────────────────────────────────────────────────────

async def trial_balance(db: AsyncSession, tenant_id: uuid.UUID, date_from: date | None = None, date_to: date | None = None,
                        warehouse_id: uuid.UUID | None = None, include_zero: bool = False,
                        include_closing: bool = True) -> dict:
    """Per account: the balance before `date_from` (opening), the period's debit and credit, and the
    closing balance at `date_to`; group accounts roll up their children. Accounts with no lines
    are hidden unless `include_zero`. The totals add the postable accounts only."""
    chart = await load_chart(db, tenant_id)
    opening = await account_sums(db, tenant_id, date_to=date_from - timedelta(days=1), warehouse_id=warehouse_id,
                                 include_closing=include_closing) if date_from else {}
    period = await account_sums(db, tenant_id, date_from=date_from, date_to=date_to, warehouse_id=warehouse_id,
                                include_closing=include_closing)
    leaf = {}
    for acc_id in {*opening, *period}:
        od, oc = opening.get(acc_id, (ZERO, ZERO))
        pd, pc = period.get(acc_id, (ZERO, ZERO))
        leaf[acc_id] = (od, oc, pd, pc)
    sums = _rollup(chart, leaf, 4)

    def figures(od: Decimal, oc: Decimal, pd: Decimal, pc: Decimal) -> dict:
        o, c = od - oc, od - oc + pd - pc
        return {"opening": money(o), "opening_debit": money(max(o, ZERO)), "opening_credit": money(max(-o, ZERO)),
                "debit": money(pd), "credit": money(pc),
                "closing": money(c), "closing_debit": money(max(c, ZERO)), "closing_credit": money(max(-c, ZERO)),
                "balance_debit": money(max(c, ZERO)), "balance_credit": money(max(-c, ZERO))}

    rows, totals = [], dict.fromkeys(("opening_debit", "opening_credit", "debit", "credit", "closing_debit", "closing_credit"), ZERO)
    for a in chart.ordered():
        od, oc, pd, pc = sums.get(a["id"], [ZERO] * 4)
        touched = a["id"] in sums
        if not touched and not include_zero:
            continue
        row = {**_name(a), "parent_id": a["parent_id"], "is_group": a["is_group"], "level": chart.level(a["id"]),
               "role": a["role"], "active": a["active"], **figures(od, oc, pd, pc)}
        rows.append(row)
        if not a["is_group"] and touched:
            for key in totals:
                totals[key] += Decimal(str(row[key]))
    totals = {k: money(v) for k, v in totals.items()}
    balanced = (totals["debit"] == totals["credit"] and totals["opening_debit"] == totals["opening_credit"]
                and totals["closing_debit"] == totals["closing_credit"])
    return {"from": date_from, "to": date_to, "warehouse_id": warehouse_id, "include_closing": include_closing,
            "include_zero": include_zero, "accounts": rows, "totals": totals,
            "total_debit": totals["debit"], "total_credit": totals["credit"], "balanced": balanced}


# ── income statement ──────────────────────────────────────────────────────────────────────────

def classify_pl(chart: Chart, acc: dict) -> str | None:
    """The income-statement section of a postable income or expense account (by role and group, never
    by code)."""
    acc_id = acc["id"]
    if acc["type"] == "income":
        if chart.in_subtree_of_role(acc_id, "sales_returns"):
            return "sales_returns"
        if chart.in_group(acc_id, chart.group_of_role("other_income")):
            return "other_income"
        return "revenue"
    if acc["type"] == "expense":
        if chart.in_subtree_of_role(acc_id, "cogs"):
            return "cogs"
        if chart.in_group(acc_id, chart.group_of_role("salaries_expense")):
            return "operating_expenses"
        return "other_expenses"
    return None


async def income_statement(db: AsyncSession, tenant_id: uuid.UUID, date_from: date | None = None, date_to: date | None = None,
                           warehouse_id: uuid.UUID | None = None, include_closing: bool = False) -> dict:
    """Revenue, less sales returns, is net sales; less cost of goods sold is gross profit; less
    operating expenses is operating profit; plus other income, less other expenses (cash shortage,
    other) is net profit. Income lines are credit minus debit, expense lines debit minus credit."""
    chart = await load_chart(db, tenant_id)
    sums = await account_sums(db, tenant_id, date_from=date_from, date_to=date_to, warehouse_id=warehouse_id,
                              include_closing=include_closing)
    sections: dict[str, list[dict]] = {k: [] for k in ("revenue", "sales_returns", "cogs", "operating_expenses",
                                                      "other_income", "other_expenses")}
    totals = dict.fromkeys(sections, ZERO)
    for a in chart.ordered():
        if a["is_group"] or a["id"] not in sums:
            continue
        section = classify_pl(chart, a)
        if section is None:
            continue
        amount = _natural(a["type"], *sums[a["id"]])
        if section == "sales_returns":  # a contra account: debit minus credit, taken off the sales
            amount = -amount
        if amount == 0:
            continue
        sections[section].append({**_name(a), "amount": money(amount)})
        totals[section] += amount
    net_sales = totals["revenue"] - totals["sales_returns"]
    gross = net_sales - totals["cogs"]
    operating = gross - totals["operating_expenses"]
    net = operating + totals["other_income"] - totals["other_expenses"]
    out = {"from": date_from, "to": date_to, "warehouse_id": warehouse_id, "include_closing": include_closing}
    for key, lines in sections.items():
        out[key] = {"lines": lines, "total": money(totals[key])}
    out.update(net_sales=money(net_sales), gross_profit=money(gross), operating_profit=money(operating),
               net_profit=money(net))
    return out


# ── balance sheet ─────────────────────────────────────────────────────────────────────────────

def fiscal_year_start_for(on: date, first_month: int) -> date:
    return date(on.year if on.month >= first_month else on.year - 1, first_month, 1)


def _bs_rows(chart: Chart, acc_type: str, sums: dict[uuid.UUID, tuple[Decimal, Decimal]]) -> tuple[list[dict], Decimal]:
    leaf = {i: (_natural(chart.by_id[i]["type"], *v),) for i, v in sums.items() if chart.by_id[i]["type"] == acc_type}
    rolled = _rollup(chart, leaf, 1)
    rows, total = [], ZERO
    for a in chart.ordered():
        if a["type"] != acc_type or a["id"] not in rolled:
            continue
        if rolled[a["id"]][0] == 0 and not any(leaf.get(i, (ZERO,))[0] for i in chart.subtree(a["id"])):
            continue
        rows.append({**_name(a), "parent_id": a["parent_id"], "is_group": a["is_group"], "level": chart.level(a["id"]),
                     "amount": money(rolled[a["id"]][0])})
        if a["parent_id"] is None:
            total += rolled[a["id"]][0]
    return rows, total


async def balance_sheet(db: AsyncSession, tenant_id: uuid.UUID, as_of: date | None = None,
                        warehouse_id: uuid.UUID | None = None, include_closing: bool = True) -> dict:
    """Assets, liabilities and equity at `as_of` (default today), every entry up to that date. Equity
    holds the equity accounts plus the profit not yet closed into retained earnings, computed from the
    income and expense accounts: `prior_years_profit` (before the fiscal year of `as_of`) and
    `current_year_profit` (from its start to `as_of`). With the year-end entry posted both are zero
    for the closed year, because its income and expense balances were moved to retained earnings.
    The sheet must satisfy assets = liabilities + equity; otherwise `balanced` is false and
    `difference` says by how much."""
    as_of = as_of or today()
    chart = await load_chart(db, tenant_id)
    first_month = (await acc_settings.get(db, tenant_id, create=False))["fiscal_year_start"]
    fy_start = fiscal_year_start_for(as_of, first_month)
    sums = await account_sums(db, tenant_id, date_to=as_of, warehouse_id=warehouse_id, include_closing=include_closing)
    before = await account_sums(db, tenant_id, date_to=fy_start - timedelta(days=1), warehouse_id=warehouse_id,
                                include_closing=include_closing)

    def profit(source: dict) -> Decimal:
        return sum((c - d for i, (d, c) in source.items() if chart.by_id[i]["type"] in ("income", "expense")), ZERO)

    prior = profit(before)
    current = profit(sums) - prior
    assets, total_assets = _bs_rows(chart, "asset", sums)
    liabilities, total_liabilities = _bs_rows(chart, "liability", sums)
    equity, equity_accounts = _bs_rows(chart, "equity", sums)
    total_equity = equity_accounts + prior + current
    difference = total_assets - total_liabilities - total_equity
    return {
        "as_of": as_of, "warehouse_id": warehouse_id, "include_closing": include_closing, "fiscal_year_start": fy_start,
        "assets": {"accounts": assets, "total": money(total_assets)},
        "liabilities": {"accounts": liabilities, "total": money(total_liabilities)},
        "equity": {"accounts": equity, "accounts_total": money(equity_accounts), "prior_years_profit": money(prior),
                   "current_year_profit": money(current), "profit_to_date": money(prior + current),
                   "total": money(total_equity)},
        "total_liabilities_and_equity": money(total_liabilities + total_equity),
        "difference": money(difference), "balanced": abs(difference) < CENT,
    }


# ── general ledger ────────────────────────────────────────────────────────────────────────────

_PARTY_JOINS = """
    LEFT JOIN customers pc ON l.party_type = 'customer' AND pc.id = l.party_id
    LEFT JOIN suppliers ps ON l.party_type = 'supplier' AND ps.id = l.party_id
    LEFT JOIN hr_employees pe ON l.party_type = 'employee' AND pe.id = l.party_id
"""


def _line_row(r, sign: int, opening: Decimal) -> dict:
    return {"entry_id": r.entry_id, "number": r.number, "date": r.date, "source_type": r.source_type,
            "source_id": r.source_id, "event": r.event, "memo": r.memo, "account_id": r.account_id,
            "account_code": r.account_code, "account_name": r.account_name, "account_name_en": r.account_name_en,
            "debit": money(r.debit), "credit": money(r.credit), "party_type": r.party_type, "party_id": r.party_id,
            "party_name": r.party_name, "warehouse_id": r.warehouse_id,
            "balance": money(opening + sign * Decimal(r.running))}


async def _lines_page(db: AsyncSession, tenant_id: uuid.UUID, where: str, params: dict, sign: int, opening: Decimal,
                      page: int, page_size: int) -> tuple[list[dict], dict]:
    """One page of lines in date order with the running balance (over the whole range), and the
    range's totals. `where` filters acc_lines `l` joined to acc_entries `e`; `sign` is +1 when the
    balance is debit minus credit, -1 for credit minus debit."""
    params = {**params, "t": tenant_id, "lim": page_size, "off": (page - 1) * page_size}
    order = "e.date, e.number, (l.credit > 0), l.id"
    rows = (await db.execute(text(f"""
        SELECT * FROM (
            SELECT e.id AS entry_id, e.number, e.date, e.source_type, e.source_id, e.event, e.memo,
                   a.id AS account_id, a.code AS account_code, a.name AS account_name, a.name_en AS account_name_en,
                   l.debit, l.credit, l.party_type, l.party_id, l.warehouse_id,
                   COALESCE(pc.name, ps.name, pe.name) AS party_name,
                   SUM(l.debit - l.credit) OVER (ORDER BY {order}) AS running,
                   row_number() OVER (ORDER BY {order}) AS rn
            FROM acc_lines l JOIN acc_entries e ON e.id = l.entry_id JOIN acc_accounts a ON a.id = l.account_id
            {_PARTY_JOINS}
            WHERE {where}
        ) x ORDER BY rn LIMIT :lim OFFSET :off
    """), params)).all()  # noqa: S608 (fixed filters, bound values)
    totals = (await db.execute(text(
        f"SELECT COUNT(*) AS n, COALESCE(SUM(l.debit), 0) AS d, COALESCE(SUM(l.credit), 0) AS c FROM acc_lines l "  # noqa: S608
        f"JOIN acc_entries e ON e.id = l.entry_id WHERE {where}"), params)).one()
    net = Decimal(totals.d) - Decimal(totals.c)
    return ([_line_row(r, sign, opening) for r in rows],
            {"count": totals.n, "total_debit": money(totals.d), "total_credit": money(totals.c),
             "closing_balance": money(opening + sign * net)})


def _range_sql(date_from, date_to, warehouse_id, include_closing, params: dict) -> str:
    sql = _line_filter(warehouse_id, include_closing)
    if warehouse_id:
        params["wh"] = warehouse_id
    if date_from:
        sql += " AND e.date >= :df"
        params["df"] = date_from
    if date_to:
        sql += " AND e.date <= :dt"
        params["dt"] = date_to
    return sql


async def _balance_before(db: AsyncSession, tenant_id, where_extra: str, params: dict, on: date | None, warehouse_id,
                          include_closing: bool) -> Decimal:
    """Debit minus credit of the matching lines dated before `on`."""
    if on is None:
        return ZERO
    p = {**params, "t": tenant_id, "before": on}
    sql = _line_filter(warehouse_id, include_closing, f"e.date < :before AND {where_extra}")
    if warehouse_id:
        p["wh"] = warehouse_id
    row = (await db.execute(text(
        f"SELECT COALESCE(SUM(l.debit - l.credit), 0) FROM acc_lines l JOIN acc_entries e ON e.id = l.entry_id "  # noqa: S608
        f"WHERE {sql}"), p)).scalar_one()
    return Decimal(row)


async def general_ledger(db: AsyncSession, tenant_id: uuid.UUID, account_id: uuid.UUID, date_from: date | None = None,
                         date_to: date | None = None, warehouse_id: uuid.UUID | None = None, include_closing: bool = True,
                         page: int = 1, page_size: int = 200) -> dict:
    """The lines of one account (a group account takes all its sub-accounts) in date order, each with
    a running balance in the account's natural direction, starting from the opening balance (before
    `date_from`). Every line names its entry, its source document (source_type / source_id / event)
    and its party."""
    chart = await load_chart(db, tenant_id)
    acc = chart.by_id.get(account_id)
    if acc is None:
        raise NotFoundError("الحساب غير موجود")
    sign = 1 if acc["type"] in DEBIT_TYPES else -1
    ids = chart.subtree(account_id)
    params: dict = {"ids": ids}
    where = _range_sql(date_from, date_to, warehouse_id, include_closing, params) + " AND l.account_id = ANY(:ids)"
    opening = sign * await _balance_before(db, tenant_id, "l.account_id = ANY(:ids)", {"ids": ids}, date_from,
                                           warehouse_id, include_closing)
    lines, totals = await _lines_page(db, tenant_id, where, params, sign, opening, page, page_size)
    return {"account": {**_name(acc), "is_group": acc["is_group"]}, "normal_side": "debit" if sign > 0 else "credit",
            "from": date_from, "to": date_to, "warehouse_id": warehouse_id, "include_closing": include_closing,
            "opening_balance": money(opening), "lines": lines, "page": page, "page_size": page_size, **totals}


# ── party statement ───────────────────────────────────────────────────────────────────────────

async def _party(db: AsyncSession, party_type: str, party_id: uuid.UUID):
    table, label = {"customer": ("customers", "العميل"), "supplier": ("suppliers", "المورد"),
                    "employee": ("hr_employees", "الموظف")}[party_type]
    balance = "balance" if party_type != "employee" else "NULL::numeric AS balance"
    row = (await db.execute(text(f"SELECT id, name, {balance} FROM {table} WHERE id = :id"),  # noqa: S608 (table from a fixed map)
                            {"id": party_id})).one_or_none()
    if row is None:
        raise NotFoundError(f"{label} غير موجود")
    return row


async def party_statement(db: AsyncSession, tenant_id: uuid.UUID, party_type: str, party_id: uuid.UUID,
                          date_from: date | None = None, date_to: date | None = None,
                          warehouse_id: uuid.UUID | None = None, page: int = 1, page_size: int = 200) -> dict:
    """The lines carrying this party, oldest first, with a running balance and the balance before
    `date_from`. The balance is what the party owes us (debit minus credit) for a customer or an
    employee, and what we owe them (credit minus debit) for a supplier: the same sign as the
    customer's and supplier's operational `balance`, so `difference` reconciles the two."""
    if party_type not in PARTY_TYPES:
        raise BusinessError("نوع الطرف غير صحيح: عميل أو مورد أو موظف")
    await load_chart(db, tenant_id)
    party = await _party(db, party_type, party_id)
    sign = -1 if party_type == "supplier" else 1
    params: dict = {"pt": party_type, "pid": party_id}
    where = _range_sql(date_from, date_to, warehouse_id, True, params) + " AND l.party_type = :pt AND l.party_id = :pid"
    opening = sign * await _balance_before(db, tenant_id, "l.party_type = :pt AND l.party_id = :pid", params, date_from,
                                           warehouse_id, True)
    lines, totals = await _lines_page(db, tenant_id, where, params, sign, opening, page, page_size)
    ledger_now = sign * await _balance_before(db, tenant_id, "l.party_type = :pt AND l.party_id = :pid", params,
                                              today() + timedelta(days=1), None, True)
    operational = None if party.balance is None else Decimal(party.balance or 0)
    return {"party": {"type": party_type, "id": party.id, "name": party.name},
            "meaning": "what_they_owe_us" if sign > 0 else "what_we_owe_them",
            "from": date_from, "to": date_to, "warehouse_id": warehouse_id, "opening_balance": money(opening),
            "lines": lines, "page": page, "page_size": page_size, **totals,
            "ledger_balance": money(ledger_now),
            "operational_balance": None if operational is None else money(operational),
            "difference": None if operational is None else money(operational - ledger_now),
            "matches": None if operational is None else abs(operational - ledger_now) < CENT}


# ── reconciliation ────────────────────────────────────────────────────────────────────────────

INVENTORY_TOLERANCE = Decimal("1.00")  # the average cost is kept to 4 places, each entry to the piastre


def _check(key: str, label: str, label_en: str, ledger: Decimal, operational: Decimal, tolerance: Decimal = CENT, **extra) -> dict:
    diff = operational - ledger
    return {"key": key, "label": label, "label_en": label_en, "ledger": money(ledger), "operational": money(operational),
            "difference": money(diff), "ok": abs(diff) < tolerance, **extra}


async def _party_differences(db: AsyncSession, tenant_id, party_type: str, table: str, role: str, sign: int, limit: int = 50):
    rows = (await db.execute(text(f"""
        WITH led AS (
            SELECT l.party_id, SUM(l.debit - l.credit) * :sign AS bal
            FROM acc_lines l JOIN acc_accounts a ON a.id = l.account_id
            WHERE l.tenant_id = :t AND a.tenant_id = :t AND a.role = :role AND l.party_type = :pt GROUP BY l.party_id),
        p AS (SELECT id, name, COALESCE(balance, 0) AS bal FROM {table} WHERE tenant_id = :t)
        SELECT COALESCE(p.id, led.party_id) AS id, p.name, COALESCE(p.bal, 0) AS operational, COALESCE(led.bal, 0) AS ledger
        FROM p FULL JOIN led ON led.party_id = p.id
        WHERE ABS(COALESCE(p.bal, 0) - COALESCE(led.bal, 0)) >= 0.01
        ORDER BY ABS(COALESCE(p.bal, 0) - COALESCE(led.bal, 0)) DESC LIMIT :lim
    """), {"t": tenant_id, "role": role, "pt": party_type, "sign": sign, "lim": limit})).all()  # noqa: S608 (table from a fixed list)
    return [{"party_type": party_type, "id": r.id, "name": r.name, "ledger": money(r.ledger),
             "operational": money(r.operational), "difference": money(Decimal(r.operational) - Decimal(r.ledger))}
            for r in rows]


async def _role_balance(db: AsyncSession, tenant_id, role: str, sign: int) -> Decimal:
    v = (await db.execute(text(
        "SELECT COALESCE(SUM(l.debit - l.credit), 0) FROM acc_lines l JOIN acc_accounts a ON a.id = l.account_id "
        "WHERE l.tenant_id = :t AND a.tenant_id = :t AND a.role = :role"), {"t": tenant_id, "role": role})).scalar_one()
    return sign * Decimal(v)


async def _money_checks(db: AsyncSession, tenant_id, kind: str, table: str, label: str, label_en: str) -> list[dict]:
    rows = (await db.execute(text(f"""
        SELECT s.id, s.name, COALESCE(s.balance, 0) AS operational,
               COALESCE((SELECT SUM(l.debit - l.credit) FROM acc_lines l WHERE l.tenant_id = :t AND l.account_id = m.account_id), 0) AS ledger
        FROM {table} s LEFT JOIN acc_money_accounts m ON m.tenant_id = :t AND m.kind = :kind AND m.ref_id = s.id
        WHERE s.tenant_id = :t ORDER BY s.name
    """), {"t": tenant_id, "kind": kind})).all()  # noqa: S608 (table from a fixed list)
    return [_check(f"{kind}:{r.id}", f"{label} — {r.name}", f"{label_en} — {r.name}", Decimal(r.ledger), Decimal(r.operational),
                   ref_id=r.id) for r in rows if Decimal(r.operational) or Decimal(r.ledger)]


async def stock_value(db: AsyncSession, tenant_id) -> Decimal:
    """Σ on-hand quantity × the product's average cost (its listed cost while it has no average yet)."""
    v = (await db.execute(text(
        "SELECT COALESCE(SUM(sb.qty * COALESCE(NULLIF(p.avg_cost, 0), p.cost_price, 0)), 0) FROM stock_balances sb "
        "JOIN products p ON p.id = sb.product_id WHERE sb.tenant_id = :t AND p.tenant_id = :t AND sb.qty > 0"),
        {"t": tenant_id})).scalar_one()
    return Decimal(v)


async def reconciliation(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """The ledger against the operational caches, per control account (ADR-014 D8). Only aggregates are
    read. It flags differences and changes nothing; the ledger is the truth. The cashier drawers are
    not compared: a drawer's cash is the open shift's, which the ledger only knows from the opening entry."""
    await load_chart(db, tenant_id)
    customers = Decimal((await db.execute(text(
        "SELECT COALESCE(SUM(balance), 0) FROM customers WHERE tenant_id = :t"), {"t": tenant_id})).scalar_one())
    suppliers = Decimal((await db.execute(text(
        "SELECT COALESCE(SUM(balance), 0) FROM suppliers WHERE tenant_id = :t"), {"t": tenant_id})).scalar_one())
    items = [
        _check("receivables", "العملاء (المدينون) مقابل أرصدة العملاء", "Receivables vs customers' balances",
               await _role_balance(db, tenant_id, "receivables", 1), customers),
        _check("payables", "الموردون (الدائنون) مقابل أرصدة الموردين", "Payables vs suppliers' balances",
               await _role_balance(db, tenant_id, "payables", -1), suppliers),
        *await _money_checks(db, tenant_id, "safe", "safes", "خزنة/بنك", "Safe / bank"),
        *await _money_checks(db, tenant_id, "wallet", "payment_wallets", "محفظة", "Wallet"),
        _check("inventory", "المخزون مقابل قيمة المخزون بمتوسط التكلفة", "Inventory vs stock value at average cost",
               await _role_balance(db, tenant_id, "inventory", 1), await stock_value(db, tenant_id),
               tolerance=INVENTORY_TOLERANCE),
    ]
    parties = [*await _party_differences(db, tenant_id, "customer", "customers", "receivables", 1),
               *await _party_differences(db, tenant_id, "supplier", "suppliers", "payables", -1)]
    return {"as_of": today(), "ok": all(i["ok"] for i in items), "items": items,
            "differences": [i for i in items if not i["ok"]], "parties": parties,
            "note": "للتنبيه فقط: الدفتر هو المرجع، ولا يغيّر هذا الفحص أي رصيد"}
