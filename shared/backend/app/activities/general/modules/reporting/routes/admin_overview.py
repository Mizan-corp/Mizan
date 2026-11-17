"""The company overview: sales and gross profit per branch, stock value, debts, cash. Company-wide, so
it needs `reports:finance` and the right to see every branch."""
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.inventory.models.stock import IN_TYPES
from app.activities.general.modules.reporting import service as rs
from app.activities.general.modules.reporting.scope import FINANCE, company_scope, day_range, today
from app.db.base import get_db
from app.dependencies import require_perm
from app.platform.auth.models.user import User

router = APIRouter(prefix="/admin", tags=["admin"])

D = Decimal
TOP = 10


@router.get("/overview")
async def company_overview(from_date: date | None = None, to_date: date | None = None,
                           db: AsyncSession = Depends(get_db), user: User = Depends(require_perm(FINANCE))):
    await company_scope(db, user)
    fd, td = from_date or today(), to_date or today()
    start, end = day_range(fd, td)
    v = await rs._vat_sql(db)
    params = {"start": start, "end": end}

    # 1. Net sales (less returns, without VAT), their cost and gross profit per branch.
    branches = (await db.execute(text(f"""
        WITH docs AS (
            SELECT s.id, s.warehouse_id, s.is_credit, {rs.SIGN} AS sign, {v['doc']} AS value,
                   (SELECT COALESCE(SUM(si.qty * COALESCE(si.unit_cost, 0)), 0) FROM sale_items si WHERE si.sale_id = s.id) AS cost,
                   s.status
            FROM sales s WHERE {rs.DOCS} AND s.created_at >= :start AND s.created_at < :end
        )
        SELECT w.id, w.name, w.warehouse_type,
               COUNT(d.id) FILTER (WHERE d.status = 'confirmed') AS invoice_count,
               COALESCE(SUM(d.sign * d.value), 0) AS revenue,
               COALESCE(SUM(d.sign * (d.value - d.cost)), 0) AS gross_profit,
               COALESCE(SUM(d.sign * d.value) FILTER (WHERE d.is_credit), 0) AS credit_sales,
               COALESCE(SUM(d.sign * d.value) FILTER (WHERE NOT d.is_credit), 0) AS cash_sales
        FROM warehouses w LEFT JOIN docs d ON d.warehouse_id = w.id
        GROUP BY w.id, w.name, w.warehouse_type
        ORDER BY revenue DESC
    """), params)).mappings().all()
    branches_data = [{**dict(b), **{k: rs.money(b[k]) for k in ("revenue", "gross_profit", "credit_sales", "cash_sales")}}
                     for b in branches]

    # 2. Stock per warehouse at the average cost (the ledger's valuation) and at retail.
    stock = (await db.execute(text("""
        WITH b AS (
            SELECT warehouse_id, product_id,
                   SUM(CASE WHEN CAST(movement_type AS text) = ANY(:ins) THEN qty ELSE -qty END) AS qty
            FROM stock_movements GROUP BY warehouse_id, product_id
        )
        SELECT w.id, w.name, w.warehouse_type,
               COALESCE(SUM(b.qty * COALESCE(NULLIF(p.avg_cost, 0), p.cost_price, 0)), 0) AS stock_cost_value,
               COALESCE(SUM(b.qty * COALESCE(p.retail_price, 0)), 0) AS stock_retail_value,
               COALESCE(SUM(b.qty), 0) AS total_units
        FROM warehouses w LEFT JOIN b ON b.warehouse_id = w.id LEFT JOIN products p ON p.id = b.product_id
        GROUP BY w.id, w.name, w.warehouse_type
        ORDER BY stock_cost_value DESC
    """), {"ins": list(IN_TYPES)})).mappings().all()
    stock_data = [{**dict(s), "stock_cost_value": rs.money(s["stock_cost_value"]),
                   "stock_retail_value": rs.money(s["stock_retail_value"]), "total_units": rs.qty(s["total_units"])}
                  for s in stock]

    # 3. Low stock items (all warehouses together).
    low_stock = (await db.execute(text("""
        SELECT p.name, p.unit, p.reorder_point,
               COALESCE(SUM(CASE WHEN CAST(sm.movement_type AS text) = ANY(:ins) THEN sm.qty ELSE -sm.qty END), 0) AS total_qty
        FROM products p LEFT JOIN stock_movements sm ON sm.product_id = p.id
        WHERE p.is_active = true AND p.reorder_point > 0
        GROUP BY p.id, p.name, p.unit, p.reorder_point
        HAVING COALESCE(SUM(CASE WHEN CAST(sm.movement_type AS text) = ANY(:ins) THEN sm.qty ELSE -sm.qty END), 0) <= p.reorder_point
        ORDER BY total_qty ASC LIMIT :top
    """), {"ins": list(IN_TYPES), "top": TOP})).mappings().all()

    # 4. Customers' open credit invoices: the total over every customer, the ten largest listed.
    debts = """
        SELECT c.id, c.name, c.phone,
               SUM(COALESCE(s.net_total, 0) - COALESCE(s.paid_amount, 0) - COALESCE(s.returns_total, 0)) AS balance_due
        FROM customers c JOIN sales s ON s.customer_id = c.id AND s.is_credit AND s.status = 'confirmed'
        GROUP BY c.id, c.name, c.phone
        HAVING SUM(COALESCE(s.net_total, 0) - COALESCE(s.paid_amount, 0) - COALESCE(s.returns_total, 0)) > 0.005
    """
    customer_debts = (await db.execute(text(f"{debts} ORDER BY balance_due DESC LIMIT :top"), {"top": TOP})).mappings().all()
    total_customer_debt = D((await db.execute(text(f"SELECT COALESCE(SUM(balance_due), 0) FROM ({debts}) x"))).scalar_one())

    # 5. What we owe suppliers.
    supplier_debts = (await db.execute(text(
        "SELECT id, name, phone, balance FROM suppliers WHERE balance > 0 ORDER BY balance DESC LIMIT :top"), {"top": TOP})).mappings().all()
    total_supplier_debt = D((await db.execute(text("SELECT COALESCE(SUM(balance), 0) FROM suppliers WHERE balance > 0"))).scalar_one())

    # 6. Cash in the open drawers: the opening amount, cash sales and deposits in, refunds and the rest out.
    cash = (await db.execute(text("""
        SELECT w.name, s.initial_amount,
               COALESCE((SELECT SUM(CASE WHEN CAST(dt.type AS text) IN ('sale', 'deposit') THEN dt.amount
                                         WHEN CAST(dt.type AS text) IN ('expense', 'withdrawal', 'return_', 'revenue_delivery') THEN -dt.amount
                                         ELSE 0 END)
                         FROM drawer_transactions dt
                         WHERE dt.shift_id = s.id AND dt.cancelled_at IS NULL AND COALESCE(dt.payment_method, 'cash') = 'cash'), 0) AS net_movement
        FROM shifts s JOIN warehouses w ON w.id = s.warehouse_id
        WHERE s.status = 'open'
        ORDER BY w.name
    """))).mappings().all()
    cash_data = [{"name": c["name"], "initial_amount": rs.money(c["initial_amount"]), "net_movement": rs.money(c["net_movement"])}
                 for c in cash]
    total_safes = D((await db.execute(text("SELECT COALESCE(SUM(balance), 0) FROM safes WHERE is_active = true"))).scalar_one())

    total_revenue = sum((D(str(b["revenue"])) for b in branches_data), D(0))
    total_profit = sum((D(str(b["gross_profit"])) for b in branches_data), D(0))
    total_stock_cost = sum((D(str(s["stock_cost_value"])) for s in stock_data), D(0))
    total_stock_retail = sum((D(str(s["stock_retail_value"])) for s in stock_data), D(0))
    total_cash = sum((D(str(c["initial_amount"])) + D(str(c["net_movement"])) for c in cash_data), D(0))

    return {
        "period": {"from": fd.isoformat(), "to": td.isoformat()},
        "summary": {
            "total_revenue": rs.money(total_revenue),
            "total_profit": rs.money(total_profit),
            "profit_margin": round(float(total_profit / total_revenue * 100), 1) if total_revenue > 0 else 0,
            "total_stock_cost": rs.money(total_stock_cost),
            "total_stock_retail": rs.money(total_stock_retail),
            "total_customer_debt": rs.money(total_customer_debt),
            "total_supplier_debt": rs.money(total_supplier_debt),
            "total_cash_in_drawers": rs.money(total_cash),
            "total_safes_balance": rs.money(total_safes),
            # stock + cash + safes + what customers owe - what we owe suppliers
            "net_capital": rs.money(total_stock_cost + total_cash + total_safes + total_customer_debt - total_supplier_debt),
        },
        "branches": branches_data,
        "stock_per_warehouse": [s for s in stock_data if s["stock_cost_value"] > 0],
        "low_stock": [{**dict(r), "total_qty": rs.qty(r["total_qty"])} for r in low_stock],
        "customer_debts": [{**dict(r), "balance_due": rs.money(r["balance_due"])} for r in customer_debts],
        "supplier_debts": [{**dict(r), "balance": rs.money(r["balance"])} for r in supplier_debts],
        "cash_drawers": cash_data,
    }
