"""v63: the pharmacy's own drugs and batches join the rest of the ERP (ADR-006 phase 4e).

Per workspace:
- each pharmacy_drugs row becomes a product (matched by barcode, then exact name, else created in
  the 'أدوية' category), with the inventory pharmacy variant's fields in products.extra;
- each pharmacy_batches row with stock becomes an opening-stock movement and, in workspaces whose
  inventory runs the pharmacy variant, a batch (lot) with its expiry;
- in those workspaces, stock that existed before batches were tracked gets a lot "—" (no batch),
  so lots add up to stock and it stays sellable;
- the controlled-drug log points at the products; pharmacy workspaces get the batches module.
The old tables stay (read-only). Idempotent: mapped drugs and migrated batches are skipped.
"""
import json
import uuid
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.framework import variants

NO_BATCH = "—"


async def _drug_subcategory(db: AsyncSession, tid) -> uuid.UUID:
    sub = await db.scalar(text("""
        SELECT s.id FROM subcategories s JOIN categories c ON c.id = s.category_id
        WHERE c.tenant_id = :t AND c.name = 'أدوية' ORDER BY s.name LIMIT 1
    """), {"t": tid})
    if sub:
        return sub
    cat = await db.scalar(text("SELECT id FROM categories WHERE tenant_id = :t AND name = 'أدوية'"), {"t": tid})
    if not cat:
        cat = await db.scalar(text("INSERT INTO categories (id, name, tenant_id) VALUES (gen_random_uuid(), 'أدوية', :t) RETURNING id"), {"t": tid})
    return await db.scalar(text(
        "INSERT INTO subcategories (id, category_id, name, tenant_id) VALUES (gen_random_uuid(), :c, 'عام', :t) RETURNING id"
    ), {"c": cat, "t": tid})


async def _balance(db: AsyncSession, tid, product_id, warehouse_id, delta) -> None:
    await db.execute(text("""
        INSERT INTO stock_balances (product_id, warehouse_id, qty, tenant_id, updated_at) VALUES (:p, :w, :q, :t, now())
        ON CONFLICT (product_id, warehouse_id) DO UPDATE SET qty = stock_balances.qty + EXCLUDED.qty, updated_at = now()
    """), {"p": product_id, "w": warehouse_id, "q": delta, "t": tid})


async def _lot(db: AsyncSession, tid, product_id, warehouse_id, batch, expiry, qty, cost, movement_id=None) -> None:
    lot_id = await db.scalar(text("""
        INSERT INTO batches_lots (id, tenant_id, product_id, warehouse_id, batch_number, expiry_date, qty, unit_cost)
        VALUES (gen_random_uuid(), :t, :p, :w, :b, :e, :q, :c)
        ON CONFLICT (tenant_id, product_id, warehouse_id, batch_number) DO UPDATE SET qty = batches_lots.qty + EXCLUDED.qty
        RETURNING id
    """), {"t": tid, "p": product_id, "w": warehouse_id, "b": batch, "e": expiry, "q": qty, "c": cost})
    if movement_id:
        await db.execute(text("""
            INSERT INTO batches_lot_movements (id, tenant_id, lot_id, movement_id, qty) VALUES (gen_random_uuid(), :t, :l, :m, :q)
        """), {"t": tid, "l": lot_id, "m": movement_id, "q": qty})


async def migrate(db: AsyncSession) -> None:
    await db.execute(text("ALTER TABLE pharmacy_drugs ADD COLUMN IF NOT EXISTS product_id uuid REFERENCES products(id) ON DELETE SET NULL"))
    tenants = (await db.execute(text("""
        SELECT id, sector, active_modules FROM tenants t
        WHERE EXISTS (SELECT 1 FROM pharmacy_drugs d WHERE d.tenant_id = t.id) OR sector IS NOT NULL
    """))).all()
    for tid, sector, active in tenants:
        tracks = variants.variant_of("inventory", sector) == "pharmacy"
        drugs = (await db.execute(text("SELECT * FROM pharmacy_drugs WHERE tenant_id = :t AND product_id IS NULL"),
                                  {"t": tid})).mappings().all()
        for d in drugs:
            product = await db.scalar(text("""
                SELECT id FROM products WHERE tenant_id = :t AND ((:b <> '' AND barcode = :b) OR name = :n) LIMIT 1
            """), {"t": tid, "b": d["barcode"] or "", "n": d["trade_name"]})
            extra = {k: v for k, v in {
                "scientific_name": d["scientific_name"], "dosage_form": d["dosage_form"], "strength": d["strength"],
                "requires_prescription": bool(d["requires_prescription"] or d["is_controlled"]),
                "is_controlled": bool(d["is_controlled"]),
            }.items() if v not in (None, "")}
            if product is None:
                product = await db.scalar(text("""
                    INSERT INTO products (id, tenant_id, subcategory_id, name, code, barcode, unit, retail_price,
                                          wholesale_price, cost_price, is_active, extra)
                    VALUES (gen_random_uuid(), :t, :s, :n, NULL, NULLIF(:b, ''), 'عدد', :price, :price, 0, true, CAST(:x AS jsonb))
                    RETURNING id
                """), {"t": tid, "s": await _drug_subcategory(db, tid), "n": d["trade_name"], "b": d["barcode"] or "",
                       "price": d["unit_price"] or 0, "x": json.dumps(extra, ensure_ascii=False)})
            else:
                await db.execute(text("UPDATE products SET extra = extra || CAST(:x AS jsonb) WHERE id = :p"),
                                 {"x": json.dumps(extra, ensure_ascii=False), "p": product})
            await db.execute(text("UPDATE pharmacy_drugs SET product_id = :p WHERE id = :d"), {"p": product, "d": d["id"]})

        warehouse = await db.scalar(text("SELECT id FROM warehouses WHERE tenant_id = :t ORDER BY is_active DESC, created_at LIMIT 1"),
                                    {"t": tid})
        if warehouse:
            batches = (await db.execute(text("""
                SELECT b.*, d.product_id FROM pharmacy_batches b JOIN pharmacy_drugs d ON d.id = b.drug_id
                WHERE b.tenant_id = :t AND b.quantity_on_hand > 0 AND d.product_id IS NOT NULL
                  AND NOT EXISTS (SELECT 1 FROM stock_movements m WHERE m.ref_type = 'pharmacy_migration' AND m.ref_id::text = b.id)
            """), {"t": tid})).mappings().all()
            for b in batches:
                movement = await db.scalar(text("""
                    INSERT INTO stock_movements (id, tenant_id, product_id, warehouse_id, movement_type, qty, unit_cost,
                                                 unit_price, ref_id, ref_type, note)
                    VALUES (gen_random_uuid(), :t, :p, :w, 'opening_stock', :q, :c, 0, CAST(:ref AS uuid), 'pharmacy_migration', :note)
                    RETURNING id
                """), {"t": tid, "p": b["product_id"], "w": warehouse, "q": b["quantity_on_hand"], "c": b["purchase_cost"] or 0,
                       "ref": b["id"], "note": f"نقل تشغيلة {b['batch_number']} من سجل الصيدلية"})
                await _balance(db, tid, b["product_id"], warehouse, b["quantity_on_hand"])
                if tracks:
                    expiry = date.fromisoformat(str(b["expiry_date"])[:10]) if b["expiry_date"] else None
                    await _lot(db, tid, b["product_id"], warehouse, b["batch_number"], expiry,
                               b["quantity_on_hand"], b["purchase_cost"], movement)

        if tracks:
            # Stock from before batches were tracked: a lot "—" so lots == stock and it stays sellable.
            gaps = (await db.execute(text("""
                SELECT sb.product_id, sb.warehouse_id, sb.qty - COALESCE(sum(l.qty), 0) AS gap
                FROM stock_balances sb
                LEFT JOIN batches_lots l ON l.product_id = sb.product_id AND l.warehouse_id = sb.warehouse_id
                WHERE sb.tenant_id = :t GROUP BY sb.product_id, sb.warehouse_id, sb.qty
                HAVING sb.qty - COALESCE(sum(l.qty), 0) > 0
            """), {"t": tid})).all()
            for product_id, warehouse_id, gap in gaps:
                await _lot(db, tid, product_id, warehouse_id, NO_BATCH, None, gap, None)
            modules = list(active or [])
            if "batches" not in modules:
                await db.execute(text("UPDATE tenants SET active_modules = CAST(:m AS jsonb) WHERE id = :t"),
                                 {"m": json.dumps(modules + ["batches"]), "t": tid})

        await db.execute(text("""
            UPDATE pharmacy_controlled_logs c SET product_id = d.product_id
            FROM pharmacy_drugs d WHERE d.id = c.drug_id AND c.product_id IS NULL AND c.tenant_id = :t
        """), {"t": tid})
