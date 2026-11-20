"""The VAT report (ADR-014 D6): output VAT (sales less returns), input VAT (purchases less returns,
and expenses) and what is payable, for a date range, read from the ledger's VAT accounts (roles
`vat_output` and `vat_input`); and, beside it, the same documents' VAT by tax code, read from the
amounts stored on their lines (what an ETA return needs).

Ledger figures follow the posting date and include cancellations (a cancelled sale's reversal takes
its VAT back) and manual entries on the VAT accounts ("other"). The breakdown counts the documents
issued in the range that stand (confirmed sales, return documents, received purchase orders,
purchase returns, approved expenses), by the Cairo date they were issued.
"""
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.accounting.services.chart import ensure_chart
from app.activities.general.modules.accounting.services.reports import money
from app.platform.settings import vat
from app.platform.tenancy.clock import TZ_NAME

ZERO = Decimal("0")
_CAIRO = TZ_NAME


def _range(column: str, date_from: date | None, date_to: date | None, params: dict) -> str:
    sql = ""
    if date_from:
        sql += f" AND {column} >= :df"
        params["df"] = date_from
    if date_to:
        sql += f" AND {column} <= :dt"
        params["dt"] = date_to
    return sql


async def _ledger(db: AsyncSession, tenant_id: uuid.UUID, date_from, date_to) -> list:
    params: dict = {"t": tenant_id}
    where = _range("e.date", date_from, date_to, params)
    return (await db.execute(text(
        "SELECT a.role, e.source_type, to_char(e.date, 'YYYY-MM') AS month, SUM(l.debit) AS d, SUM(l.credit) AS c "
        "FROM acc_lines l JOIN acc_entries e ON e.id = l.entry_id JOIN acc_accounts a ON a.id = l.account_id "
        "WHERE l.tenant_id = :t AND e.tenant_id = :t AND a.role IN ('vat_output', 'vat_input') "
        "AND e.source_type <> 'year_end'" + where + " GROUP BY 1, 2, 3"), params)).all()


def _code_rows(rows) -> list[dict]:
    out = []
    for r in rows:
        out.append({"tax_code": r.tax_code, "label": vat.TAX_LABELS.get(r.tax_code, r.tax_code),
                    "rate": float(vat.tax_rate(r.tax_code)), "taxable": money(r.net), "tax": money(r.tax),
                    "documents": int(r.docs or 0)})
    return sorted(out, key=lambda x: list(vat.TAX_RATES).index(x["tax_code"]) if x["tax_code"] in vat.TAX_RATES else 99)


async def _by_code(db: AsyncSession, tenant_id: uuid.UUID, date_from, date_to) -> dict:
    out = {}
    for key, sql, column in (
        ("sales", "SELECT si.tax_code, SUM(si.net_amount) AS net, SUM(si.tax_amount) AS tax, COUNT(DISTINCT s.id) AS docs "
                  "FROM sale_items si JOIN sales s ON s.id = si.sale_id WHERE s.tenant_id = :t AND si.tax_code IS NOT NULL "
                  "AND s.status = 'confirmed'", f"(s.created_at AT TIME ZONE '{_CAIRO}')::date"),
        ("sale_returns", "SELECT si.tax_code, SUM(si.net_amount) AS net, SUM(si.tax_amount) AS tax, COUNT(DISTINCT s.id) AS docs "
                         "FROM sale_items si JOIN sales s ON s.id = si.sale_id WHERE s.tenant_id = :t AND si.tax_code IS NOT NULL "
                         "AND s.status = 'returned' AND s.return_of IS NOT NULL", f"(s.created_at AT TIME ZONE '{_CAIRO}')::date"),
        # Each goods receipt on its own date (PUR-4); orders received before receipts were kept
        # (no purchase_receipts row) from their lines, on the order's receipt date.
        ("purchases", "SELECT x.tax_code, SUM(x.net) AS net, SUM(x.tax) AS tax, COUNT(DISTINCT x.doc) AS docs FROM ("
                      "SELECT ri.tax_code, ri.net_amount AS net, ri.tax_amount AS tax, r.id AS doc, r.created_at AS at "
                      "FROM purchase_receipt_items ri JOIN purchase_receipts r ON r.id = ri.receipt_id "
                      "WHERE r.tenant_id = :t AND ri.tax_code IS NOT NULL "
                      "UNION ALL SELECT i.tax_code, i.net_amount, i.tax_amount, po.id, po.received_at "
                      "FROM purchase_order_items i JOIN purchase_orders po ON po.id = i.po_id WHERE po.tenant_id = :t "
                      "AND i.tax_code IS NOT NULL AND po.status = 'received' "
                      "AND NOT EXISTS (SELECT 1 FROM purchase_receipts r WHERE r.po_id = po.id)) x WHERE true",
         f"(x.at AT TIME ZONE '{_CAIRO}')::date"),
        ("purchase_returns", "SELECT i.tax_code, SUM(i.net_amount) AS net, SUM(i.tax_amount) AS tax, COUNT(DISTINCT r.id) AS docs "
                             "FROM purchase_return_items i JOIN purchase_returns r ON r.id = i.return_id WHERE r.tenant_id = :t "
                             "AND i.tax_code IS NOT NULL", f"(r.created_at AT TIME ZONE '{_CAIRO}')::date"),
    ):
        params: dict = {"t": tenant_id}
        rows = (await db.execute(text(sql + _range(column, date_from, date_to, params) + " GROUP BY 1"), params)).all()
        out[key] = _code_rows(rows)
    params = {"t": tenant_id}
    exp = (await db.execute(text(
        "SELECT COALESCE(SUM(amount - tax_amount), 0) AS net, COALESCE(SUM(tax_amount), 0) AS tax, COUNT(*) AS docs "
        "FROM expenses WHERE tenant_id = :t AND status = 'approved' AND tax_amount > 0"
        + _range("date", date_from, date_to, params)), params)).one()
    out["expenses"] = {"taxable": money(exp.net), "tax": money(exp.tax), "documents": int(exp.docs or 0)}
    return out


async def vat_report(db: AsyncSession, tenant_id: uuid.UUID, date_from: date | None = None,
                     date_to: date | None = None) -> dict:
    await ensure_chart(db, tenant_id)
    output = dict.fromkeys(("sales", "returns", "other"), ZERO)
    inp = dict.fromkeys(("purchases", "returns", "expenses", "other"), ZERO)
    months: dict[str, dict[str, Decimal]] = {}
    for r in await _ledger(db, tenant_id, date_from, date_to):
        d, c = Decimal(r.d or 0), Decimal(r.c or 0)
        m = months.setdefault(r.month, {"output": ZERO, "input": ZERO})
        if r.role == "vat_output":
            m["output"] += c - d
            if r.source_type == "sale":
                output["sales"] += c - d
            elif r.source_type == "sale_return":
                output["returns"] += d - c
            else:
                output["other"] += c - d
        else:
            m["input"] += d - c
            if r.source_type == "purchase":
                inp["purchases"] += d - c
            elif r.source_type == "purchase_return":
                inp["returns"] += c - d
            elif r.source_type == "expense":
                inp["expenses"] += d - c
            else:
                inp["other"] += d - c
    output_total = output["sales"] - output["returns"] + output["other"]
    input_total = inp["purchases"] - inp["returns"] + inp["expenses"] + inp["other"]
    settings = await vat.vat_settings(db)
    return {
        "from": date_from, "to": date_to,
        "vat_registered": settings.registered, "tax_number": vat.format_tax_number(settings.tax_number),
        "output": {**{k: money(v) for k, v in output.items()}, "total": money(output_total)},
        "input": {**{k: money(v) for k, v in inp.items()}, "total": money(input_total)},
        # Positive: owed to the Tax Authority for the period; negative: a credit carried forward.
        "net_payable": money(output_total - input_total),
        "by_month": [{"month": k, "output": money(v["output"]), "input": money(v["input"]),
                      "net": money(v["output"] - v["input"])} for k, v in sorted(months.items())],
        "by_code": await _by_code(db, tenant_id, date_from, date_to),
    }
