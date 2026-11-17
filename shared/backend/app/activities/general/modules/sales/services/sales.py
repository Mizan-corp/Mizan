import uuid
from datetime import UTC
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BusinessError
from app.activities.general.modules.sales.models.sale import Sale, SaleItem, SaleStatus
from app.activities.general.modules.pos.models import DrawerTransaction, DrawerTxType, Shift
from app.activities.general.modules.inventory.models.stock import MovementType
from app.framework.events import notify
from app.framework.hooks import emit
from app.activities.general.modules.inventory.services.stock import get_balance
from app.activities.general.modules.sales.services import checks


async def _sale_event(db, event: str, sale, lines, **extra) -> list:
    """Webhooks for community modules subscribed to sales (ADR-007), recorded with the change."""
    from app.platform.community.events import publish

    status = getattr(sale.status, "value", sale.status)
    if event == "sale.confirmed" and status != "confirmed":
        return []
    # Modules of the workspace that follow sales (the ledger, ADR-014 D3), in this transaction.
    await notify(event, db, sale=sale, lines=lines, **extra)
    data = {"id": str(sale.id), "invoice_number": sale.invoice_number,
            "customer_id": str(sale.customer_id) if sale.customer_id else None,
            "branch_id": str(sale.warehouse_id) if sale.warehouse_id else None,
            "total": str(sale.total) if sale.total is not None else None,
            "net_total": str(sale.net_total) if sale.net_total is not None else None,
            "is_credit": bool(sale.is_credit),
            "lines": [{"product_id": str(i.product_id), "qty": str(i.qty), "unit_price": str(i.unit_price),
                       "discount": str(getattr(i, "discount", 0) or 0)} for i in lines]}
    if "returned" in extra:
        ret = extra.pop("returned")
        data["return"] = {"id": str(ret.id), "invoice_number": ret.invoice_number,
                          "total": str(ret.net_total if ret.net_total is not None else ret.total)}
    if "returned_total" in extra:
        data["return"] = {"total": str(extra.pop("returned_total"))}
    return await publish(db, event, data)


def _send(ids: list) -> None:
    from app.platform.community.events import deliver_soon

    deliver_soon(ids)


async def _invoice_number(db) -> str:
    """The workspace's next invoice number (PLAT-6: counted per workspace, under a row lock)."""
    from app.platform.archive.numbering import next_number

    return await next_number(db, "INV")


async def _quotation_number(db) -> str:
    from app.platform.archive.numbering import next_number

    return await next_number(db, "QUO")


async def _draft_number(db) -> str:
    """Drafts have numbers of their own: an invoice number is given only when one is confirmed
    (SAL-4: drafts used to take one, and another on confirming)."""
    from app.platform.archive.numbering import next_number

    return await next_number(db, "DRF")


async def _audit(db, actor, entity_type: str, action: str, entity_id, changes: dict | None, note: str) -> None:
    """The audit row, in the document's own transaction (SAL-5: rows written after the
    service's commit were never committed)."""
    from app.platform.audit.service import log as audit_log

    await audit_log(db, entity_type, action, actor.id, getattr(actor, "full_name", None), entity_id, changes, note)


async def _check_stock(db, items, warehouse_id, actor) -> None:
    """Each tracked line is in stock in the branch (balance rows locked, in product order), unless
    the server allows selling below it (SAL-1: never a flag from the client). A shortage that is
    allowed is recorded in the audit log."""
    allowed = None
    for item in sorted(items, key=lambda i: str(i.product_id)):
        if await _is_untracked(db, item.product_id, warehouse_id):
            continue
        balance = await get_balance(db, item.product_id, warehouse_id, for_update=True)
        if balance >= item.qty:
            continue
        name = (await db.execute(text("SELECT name FROM products WHERE id = :id"), {"id": item.product_id})).scalar() \
            or str(item.product_id)
        if allowed is None:
            allowed = await checks.negative_stock_allowed(db, actor)
        if not allowed:
            raise BusinessError(f"المخزون غير كافي لـ {name} (المتاح {balance})")
        await _audit(db, actor, "product", "inventory_discrepancy", item.product_id, {
            "product_name": name, "warehouse_id": str(warehouse_id), "balance_before": float(balance),
            "sold_qty": float(item.qty), "deficit": float(item.qty - balance),
        }, f"بيع بأكثر من الرصيد المتاح لـ {name}")



async def _is_untracked(db, product_id, warehouse_id=None) -> bool:
    from sqlalchemy import text as sqlt
    if warehouse_id:
        wh_row = await db.execute(sqlt(
            "SELECT status FROM warehouse_product_status WHERE product_id=:pid AND warehouse_id=:wid"
        ), {"pid": product_id, "wid": warehouse_id})
        wh_status = wh_row.scalar()
        if wh_status is not None:
            return wh_status != 'tracked'
        return True
    row = await db.execute(sqlt("SELECT stock_status FROM products WHERE id=:id"), {"id": product_id})
    return row.scalar() != 'tracked'

_CENT = Decimal("0.01")


def _d(v) -> Decimal:
    return Decimal(str(v or 0))


async def _apply_vat(db, sale: Sale, items) -> None:
    """The VAT of each line and of the sale (ADR-014 D6), from the products' tax codes now and the
    workspace's settings (app/platform/settings/vat.py): each line gets its code, rate, tax and value
    without VAT, the sale its tax_amount, and net_total becomes what the customer pays. With prices
    including VAT (the default) or no VAT registration that is the same total as before; with prices
    excluding VAT the tax is added on top. Discounts come first (the invoice discount is shared over
    the lines)."""
    from app.platform.settings import vat

    settings = await vat.vat_settings(db)
    codes = await vat.product_tax_codes(db, [i.product_id for i in items]) if settings.registered else {}
    taxes = vat.document_taxes([(_d(i.qty) * _d(i.unit_price) - _d(i.discount), codes.get(i.product_id)) for i in items],
                               _d(sale.discount_amount), settings)
    for item, t in zip(items, taxes, strict=True):
        item.tax_code, item.tax_rate, item.tax_amount, item.net_amount = t.tax_code, t.tax_rate, t.tax, t.net
    sale.tax_amount = sum((t.tax for t in taxes), Decimal("0"))
    if items:
        sale.net_total = sum((t.gross for t in taxes), Decimal("0"))


async def _add_payment(db, sale_id, method: str, amount: Decimal, wallet_id=None, safe_id=None) -> uuid.UUID:
    """One line of how a sale was paid (or, on a return document, refunded). Returns its id."""
    payment_id = uuid.uuid4()
    await db.execute(text(
        "INSERT INTO sale_payments (id, sale_id, method, amount, wallet_id, safe_id) "
        "VALUES (:id, :sid, :m, :amt, :wid, :safe)"
    ), {"id": payment_id, "sid": sale_id, "m": method, "amt": amount, "wid": wallet_id, "safe": safe_id})
    return payment_id


async def _change_customer_balance(db, customer_id, delta: Decimal) -> None:
    """What the customer owes: + for a credit sale, - when it is returned or cancelled. Never
    clamped at zero (SAL-8): below zero we owe the customer, and the ledger's receivables say the
    same."""
    if not customer_id or not delta:
        return
    await db.execute(text("UPDATE customers SET balance = COALESCE(balance,0) + :amt WHERE id = :cid"),
                     {"amt": delta, "cid": customer_id})


async def _check_credit_limit(db, customer_id, amount: Decimal) -> None:
    c = (await db.execute(text("SELECT credit_limit, balance FROM customers WHERE id=:id FOR UPDATE"),
                          {"id": customer_id})).one_or_none()
    if c and c.credit_limit is not None:
        if _d(c.balance) + amount > _d(c.credit_limit):
            remaining = _d(c.credit_limit) - _d(c.balance)
            raise BusinessError(f"تجاوز حد الائتمان (الحد: {c.credit_limit:.2f}, المتبقي: {remaining:.2f})")


async def _record_payments(db, sale: Sale, user_id, payments=None, paid_amount=None) -> None:
    """The money side of a sale being confirmed (POS sale or a draft): its sale_payments lines, the
    cash in the shift's drawer, wallet balances and the customer's balance for the part on credit.
    Bank and cheque lines are recorded (their bank account comes with the ledger, ADR-014 D12)."""
    net_total = _d(sale.net_total)
    shift_id = sale.shift_id
    if payments:
        pmt_sum = sum((_d(p.amount) for p in payments), Decimal("0"))
        if pmt_sum != net_total:
            raise BusinessError(f"مجموع المدفوعات ({pmt_sum}) لا يساوي إجمالي الفاتورة ({net_total})")
        sale.is_credit = any(p.method == "credit" for p in payments)
        sale.payment_method = payments[0].method
        lines = [(p.method, _d(p.amount), p.wallet_id) for p in payments]
    else:
        wallet_id = sale.wallet_id
        if sale.is_credit:
            # A credit sale may take a first payment in cash; the rest goes on the customer's account.
            down = min(_d(paid_amount), net_total) if paid_amount else Decimal("0")
            lines = ([("cash", down, None)] if down > 0 else []) + (
                [("credit", net_total - down, None)] if net_total - down > 0 else [])
        elif wallet_id:
            lines = [("wallet", net_total, wallet_id)]
        else:
            lines = [(sale.payment_method or "cash", net_total, None)]
    paid = Decimal("0")
    for method, amount, wallet_id in lines:
        if method == "wallet" and not wallet_id:
            raise BusinessError("يجب اختيار المحفظة")
        if method == "credit" and not sale.customer_id:
            raise BusinessError("البيع الآجل يتطلب اختيار عميل")
        await _add_payment(db, sale.id, method, amount, wallet_id)
        if method == "cash":
            paid += amount
            if shift_id:
                db.add(DrawerTransaction(
                    shift_id=shift_id, type=DrawerTxType.sale, amount=amount, ref_id=sale.id, created_by=user_id,
                    note=f"قسط نقدي - {sale.invoice_number}" if len(lines) > 1 else None,
                ))
        elif method == "wallet":
            paid += amount
            from app.activities.general.modules.finance.services.wallets import record_wallet_tx
            await record_wallet_tx(db, wallet_id, amount, "sale", sale.id,
                                   f"{'قسط محفظة' if len(lines) > 1 else 'بيع'} - {sale.invoice_number}", user_id)
        elif method == "credit":
            await _check_credit_limit(db, sale.customer_id, amount)
            await _change_customer_balance(db, sale.customer_id, amount)
        else:  # bank, cheque
            paid += amount
    sale.paid_amount = paid


async def create_quotation(db: AsyncSession, data, cashier_id: uuid.UUID, actor=None) -> Sale:
    """Create a quotation (عرض سعر) — no stock deduction, status=quotation. No money moves, so it
    belongs to no shift; its prices follow the same rules as a sale's."""
    actor = await checks.load_actor(db, cashier_id, actor)
    await checks.check_references(db, warehouse_id=data.warehouse_id, customer_id=data.customer_id)
    await checks.check_prices(db, data.items, data.sale_mode, data.discount_amount, actor)
    gross_total, net_total, _ = checks.totals(data.items, data.discount_amount)

    sale = Sale(
        invoice_number=await _quotation_number(db),
        customer_id=data.customer_id,
        warehouse_id=data.warehouse_id,
        cashier_id=cashier_id,
        shift_id=None,
        sale_mode=data.sale_mode,
        discount_amount=data.discount_amount,
        total=Decimal(str(gross_total)),
        net_total=Decimal(str(net_total)),
        notes=data.notes,
        status=SaleStatus.quotation,
        created_by=cashier_id,
    )
    db.add(sale)
    await db.flush()
    lines = [SaleItem(sale_id=sale.id, product_id=item.product_id, qty=item.qty,
                      unit_price=item.unit_price, unit_cost=item.unit_cost, discount=item.discount) for item in data.items]
    db.add_all(lines)
    await _apply_vat(db, sale, lines)
    # Auto-archive within same transaction
    from app.platform.archive.models import ArchivedDocument, DocType
    db.add(ArchivedDocument(doc_number=sale.invoice_number, doc_type=DocType.quotation,
                            ref_id=sale.id, created_by=cashier_id,
                            metadata_={"items_count": len(data.items), "mode": data.sale_mode}))
    await _audit(db, actor, "quotation", "create", sale.id, {"invoice_number": sale.invoice_number,
                                                             "net_total": str(net_total)}, f"عرض سعر {sale.invoice_number}")
    await db.commit()
    result = await db.execute(select(Sale).options(selectinload(Sale.items)).where(Sale.id == sale.id))
    return result.scalar_one()


async def update_quotation(db: AsyncSession, sale_id: uuid.UUID, data, user_id: uuid.UUID | None = None,
                           actor=None) -> None:
    """Edit a quotation. Only what the request contains changes: leaving out items, notes or the
    customer keeps them (it used to clear them). Totals and prices follow create_quotation().
    Commits, with its audit row."""
    from app.core.exceptions import NotFoundError

    row = (await db.execute(text("SELECT status, sale_mode, discount_amount, invoice_number FROM sales "
                                 "WHERE id = :id FOR UPDATE"), {"id": sale_id})).first()
    if row is None:
        raise NotFoundError("عرض السعر غير موجود")
    if row.status != "quotation":
        raise BusinessError("لا يُعدَّل إلا عرض السعر")
    actor = await checks.load_actor(db, user_id or (actor.id if actor else None), actor)
    sent = data.model_fields_set
    if "customer_id" in sent:
        await checks.check_references(db, customer_id=data.customer_id)
    if "items" in sent or "discount_amount" in sent:
        if "items" in sent:
            if not data.items:
                raise BusinessError("عرض السعر يحتاج صنفاً واحداً على الأقل")
            await checks.check_prices(db, data.items, row.sale_mode,
                                      data.discount_amount if "discount_amount" in sent else row.discount_amount, actor)
            await db.execute(text("DELETE FROM sale_items WHERE sale_id = :id"), {"id": sale_id})
            for item in data.items:
                db.add(SaleItem(sale_id=sale_id, product_id=item.product_id, qty=item.qty, unit_price=item.unit_price,
                                unit_cost=item.unit_cost, discount=item.discount))
            await db.flush()
        rows = (await db.execute(text("SELECT qty, unit_price, discount FROM sale_items WHERE sale_id = :id"), {"id": sale_id})).all()
        gross = sum((Decimal(r.qty) * Decimal(r.unit_price) for r in rows), Decimal("0"))
        line_discounts = sum((Decimal(r.discount or 0) for r in rows), Decimal("0"))
        invoice_discount = data.discount_amount if "discount_amount" in sent else Decimal(row.discount_amount or 0)
        if "items" not in sent and invoice_discount > 0 \
                and not await checks.setting_on(db, "sales", "allow_manual_discount", True) \
                and not checks.can(actor, "sales:override_price"):
            raise BusinessError("الخصم اليدوي غير مسموح في إعدادات المبيعات")
        net = gross - line_discounts - invoice_discount
        if net < 0:
            raise BusinessError("الخصم أكبر من إجمالي الفاتورة")
        await db.execute(text("UPDATE sales SET total = :t, net_total = :n, discount_amount = :d WHERE id = :id"),
                         {"t": gross, "n": net, "d": invoice_discount, "id": sale_id})
        sale = (await db.execute(select(Sale).options(selectinload(Sale.items)).where(Sale.id == sale_id)
                                 .execution_options(populate_existing=True))).scalar_one()
        await _apply_vat(db, sale, sale.items)
        await db.flush()
    if "notes" in sent:
        await db.execute(text("UPDATE sales SET notes = :v WHERE id = :id"), {"v": data.notes, "id": sale_id})
    if "customer_id" in sent:
        await db.execute(text("UPDATE sales SET customer_id = :v WHERE id = :id"), {"v": data.customer_id, "id": sale_id})
    await _audit(db, actor, "quotation", "update", sale_id, {"fields": sorted(sent)}, f"تعديل عرض السعر {row.invoice_number}")
    await db.commit()


async def delete_draft_or_quotation(db: AsyncSession, sale_id: uuid.UUID, user_id: uuid.UUID, actor=None) -> None:
    """Delete a draft or a quotation (nothing was taken or paid); confirmed documents are
    cancelled or returned, never deleted. Commits, with its audit row."""
    from app.core.exceptions import NotFoundError

    sale = (await db.execute(select(Sale).where(Sale.id == sale_id).with_for_update())).scalar_one_or_none()
    if not sale:
        raise NotFoundError("الفاتورة غير موجودة")
    if sale.status not in (SaleStatus.draft, SaleStatus.quotation):
        raise BusinessError("لا يُحذف إلا المسودات وعروض الأسعار — الفاتورة المؤكدة تُلغى أو تُرتجع")
    actor = await checks.load_actor(db, user_id, actor)
    await _audit(db, actor, "quotation" if sale.status == SaleStatus.quotation else "sale", "delete", sale_id,
                 {"invoice_number": sale.invoice_number, "status": str(sale.status)}, f"حذف {sale.invoice_number}")
    await db.execute(text("DELETE FROM archived_documents WHERE ref_id=:id AND doc_type IN ('sale_invoice','quotation')"),
                     {"id": sale_id})
    await db.delete(sale)
    await db.commit()


async def confirm_quotation(db: AsyncSession, sale_id: uuid.UUID, user_id: uuid.UUID,
                            destination: str = "drawer", safe_id: uuid.UUID | None = None, actor=None) -> Sale:
    """Convert a quotation to a confirmed sale — deducts stock and records where the money went:
    the user's own open shift in the quotation's branch, a safe (through the finance safes
    service), or the customer's account."""
    result = await db.execute(select(Sale).options(selectinload(Sale.items)).where(Sale.id == sale_id).with_for_update())
    sale = result.scalar_one_or_none()
    if not sale:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("عرض السعر غير موجود")
    if sale.status != SaleStatus.quotation:
        raise BusinessError("لا يُؤكَّد بهذه الطريقة إلا عرض السعر")
    actor = await checks.load_actor(db, user_id, actor)
    quotation_number = sale.invoice_number

    sorted_items = sorted(sale.items, key=lambda i: str(i.product_id))
    await _check_stock(db, sorted_items, sale.warehouse_id, actor)

    await emit("pos.before_confirm", db, sale=sale, lines=sorted_items)
    for item in sorted_items:
        await _take_stock(db, item, sale.warehouse_id, sale.id, user_id)
    await emit("pos.after_confirm", db, sale=sale, lines=sorted_items)

    sale.status = SaleStatus.confirmed
    sale.invoice_number = await _invoice_number(db)
    await _apply_vat(db, sale, sale.items)  # the invoice's VAT is the codes' at the time it is issued
    from app.platform.archive.models import ArchivedDocument, DocType
    doc = ArchivedDocument(
        doc_type=DocType.sale_invoice,
        doc_number=sale.invoice_number,
        amount=sale.net_total,
        ref_id=sale.id,
        created_by=user_id,
    )
    db.add(doc)

    # ── Cash destination: drawer (user's open shift) or safe ─────────────
    net_total = _d(sale.net_total)
    if destination == "credit":
        sale.is_credit = True
        sale.payment_method = "credit"
    if net_total and sale.is_credit:
        if not sale.customer_id:
            raise BusinessError("البيع الآجل يتطلب اختيار عميل")
        await _check_credit_limit(db, sale.customer_id, net_total)
        await _add_payment(db, sale.id, "credit", net_total)
        await _change_customer_balance(db, sale.customer_id, net_total)
        sale.paid_amount = Decimal("0")
    elif net_total:
        if destination == "safe":
            if not safe_id:
                raise BusinessError("يجب اختيار خزنة لإيداع المقبوضات")
            active = (await db.execute(text("SELECT is_active FROM safes WHERE id=:id"), {"id": safe_id})).scalar()
            if not active:
                raise BusinessError("الخزنة غير موجودة")
            from app.activities.general.modules.finance.services import safes as safe_service
            from app.platform.auth.models.user import User

            user = await db.get(User, user_id)
            await safe_service.deposit(db, safe_id, net_total, user, shift_id=sale.shift_id,
                                       warehouse_id=sale.warehouse_id,
                                       notes=f"تأكيد عرض سعر {sale.invoice_number}")
            await _add_payment(db, sale.id, "cash", net_total, safe_id=safe_id)
        else:
            # drawer → user's own open shift in this warehouse (SAL-3)
            shift_id = await checks.sale_shift(db, user_id, sale.warehouse_id, None, cash=True)
            db.add(DrawerTransaction(
                shift_id=shift_id, type=DrawerTxType.sale,
                amount=net_total, ref_id=sale.id, created_by=user_id,
                note=f"تأكيد عرض سعر {sale.invoice_number}",
            ))
            await _add_payment(db, sale.id, "cash", net_total)
            sale.shift_id = shift_id
        sale.paid_amount = net_total

    await _audit(db, actor, "quotation", "confirm", sale.id,
                 {"quotation": quotation_number, "invoice_number": sale.invoice_number, "destination": destination},
                 f"تأكيد عرض السعر {quotation_number} — فاتورة {sale.invoice_number}")
    _hooks = await _sale_event(db, "sale.confirmed", sale, sorted_items)
    await db.commit()
    _send(_hooks)
    await db.refresh(sale)
    return sale


async def create_draft_sale(db: AsyncSession, data, cashier_id: uuid.UUID, actor=None) -> Sale:
    """Create a draft sale — no stock deduction, status=draft, no archive. It takes a draft number
    (DRF-…); the invoice number comes when it is confirmed. Its money goes, when confirmed, into
    the confirming user's own open shift."""
    actor = await checks.load_actor(db, cashier_id, actor)
    await checks.check_references(db, warehouse_id=data.warehouse_id, customer_id=data.customer_id,
                                  wallet_ids=[data.wallet_id])
    if data.shift_id:
        await checks.sale_shift(db, cashier_id, data.warehouse_id, data.shift_id, cash=False, require_setting=False)
    await checks.check_prices(db, data.items, data.sale_mode, data.discount_amount, actor)
    gross_total, net_total, _ = checks.totals(data.items, data.discount_amount)

    sale = Sale(
        invoice_number=await _draft_number(db),
        customer_id=data.customer_id,
        warehouse_id=data.warehouse_id,
        cashier_id=cashier_id,
        shift_id=data.shift_id,
        sale_mode=data.sale_mode,
        discount_amount=data.discount_amount,
        total=Decimal(str(gross_total)),
        net_total=Decimal(str(net_total)),
        paid_amount=Decimal("0"),
        notes=data.notes,
        is_credit=data.is_credit,
        payment_method=data.payment_method,
        wallet_id=data.wallet_id,
        status=SaleStatus.draft,
        created_by=cashier_id,
    )
    db.add(sale)
    await db.flush()
    lines = [SaleItem(sale_id=sale.id, product_id=item.product_id, qty=item.qty, unit_price=item.unit_price,
                      unit_cost=item.unit_cost, discount=item.discount) for item in data.items]
    db.add_all(lines)
    await _apply_vat(db, sale, lines)
    await _audit(db, actor, "sale", "create_draft", sale.id, {"draft_number": sale.invoice_number,
                                                              "net_total": str(sale.net_total)}, f"مسودة {sale.invoice_number}")
    await db.commit()
    result = await db.execute(select(Sale).options(selectinload(Sale.items)).where(Sale.id == sale.id))
    return result.scalar_one()


async def confirm_draft_sale(db: AsyncSession, sale_id: uuid.UUID, user_id: uuid.UUID, actor=None) -> Sale:
    """Convert a draft sale to confirmed — assigns real invoice number, deducts stock. The money
    goes into the confirming user's own open shift in the draft's branch (SAL-3), not the shift
    the draft was saved in (it may be closed, or someone else's)."""
    from app.core.exceptions import NotFoundError
    from app.platform.archive.models import ArchivedDocument, DocType
    result = await db.execute(select(Sale).options(selectinload(Sale.items)).where(Sale.id == sale_id).with_for_update())
    sale = result.scalar_one_or_none()
    if not sale:
        raise NotFoundError("المسودة غير موجودة")
    if sale.status != SaleStatus.draft:
        raise BusinessError("لا يُؤكَّد بهذه الطريقة إلا المسودة")
    actor = await checks.load_actor(db, user_id, actor)
    draft_number = sale.invoice_number
    sale.shift_id = await checks.sale_shift(
        db, user_id, sale.warehouse_id, None,
        cash=checks.cash_involved(is_credit=sale.is_credit, wallet_id=sale.wallet_id, payment_method=sale.payment_method))

    sorted_items = sorted(sale.items, key=lambda i: str(i.product_id))
    await _check_stock(db, sorted_items, sale.warehouse_id, actor)

    await emit("pos.before_confirm", db, sale=sale, lines=sorted_items)
    for item in sorted_items:
        await _take_stock(db, item, sale.warehouse_id, sale.id, user_id)
    await emit("pos.after_confirm", db, sale=sale, lines=sorted_items)

    new_inv = await _invoice_number(db)
    sale.status = SaleStatus.confirmed
    sale.invoice_number = new_inv
    await _apply_vat(db, sale, sale.items)  # the invoice's VAT is the codes' at the time it is issued
    # The money is taken now, as for a POS sale (it used to confirm with nothing recorded).
    await _record_payments(db, sale, user_id)
    db.add(ArchivedDocument(doc_number=new_inv, doc_type=DocType.sale_invoice,
                            amount=sale.net_total, ref_id=sale.id, created_by=user_id,
                            metadata_={"items_count": len(sale.items)}))
    await _audit(db, actor, "sale", "confirm_draft", sale.id, {"draft_number": draft_number, "invoice_number": new_inv},
                 f"تأكيد مسودة {draft_number} — فاتورة {new_inv}")
    _hooks = await _sale_event(db, "sale.confirmed", sale, sorted_items)
    await db.commit()
    _send(_hooks)
    await db.refresh(sale)
    return sale


def _return_lots(item, qty: Decimal, skip: Decimal = Decimal("0")) -> list[tuple[Decimal, dict]]:
    """Returned stock goes back into the batches the line was sold from (in order, after `skip`
    already returned); lines without batches return plain stock."""
    extra = item.extra or {}
    lots = extra.get("batches") or ([{"batch_number": extra["batch_number"], "expiry_date": extra.get("expiry_date"),
                                      "qty": float(item.qty)}] if extra.get("batch_number") else [])
    if not lots:
        return [(qty, {})]
    out, left = [], qty
    for lot in lots:
        room = Decimal(str(lot["qty"]))
        used = min(room, skip)
        skip -= used
        part = min(room - used, left)
        if part > 0:
            out.append((part, {"batch_number": lot["batch_number"], "expiry_date": lot.get("expiry_date")}))
            left -= part
    if left > 0:
        out.append((left, {"batch_number": lots[-1]["batch_number"], "expiry_date": lots[-1].get("expiry_date")}))
    return out


async def _take_stock(db: AsyncSession, item, warehouse_id, sale_id, user_id) -> list:
    """A sale line leaves stock through the one stock path (apply_movement), at the product's
    average cost. The batches it came from (if the workspace tracks batches) are kept on the
    line's extra values."""
    from app.activities.general.modules.inventory.services.stock import apply_movement

    mv, lots = await apply_movement(
        db, product_id=item.product_id, warehouse_id=warehouse_id, movement_type=MovementType.sale,
        qty=item.qty, unit_price=item.unit_price, created_by=user_id,
        ref_id=sale_id, ref_type="sale", sale_id=sale_id,
    )
    # The cost of the line is the product's average cost now, never what the client sent (D5).
    item.unit_cost = mv.unit_cost
    if lots and hasattr(item, "extra"):
        first = lots[0]
        item.extra = {**(item.extra or {}), "batch_number": first.get("batch_number"),
                      "expiry_date": first.get("expiry_date"),
                      **({"batches": [{"batch_number": x.get("batch_number"), "expiry_date": x.get("expiry_date"),
                                       "qty": float(x["qty"])} for x in lots]} if len(lots) > 1 else {})}
    return lots


async def _sale_with_items(db, sale_id) -> Sale:
    return (await db.execute(select(Sale).options(selectinload(Sale.items)).where(Sale.id == sale_id))).scalar_one()


async def create_sale(db: AsyncSession, data, cashier_id: uuid.UUID, actor=None) -> Sale:
    """A confirmed sale (POS). The server decides everything the client used to (SAL-1): prices,
    discounts and stock follow the workspace's settings and the user's permissions; the money
    goes into the user's own open shift in the sale's branch (SAL-3). A sale sent again with the
    same `local_id` (the POS's offline queue, a retry) is the sale recorded the first time (SAL-2)."""
    from app.platform.tenancy.context import current_tenant_id

    actor = await checks.load_actor(db, cashier_id, actor)
    tid = current_tenant_id.get()
    if not tid and actor.tenant_id:
        tid = actor.tenant_id
        current_tenant_id.set(tid)

    local_id = data.local_id
    if local_id:
        # Two copies of one sale arriving at once wait for each other; the second finds the first.
        await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
                         {"k": f"sale-local:{tid}:{cashier_id}:{local_id}"})
        existing = (await db.execute(select(Sale.id).where(Sale.cashier_id == cashier_id, Sale.local_id == local_id))).scalar()
        if existing:
            await db.commit()
            return await _sale_with_items(db, existing)

    # Sort items by product_id to prevent deadlocks (consistent lock ordering)
    sorted_items = sorted(data.items, key=lambda i: str(i.product_id))
    payments = data.payments or None
    await checks.check_references(db, warehouse_id=data.warehouse_id, customer_id=data.customer_id,
                                  wallet_ids=[data.wallet_id, *[p.wallet_id for p in payments or []]])
    await checks.check_prices(db, sorted_items, data.sale_mode, data.discount_amount, actor)
    checks.totals(sorted_items, data.discount_amount)
    shift_id = await checks.sale_shift(db, cashier_id, data.warehouse_id, data.shift_id, cash=checks.cash_involved(
        payments=payments, is_credit=data.is_credit, paid_amount=data.paid_amount, wallet_id=data.wallet_id,
        payment_method=data.payment_method))
    await _check_stock(db, sorted_items, data.warehouse_id, actor)

    sale = Sale(
        invoice_number=await _invoice_number(db),
        tenant_id=tid,
        local_id=local_id,
        customer_id=data.customer_id,
        warehouse_id=data.warehouse_id,
        cashier_id=cashier_id,
        shift_id=shift_id,
        sale_mode=data.sale_mode,
        discount_amount=data.discount_amount,
        is_credit=data.is_credit,
        payment_method=getattr(data, 'payment_method', 'cash') or 'cash',
        wallet_id=getattr(data, 'wallet_id', None),
        notes=data.notes or None,
        status=SaleStatus.confirmed,
        created_by=cashier_id,
    )
    if getattr(data, "extra", None):
        from app.framework.fields import clean_extra
        from app.framework.hooks import workspace_activity

        sale.extra = await clean_extra(db, "sale", data.extra, await workspace_activity(db), partial=True)
    db.add(sale)
    await db.flush()

    gross_total = Decimal("0")
    total_discount = Decimal("0")
    sale_items: list[SaleItem] = []
    for item in sorted_items:
        si = SaleItem(
            sale_id=sale.id,
            product_id=item.product_id,
            qty=item.qty,
            unit_price=item.unit_price,
            unit_cost=Decimal("0"),  # set from the average cost when the stock leaves (ADR-014 D5)
            discount=item.discount,
        )
        sale_items.append(si)
        gross_total += Decimal(str(item.qty)) * Decimal(str(item.unit_price))
        total_discount += Decimal(str(item.discount))


    db.add_all(sale_items)
    await db.flush()
    # The activity's sale rules (ADR-006 phase 4): e.g. a pharmacy's prescription checks.
    await emit("pos.before_confirm", db, sale=sale, lines=sale_items)
    for si in sale_items:
        await _take_stock(db, si, data.warehouse_id, sale.id, cashier_id)
    await emit("pos.after_confirm", db, sale=sale, lines=sale_items)

    net_total = gross_total - total_discount - Decimal(str(data.discount_amount))
    sale.total = Decimal(str(gross_total))
    sale.net_total = Decimal(str(net_total))
    await _apply_vat(db, sale, sale_items)
    await _record_payments(db, sale, cashier_id, payments=getattr(data, "payments", None),
                           paid_amount=getattr(data, "paid_amount", None))

    # Auto-archive within the same transaction
    from app.platform.archive.models import ArchivedDocument, DocType
    db.add(ArchivedDocument(doc_number=sale.invoice_number, doc_type=DocType.sale_invoice,
                            amount=sale.net_total, ref_id=sale.id, created_by=cashier_id,
                            metadata_={"items_count": len(data.items), "mode": str(data.sale_mode)}))

    await _audit(db, actor, "sale", "create", sale.id, {"invoice_number": sale.invoice_number, "total": float(sale.total),
                                                        "net_total": float(sale.net_total)}, f"فاتورة {sale.invoice_number}")
    _hooks = await _sale_event(db, "sale.confirmed", sale, sale_items)
    await db.commit()
    _send(_hooks)
    return await _sale_with_items(db, sale.id)


# ── Returns and cancellations (ADR-014 D4) ────────────────────────────────────────────────────
# A return is its own document: a Sale with status 'returned', number RET-…, `return_of` pointing to
# the sale, its own lines, totals and refund lines (sale_payments). The sale itself stays
# 'confirmed' and its returns_total grows. Cancelling keeps every payment row and reverses the money.


async def _payment_lines(db, sale: Sale) -> list[tuple[str, Decimal, uuid.UUID | None, uuid.UUID | None]]:
    """How a sale was paid: (method, amount, wallet_id, safe_id) from its sale_payments lines, or,
    for sales from before those were kept, what the sale's own fields say."""
    rows = (await db.execute(text(
        "SELECT method, wallet_id, safe_id, SUM(amount) AS amt FROM sale_payments WHERE sale_id = :sid "
        "GROUP BY method, wallet_id, safe_id ORDER BY method"
    ), {"sid": sale.id})).all()
    lines = [(r.method, _d(r.amt), r.wallet_id, r.safe_id) for r in rows if _d(r.amt) > 0]
    if lines:
        return lines
    net = _d(sale.net_total)
    if not net:
        return []
    if sale.is_credit:
        return [("credit", net, None, None)]
    if sale.wallet_id:
        return [("wallet", net, sale.wallet_id, None)]
    return [(sale.payment_method or "cash", net, None, None)]


async def _returned_qty(db, sale_id) -> dict[str, Decimal]:
    rows = (await db.execute(text(
        "SELECT si.product_id, SUM(si.qty) AS qty FROM sale_items si JOIN sales r ON r.id = si.sale_id "
        "WHERE r.return_of = :sid AND r.status = 'returned' GROUP BY si.product_id"
    ), {"sid": sale_id})).all()
    return {str(r.product_id): _d(r.qty) for r in rows}


async def _refunded(db, sale_id) -> dict[tuple, Decimal]:
    rows = (await db.execute(text(
        "SELECT sp.method, sp.wallet_id, SUM(sp.amount) AS amt FROM sale_payments sp "
        "JOIN sales r ON r.id = sp.sale_id WHERE r.return_of = :sid AND r.status = 'returned' "
        "GROUP BY sp.method, sp.wallet_id"
    ), {"sid": sale_id})).all()
    return {(r.method, r.wallet_id): _d(r.amt) for r in rows}


async def _open_shift_for_refund(db, user_id, wanted, sale: Sale):
    """The drawer cash refunds come out of: the user's own open shift in the sale's branch (the one
    asked for must be that). Never another cashier's shift (SAL-7), never a closed one."""
    if wanted:
        shift = (await db.execute(select(Shift).where(Shift.id == wanted).with_for_update(read=True))).scalar_one_or_none()
        if shift is None:
            from app.core.exceptions import NotFoundError
            raise NotFoundError("الوردية غير موجودة")
        if shift.cashier_id != user_id or shift.status != "open" or shift.warehouse_id != sale.warehouse_id:
            raise BusinessError("يُصرف المرتجع من ورديتك المفتوحة في فرع الفاتورة فقط")
        return shift.id
    return (await db.execute(
        select(Shift.id).where(Shift.cashier_id == user_id, Shift.warehouse_id == sale.warehouse_id,
                               Shift.status == "open")
        .order_by(Shift.started_at.desc()).limit(1).with_for_update(read=True)
    )).scalar_one_or_none()


async def _make_return(db, orig: Sale, wanted: dict[str, Decimal] | None, user_id, shift_id=None) -> tuple[Sale, bool]:
    """Return `wanted` (product id → qty) of a confirmed sale, or everything not returned yet when
    `wanted` is None. Creates the return document, puts the stock back at the cost it left at,
    refunds each payment method in proportion (the last return refunds exactly what is left) and
    adds to the sale's returns_total. Returns (the return document, whether the sale is now fully
    returned)."""
    from app.platform.archive.models import ArchivedDocument, DocType
    from app.activities.general.modules.inventory.services.stock import apply_movement

    if orig.return_of is not None or orig.status != SaleStatus.confirmed:
        raise BusinessError("لا يمكن إرجاع إلا فاتورة مؤكدة")

    returned = await _returned_qty(db, orig.id)
    left_wanted = dict(wanted) if wanted is not None else None
    lines: list[tuple[SaleItem, Decimal, Decimal]] = []  # (sale line, qty returned now, qty returned before)
    fully = True
    for oi in sorted(orig.items, key=lambda i: (str(i.product_id), str(i.id))):
        pid, sold = str(oi.product_id), _d(oi.qty)
        before = min(sold, returned.get(pid, Decimal("0")))
        returned[pid] = returned.get(pid, Decimal("0")) - before
        room = sold - before
        if left_wanted is None:
            qty = room
        else:
            qty = min(room, left_wanted.get(pid, Decimal("0")))
            left_wanted[pid] = left_wanted.get(pid, Decimal("0")) - qty
        if qty > 0:
            lines.append((oi, qty, before))
        if room - qty > 0:
            fully = False
    for pid, rest in (left_wanted or {}).items():
        if rest > 0:
            name = (await db.execute(text("SELECT name FROM products WHERE id = :id"), {"id": pid})).scalar() or pid
            room = sum((_d(i.qty) for i in orig.items if str(i.product_id) == pid), Decimal("0"))
            room -= (await _returned_qty(db, orig.id)).get(pid, Decimal("0"))
            raise BusinessError(f"الكمية المرتجعة ({wanted[pid]}) تتجاوز المتبقي القابل للإرجاع ({max(room, Decimal('0'))}) للمنتج {name}")
    if not lines:
        raise BusinessError("أُرجعت كل أصناف هذه الفاتورة من قبل")

    # Amounts on net: each line's own discount pro rata, then its share of the invoice discount.
    gross = sum((q * _d(oi.unit_price) for oi, q, _ in lines), Decimal("0"))
    line_disc = sum(((_d(oi.discount) * q / _d(oi.qty)).quantize(_CENT) for oi, q, _ in lines), Decimal("0"))
    before_invoice_discount = _d(orig.total) - sum((_d(i.discount) for i in orig.items), Decimal("0"))
    inv_share = Decimal("0")
    if _d(orig.discount_amount) and before_invoice_discount > 0:
        inv_share = (_d(orig.discount_amount) * (gross - line_disc) / before_invoice_discount).quantize(_CENT)
    net = gross - line_disc - inv_share
    # A sale issued with VAT data (ADR-014 D6): each returned line takes its part of what the original
    # line cost and of its tax, in proportion to the quantity (never the product's code today), so
    # returning everything gives back exactly the sale's total and its VAT.
    vat_doc = any(oi.tax_code is not None for oi in orig.items)
    from app.platform.settings.vat import portion

    taxes: list[tuple[Decimal, Decimal]] = []  # (tax, value without VAT) per returned line
    if vat_doc:
        for oi, q, before in lines:
            pay = portion(_d(oi.net_amount) + _d(oi.tax_amount), before, q, _d(oi.qty))
            tax = portion(_d(oi.tax_amount), before, q, _d(oi.qty))
            taxes.append((tax, pay - tax))
        net = sum((t + n for t, n in taxes), Decimal("0"))
    elif fully:
        # The last return refunds exactly what is left of the sale (no rounding drift).
        net = _d(orig.net_total) - _d(orig.returns_total)
        inv_share = gross - line_disc - net
    if net < 0:
        net = Decimal("0")

    # Refund each way the sale was paid, in proportion.
    paid_by: dict[tuple, Decimal] = {}
    for method, amt, wallet_id, _safe in await _payment_lines(db, orig):
        paid_by[(method, wallet_id)] = paid_by.get((method, wallet_id), Decimal("0")) + amt
    refunded = await _refunded(db, orig.id)
    ratio = net / _d(orig.net_total) if _d(orig.net_total) > 0 else Decimal("0")
    refunds: dict[tuple, Decimal] = {}
    for key, amt in paid_by.items():
        left = max(amt - refunded.get(key, Decimal("0")), Decimal("0"))
        refunds[key] = left if fully else min(left, (amt * ratio).quantize(_CENT))
    diff = net - sum(refunds.values(), Decimal("0"))
    if diff and refunds:
        for key in sorted(refunds, key=lambda k: paid_by[k], reverse=True):
            left = paid_by[key] - refunded.get(key, Decimal("0")) - refunds[key]
            step = min(diff, left) if diff > 0 else max(diff, -refunds[key])
            refunds[key] += step
            diff -= step
            if not diff:
                break

    cash_refund = sum((v for (m, _), v in refunds.items() if m == "cash"), Decimal("0"))
    target_shift = await _open_shift_for_refund(db, user_id, shift_id, orig)
    # Cash that went through a drawer comes back out of one; a sale made without a shift
    # recorded no drawer cash, so its refund records none either.
    if cash_refund > 0 and not target_shift and orig.shift_id:
        raise BusinessError("لا توجد وردية مفتوحة لك في فرع الفاتورة لصرف المبلغ النقدي للمرتجع — افتح وردية أولاً")

    from app.platform.archive.numbering import next_number

    first = next((k for k, v in refunds.items() if v > 0), None)
    ret = Sale(
        invoice_number=await next_number(db, "RET"), return_of=orig.id,
        customer_id=orig.customer_id, warehouse_id=orig.warehouse_id, cashier_id=user_id, created_by=user_id,
        shift_id=target_shift or orig.shift_id, sale_mode=orig.sale_mode, status=SaleStatus.returned,
        total=gross, discount_amount=inv_share, net_total=net, paid_amount=net, returns_total=Decimal("0"),
        tax_amount=sum((t for t, _ in taxes), Decimal("0")),
        is_credit=any(m == "credit" and v > 0 for (m, _), v in refunds.items()),
        payment_method=first[0] if first else (orig.payment_method or "cash"),
        wallet_id=next((w for (m, w), v in refunds.items() if m == "wallet" and v > 0), None),
        notes=f"مرتجع {'كامل' if fully and not any(b for _, _, b in lines) else 'جزئي'} من {orig.invoice_number}",
    )
    db.add(ret)
    await db.flush()

    for n, (oi, qty, before) in enumerate(lines):
        tax, value = taxes[n] if vat_doc else (Decimal("0"), None)
        db.add(SaleItem(sale_id=ret.id, product_id=oi.product_id, qty=qty, unit_price=oi.unit_price,
                        unit_cost=oi.unit_cost, discount=(_d(oi.discount) * qty / _d(oi.qty)).quantize(_CENT),
                        tax_code=oi.tax_code, tax_rate=_d(oi.tax_rate), tax_amount=tax, net_amount=value))
        # Back into stock at the cost the line left at, into the batches it came from.
        for part, lot in _return_lots(oi, qty, skip=before):
            await apply_movement(db, product_id=oi.product_id, warehouse_id=orig.warehouse_id,
                                 movement_type=MovementType.return_in, qty=part, unit_cost=oi.unit_cost,
                                 unit_price=oi.unit_price, created_by=user_id, ref_id=ret.id,
                                 ref_type="return", sale_id=ret.id, lot=lot or None)

    note = f"مرتجع {ret.invoice_number} من {orig.invoice_number}"
    for (method, wallet_id), amount in refunds.items():
        if amount <= 0:
            continue
        await _add_payment(db, ret.id, method, amount, wallet_id)
        if method == "cash" and target_shift:
            db.add(DrawerTransaction(shift_id=target_shift, type=DrawerTxType.return_, amount=amount,
                                     ref_id=ret.id, created_by=user_id, note=note))
        elif method == "wallet" and wallet_id:
            from app.activities.general.modules.finance.services.wallets import record_wallet_tx
            await record_wallet_tx(db, wallet_id, -amount, "return", ret.id, note, user_id)
        elif method == "credit":
            await _change_customer_balance(db, orig.customer_id, -amount)
        # bank / cheque refunds are recorded on the return; their bank account comes with the ledger.

    orig.returns_total = _d(orig.returns_total) + net
    db.add(ArchivedDocument(doc_number=ret.invoice_number, doc_type=DocType.sale_invoice, amount=net,
                            ref_id=ret.id, created_by=user_id,
                            metadata_={"original_invoice": orig.invoice_number, "type": "return"}))
    return ret, fully


async def return_sale(db: AsyncSession, sale_id: uuid.UUID, user_id: uuid.UUID, shift_id: uuid.UUID | None = None,
                      actor=None) -> dict:
    """Full return: everything on the sale not returned yet goes into one return document."""
    sale = (await db.execute(select(Sale).options(selectinload(Sale.items)).where(Sale.id == sale_id)
                             .with_for_update())).scalar_one_or_none()
    if not sale:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("الفاتورة غير موجودة")
    actor = await checks.load_actor(db, user_id, actor)
    ret, _ = await _make_return(db, sale, None, user_id, shift_id)
    await _audit(db, actor, "sale", "return", sale.id, {"return": ret.invoice_number, "amount": str(ret.net_total)},
                 f"إرجاع فاتورة {sale.invoice_number} — {ret.invoice_number}")
    _hooks = await _sale_event(db, "sale.returned", sale, [], returned=ret)
    await db.commit()
    _send(_hooks)
    return {"detail": "Returned", "invoice_number": sale.invoice_number, "amount": ret.net_total,
            "doc_number": ret.invoice_number, "sale_id": str(ret.id)}


async def partial_return_sale(db: AsyncSession, sale_id: uuid.UUID, data: dict, current_user_id: uuid.UUID,
                              actor=None) -> dict:
    orig = (await db.execute(select(Sale).options(selectinload(Sale.items)).where(Sale.id == sale_id)
                             .with_for_update())).scalar_one_or_none()
    if not orig:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("الفاتورة غير موجودة")
    wanted: dict[str, Decimal] = {}
    for i in data.get("items", []):
        wanted[str(i["product_id"])] = wanted.get(str(i["product_id"]), Decimal("0")) + _d(i["qty"])
    if not wanted:
        raise BusinessError("اختر صنفاً واحداً على الأقل للإرجاع")
    actor = await checks.load_actor(db, current_user_id, actor)
    ret, _ = await _make_return(db, orig, wanted, current_user_id, data.get("shift_id"))
    await _audit(db, actor, "sale", "partial_return", orig.id,
                 {"return": ret.invoice_number, "amount": str(ret.net_total),
                  "items": {k: str(v) for k, v in wanted.items()}},
                 f"مرتجع جزئي {ret.invoice_number} من {orig.invoice_number}")
    _hooks = await _sale_event(db, "sale.returned", orig, [], returned=ret)
    await db.commit()
    _send(_hooks)
    return {"doc_number": ret.invoice_number, "sale_id": str(ret.id), "total": float(ret.net_total),
            "original": orig.invoice_number}


async def cancel_sale(db: AsyncSession, sale_id: uuid.UUID, user_id: uuid.UUID, actor=None) -> Sale:
    """Cancel a confirmed sale. Nothing is deleted: the sale becomes 'cancelled', its stock comes
    back, its drawer rows are cancelled (taking the cash out of the shift), wallet and safe
    payments are paid back out and the part on credit comes off the customer's balance. Its
    sale_payments and customer_payments rows stay (reports only count confirmed sales)."""
    from datetime import datetime

    from app.activities.general.modules.inventory.services.stock import apply_movement

    sale = (await db.execute(select(Sale).where(Sale.id == sale_id).with_for_update())).scalar_one_or_none()
    if not sale:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("الفاتورة غير موجودة")
    if sale.status != SaleStatus.confirmed or sale.return_of is not None:
        raise BusinessError("لا يُلغى إلا فاتورة مؤكدة")
    if sale.returns_total and Decimal(str(sale.returns_total)) > 0:
        raise BusinessError("تم إرجاع أجزاء من هذه الفاتورة مسبقاً — لا يمكن إلغاء الفاتورة")

    closed_msg = ("لا يمكن إلغاء فاتورة تابعة لوردية مغلقة. يرجى استخدام مرتجع المبيعات بدلاً من الإلغاء "
                  "للحفاظ على السجل المالي للوردية")
    # BIZ-02: a closed shift's history is never changed.
    if sale.shift_id:
        shift = await db.get(Shift, sale.shift_id)
        if shift and shift.status == "closed":
            raise BusinessError(closed_msg)
    drawer_rows = (await db.execute(select(DrawerTransaction).where(
        DrawerTransaction.ref_id == sale_id, DrawerTransaction.cancelled_at.is_(None)))).scalars().all()
    for row in drawer_rows:
        shift = await db.get(Shift, row.shift_id)
        if shift and shift.status == "closed":
            raise BusinessError(closed_msg)

    sale.status = SaleStatus.cancelled
    note = f"إلغاء فاتورة {sale.invoice_number}"

    # Stock back, at the cost each line left at.
    items = (await db.execute(select(SaleItem).where(SaleItem.sale_id == sale_id))).scalars().all()
    for item in items:
        extra = item.extra or {}
        # Back into the batches the line was taken from (pharmacies), else plain stock.
        lots = extra.get("batches") or ([{"batch_number": extra["batch_number"], "expiry_date": extra.get("expiry_date"),
                                          "qty": item.qty}] if extra.get("batch_number") else [None])
        for lot in lots:
            await apply_movement(db, product_id=item.product_id, warehouse_id=sale.warehouse_id,
                                 movement_type=MovementType.return_in, qty=lot["qty"] if lot else item.qty,
                                 unit_cost=item.unit_cost, unit_price=item.unit_price, ref_id=sale_id,
                                 ref_type="sale_cancel", sale_id=sale_id, created_by=user_id, lot=lot)

    # Cash in a drawer: its rows are cancelled, so the shift no longer expects that cash.
    now = datetime.now(UTC)
    for row in drawer_rows:
        row.cancelled_at = now
        row.cancelled_by = user_id

    for method, amount, wallet_id, safe_id in await _payment_lines(db, sale):
        if method == "wallet" and wallet_id:
            from app.activities.general.modules.finance.services.wallets import record_wallet_tx
            await record_wallet_tx(db, wallet_id, -amount, "sale_cancelled", sale.id, note, user_id)
        elif method == "credit":
            await _change_customer_balance(db, sale.customer_id, -amount)
        elif safe_id:
            from app.activities.general.modules.finance.services import safes as safe_service
            from app.platform.auth.models.user import User

            await safe_service.withdraw(db, safe_id, amount, note, await db.get(User, user_id))
        # cash through a drawer: handled above; bank / cheque: recorded only, nothing to move back yet.

    await _audit(db, await checks.load_actor(db, user_id, actor), "sale", "cancel", sale.id,
                 {"invoice_number": sale.invoice_number, "net_total": str(sale.net_total)}, note)
    await notify("sale.cancelled", db, sale=sale, user_id=user_id)
    await db.commit()
    await db.refresh(sale)
    return sale


_NO_EDIT = "لا يمكن تعديل فاتورة مؤكدة — لتصحيحها استخدم المرتجع (الجزئي أو الكامل) أو ألغِ الفاتورة"


async def _refuse_item_edit(db: AsyncSession, sale_id: uuid.UUID, item_id: uuid.UUID, other_msg: str):
    """Confirmed sales are not edited (ADR-014 D4): a change to what was sold is a return."""
    from app.core.exceptions import ConflictError, NotFoundError

    status = (await db.execute(text(
        "SELECT s.status FROM sale_items si JOIN sales s ON s.id = si.sale_id WHERE si.id = :iid AND si.sale_id = :sid"
    ), {"iid": item_id, "sid": sale_id})).scalar()
    if status is None:
        raise NotFoundError("البند غير موجود")
    if status == "confirmed":
        raise ConflictError(_NO_EDIT)
    raise BusinessError(other_msg)


async def update_sale_item_qty(db: AsyncSession, sale_id: uuid.UUID, item_id: uuid.UUID, data, current_user_id: uuid.UUID, current_user_full_name: str) -> dict:
    """Refused: a confirmed sale's quantities are corrected with a return; quotations are edited
    with PUT /sales/{id}."""
    await _refuse_item_edit(db, sale_id, item_id, "لا يمكن تعديل فاتورة ملغاة أو مرتجعة")


async def delete_sale_item(db: AsyncSession, sale_id: uuid.UUID, item_id: uuid.UUID, current_user_id: uuid.UUID) -> dict:
    """Refused: removing a line from a confirmed sale is a partial return."""
    await _refuse_item_edit(db, sale_id, item_id, "لا يمكن حذف بند من فاتورة ملغاة أو مرتجعة")
