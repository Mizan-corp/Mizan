"""Pharmacy: the formulary, batches, prescriptions and the controlled-drug register.

One system with the rest of the ERP (ADR-006 phase 4): a drug is a product with the inventory
pharmacy variant's fields (scientific name, form, strength, prescription, controlled); its stock
is kept in batches (the `batches` module); dispensing is a sale made at the POS (pharmacy
variant), which records the prescription and the controlled-drug log. The pharmacy's older own
tables (pharmacy_drugs, pharmacy_batches) are kept read-only; v63 moved their data here.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import require_perm

router = APIRouter(prefix="/pharmacy", tags=["Pharmacy Module"])

DRUG_SQL = """
    SELECT p.id, p.name AS trade_name, p.code, p.barcode, p.retail_price AS unit_price, p.unit,
           p.extra->>'scientific_name' AS scientific_name, p.extra->>'dosage_form' AS dosage_form,
           p.extra->>'strength' AS strength,
           COALESCE((p.extra->>'requires_prescription')::boolean, false) AS requires_prescription,
           COALESCE((p.extra->>'is_controlled')::boolean, false) AS is_controlled,
           COALESCE((SELECT sum(l.qty) FROM batches_lots l WHERE l.product_id = p.id AND l.status = 'active'
                     AND (l.expiry_date IS NULL OR l.expiry_date >= CURRENT_DATE)), 0) AS sellable_qty,
           COALESCE((SELECT sum(b.qty) FROM stock_balances b WHERE b.product_id = p.id), 0) AS stock_qty,
           (SELECT min(l.expiry_date) FROM batches_lots l WHERE l.product_id = p.id AND l.qty > 0
                AND l.expiry_date >= CURRENT_DATE) AS nearest_expiry
    FROM products p
"""


class CreateDrugRequest(BaseModel):
    trade_name: str = Field(min_length=1, max_length=256)
    scientific_name: str = ""
    dosage_form: str | None = None
    strength: str = ""
    code: str | None = None
    barcode: str | None = None
    unit_price: Decimal = Field(default=Decimal("0"), ge=0)
    is_controlled: bool = False
    requires_prescription: bool = False


class ReceiveBatchRequest(BaseModel):
    product_id: uuid.UUID
    warehouse_id: uuid.UUID
    batch_number: str = Field(min_length=1, max_length=64)
    expiry_date: date
    quantity: Decimal = Field(gt=0)
    purchase_cost: Decimal = Field(default=Decimal("0"), ge=0)
    supplier_name: str | None = None


@router.get("/summary")
async def summary(db: AsyncSession = Depends(get_db), _=Depends(require_perm("inventory", "pos"))):
    row = (await db.execute(text("""
        SELECT
          (SELECT count(*) FROM products WHERE is_active AND extra ? 'scientific_name') AS drugs,
          (SELECT count(*) FROM products WHERE is_active AND (extra->>'requires_prescription')::boolean) AS prescription_only,
          (SELECT count(*) FROM products WHERE is_active AND (extra->>'is_controlled')::boolean) AS controlled,
          (SELECT count(*) FROM batches_lots WHERE qty > 0 AND expiry_date < CURRENT_DATE) AS expired_batches,
          (SELECT count(*) FROM batches_lots WHERE qty > 0 AND expiry_date >= CURRENT_DATE
                AND expiry_date <= CURRENT_DATE + 90) AS expiring_batches,
          (SELECT count(*) FROM pharmacy_prescriptions WHERE dispensed_at >= CURRENT_DATE) AS prescriptions_today
    """))).mappings().one()
    return dict(row)


@router.get("/drugs")
async def list_drugs(search: str | None = None, db: AsyncSession = Depends(get_db),
                     _=Depends(require_perm("inventory", "pos"))):
    """The formulary: products with drug details, their sellable stock and nearest expiry."""
    where = "WHERE p.is_active AND (p.extra ? 'scientific_name' OR p.extra ? 'requires_prescription')"
    params: dict = {}
    if search:
        where += " AND (p.name ILIKE :s OR p.extra->>'scientific_name' ILIKE :s OR p.barcode = :b OR p.code ILIKE :s)"
        params = {"s": f"%{search}%", "b": search}
    rows = (await db.execute(text(DRUG_SQL + where + " ORDER BY p.name LIMIT 300"), params)).mappings().all()
    return [dict(r) for r in rows]


@router.post("/drugs", status_code=201)
async def create_drug(data: CreateDrugRequest, db: AsyncSession = Depends(get_db), user=Depends(require_perm("inventory"))):
    """A new drug is a product (in the 'أدوية' category) with the pharmacy's product fields."""
    from app.activities.general.modules.inventory.schemas.product import ProductCreate
    from app.activities.general.modules.inventory.services.products import create_product

    sub_id = await _drug_subcategory(db)
    extra = {"scientific_name": data.scientific_name, "dosage_form": data.dosage_form, "strength": data.strength,
             "requires_prescription": data.requires_prescription or data.is_controlled,
             "is_controlled": data.is_controlled}
    product = await create_product(db, ProductCreate(
        subcategory_id=sub_id, name=data.trade_name.strip(), code=data.code or None, barcode=data.barcode or None,
        retail_price=data.unit_price, extra={k: v for k, v in extra.items() if v not in ("", None)},
    ), user.id)
    return {"id": str(product.id), "trade_name": product.name}


async def _drug_subcategory(db: AsyncSession) -> uuid.UUID:
    sub = await db.scalar(text("""
        SELECT s.id FROM subcategories s JOIN categories c ON c.id = s.category_id
        WHERE c.name = 'أدوية' ORDER BY s.name LIMIT 1
    """))
    if sub:
        return sub
    cat = await db.scalar(text("SELECT id FROM categories WHERE name = 'أدوية'"))
    if not cat:
        cat = await db.scalar(text("INSERT INTO categories (id, name) VALUES (gen_random_uuid(), 'أدوية') RETURNING id"))
    return await db.scalar(text(
        "INSERT INTO subcategories (id, category_id, name) VALUES (gen_random_uuid(), :c, 'عام') RETURNING id"), {"c": cat})


@router.get("/drugs/{product_id}/alternatives")
async def alternatives(product_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                       _=Depends(require_perm("inventory", "pos"))):
    """Other products with the same scientific name (same active ingredient), cheapest first."""
    base = (await db.execute(text(DRUG_SQL + " WHERE p.id = :id"), {"id": product_id})).mappings().first()
    if not base:
        raise HTTPException(404, "الدواء غير موجود")
    if not base["scientific_name"]:
        return {"drug": dict(base), "alternatives": []}
    rows = (await db.execute(text(DRUG_SQL + """
        WHERE p.is_active AND p.id <> :id AND lower(p.extra->>'scientific_name') = lower(:sci)
        ORDER BY p.retail_price
    """), {"id": product_id, "sci": base["scientific_name"]})).mappings().all()
    return {"drug": dict(base), "alternatives": [dict(r) for r in rows]}


@router.get("/batches")
async def list_batches(db: AsyncSession = Depends(get_db), _=Depends(require_perm("inventory", "pos"))):
    """Batches with stock, soonest expiry first (the batches module's data)."""
    rows = (await db.execute(text("""
        SELECT l.id, l.product_id, p.name AS trade_name, p.extra->>'scientific_name' AS scientific_name,
               l.warehouse_id, w.name AS warehouse_name, l.batch_number, l.expiry_date, l.qty AS quantity_on_hand,
               l.unit_cost AS purchase_cost, l.status, (l.expiry_date - CURRENT_DATE) AS days_left
        FROM batches_lots l JOIN products p ON p.id = l.product_id JOIN warehouses w ON w.id = l.warehouse_id
        WHERE l.qty > 0 ORDER BY l.expiry_date NULLS LAST, p.name LIMIT 500
    """))).mappings().all()
    return [dict(r) for r in rows]


@router.post("/batches", status_code=201)
async def receive_batch(data: ReceiveBatchRequest, db: AsyncSession = Depends(get_db), user=Depends(require_perm("inventory"))):
    """Stock arrives as a batch: a purchase movement through the one stock path."""
    from app.activities.general.modules.inventory.models.stock import MovementType
    from app.activities.general.modules.inventory.services.stock import apply_movement

    _, lots = await apply_movement(
        db, product_id=data.product_id, warehouse_id=data.warehouse_id, movement_type=MovementType.purchase,
        qty=data.quantity, unit_cost=data.purchase_cost, created_by=user.id, ref_type="pharmacy_receipt",
        note=f"استلام تشغيلة {data.batch_number}" + (f" من {data.supplier_name}" if data.supplier_name else ""),
        lot={"batch_number": data.batch_number.strip(), "expiry_date": data.expiry_date},
    )
    await db.commit()
    return {"batch_number": data.batch_number, "lots": [{**x, "qty": float(x["qty"])} for x in lots]}


@router.get("/prescriptions")
async def list_prescriptions(limit: int = Query(200, le=1000), db: AsyncSession = Depends(get_db),
                             _=Depends(require_perm("pos", "sales"))):
    """Prescriptions dispensed, newest first, with the invoice that dispensed them."""
    rows = (await db.execute(text("""
        SELECT rx.id, rx.rx_number, rx.patient_name, rx.patient_national_id, rx.doctor_name, rx.doctor_license,
               rx.total_amount, rx.status, rx.dispensed_at, rx.sale_id, s.invoice_number
        FROM pharmacy_prescriptions rx LEFT JOIN sales s ON s.id = rx.sale_id
        ORDER BY rx.dispensed_at DESC LIMIT :n
    """), {"n": limit})).mappings().all()
    return [dict(r) for r in rows]


@router.post("/prescriptions")
@router.post("/prescriptions/dispense")
async def dispense_moved():
    """Dispensing is a sale now, so stock, cash and finance stay in one system (ADR-006 phase 4)."""
    raise HTTPException(410, "الصرف يتم الآن من نقطة البيع: أضف الدواء للفاتورة وأدخل بيانات الروشتة")


@router.get("/controlled")
@router.get("/controlled-log")
async def controlled_register(limit: int = Query(300, le=2000), db: AsyncSession = Depends(get_db),
                              _=Depends(require_perm("inventory", "pos"))):
    """The controlled-drug register: every dispense with patient, prescriber and batch."""
    rows = (await db.execute(text("""
        SELECT c.id, c.logged_at, COALESCE(p.name, d.trade_name) AS trade_name, c.batch_number, c.quantity,
               c.patient_name, c.patient_national_id, c.prescriber_doctor, c.doctor_license, c.transaction_type,
               c.notes, s.invoice_number
        FROM pharmacy_controlled_logs c
        LEFT JOIN products p ON p.id = c.product_id
        LEFT JOIN pharmacy_drugs d ON d.id = c.drug_id
        LEFT JOIN sales s ON s.id = c.sale_id
        ORDER BY c.logged_at DESC LIMIT :n
    """), {"n": limit})).mappings().all()
    return [dict(r) for r in rows]
