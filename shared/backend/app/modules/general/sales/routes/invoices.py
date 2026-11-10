"""
Invoices API Router:
Branded PDF generation (GET /invoices/{id}/pdf) and Email Delivery (POST /invoices/{id}/send).
"""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.platform.notifications.service import send_email

router = APIRouter(prefix="/invoices", tags=["invoices"])


class SendInvoiceEmailIn(BaseModel):
    email: str | None = None
    subject: str | None = None


def _format_ar_date(dt_val) -> str:
    try:
        if isinstance(dt_val, str):
            dt_val = datetime.fromisoformat(dt_val)
        return dt_val.strftime("%Y/%m/%d %I:%M %p").replace("AM", "ص").replace("PM", "م")
    except Exception:
        return str(dt_val or "")


async def _render_invoice_html(db: AsyncSession, invoice_id: uuid.UUID, tenant_id: uuid.UUID | None) -> tuple[str, dict]:
    """Fetch invoice data and render branded Arabic RTL invoice HTML."""
    row = await db.execute(text("""
        SELECT sa.*, c.name as customer_name, c.phone as customer_phone, c.address as customer_address,
               w.name as warehouse_name, u.full_name as created_by_name,
               cashier.full_name as cashier_name
        FROM sales sa
        LEFT JOIN customers c ON c.id = sa.customer_id
        LEFT JOIN warehouses w ON w.id = sa.warehouse_id
        LEFT JOIN users u ON u.id = sa.created_by
        LEFT JOIN users cashier ON cashier.id = sa.cashier_id
        WHERE sa.id = :id
    """), {"id": invoice_id})
    sale_row = row.fetchone()
    if not sale_row:
        raise HTTPException(404, "الفاتورة غير موجودة")
    sale = dict(sale_row._mapping)

    items_res = await db.execute(text("""
        SELECT si.*, p.name as product_name, p.unit, p.code as product_code
        FROM sale_items si
        JOIN products p ON p.id = si.product_id
        WHERE si.sale_id = :id
        ORDER BY si.id
    """), {"id": invoice_id})
    items = [dict(r._mapping) for r in items_res.fetchall()]

    # Fetch store / tenant settings
    store_name = "ميزان لإدارة الموارد"
    store_phone = ""
    store_address = ""
    logo_url = ""
    primary_color = "#0f766e"  # Teal / emerald default
    tax_id = ""

    # Check store settings
    s_rows = await db.execute(text("SELECT key, value FROM store_settings"))
    for r in s_rows.fetchall():
        if r.key == "store_name" and r.value:
            store_name = r.value
        elif r.key == "store_phone" and r.value:
            store_phone = r.value
        elif r.key == "store_address" and r.value:
            store_address = r.value
        elif r.key == "logo_url" and r.value:
            logo_url = r.value
        elif r.key == "tax_number" and r.value:
            tax_id = r.value
        elif r.key == "primary_color" and r.value:
            primary_color = r.value

    # Check tenant palette if available
    if tenant_id:
        # The logo is a workspace setting (read above); tenants has no logo column.
        t_row = (await db.execute(text("SELECT name, palette FROM tenants WHERE id = :tid"), {"tid": tenant_id})).fetchone()
        if t_row:
            if t_row.name:
                store_name = t_row.name
            if t_row.palette and isinstance(t_row.palette, dict) and t_row.palette.get("name"):
                pal = t_row.palette.get("name")
                if pal == "indigo":
                    primary_color = "#4f46e5"
                elif pal == "blue":
                    primary_color = "#2563eb"
                elif pal == "violet":
                    primary_color = "#7c3aed"
                elif pal == "emerald":
                    primary_color = "#059669"

    # Compute calculations
    gross_total = float(sale.get("total") or 0)
    net_total = float(sale.get("net_total") or gross_total)
    discount = gross_total - net_total if gross_total > net_total else 0.0
    tax_amount = round(net_total * 0.14 / 1.14, 2)  # Included standard 14% VAT estimate

    items_html_rows = ""
    for idx, it in enumerate(items, 1):
        it_qty = float(it.get("qty") or 0)
        it_price = float(it.get("unit_price") or 0)
        it_disc = float(it.get("discount") or 0)
        it_total = (it_qty * it_price) - it_disc
        items_html_rows += f"""
        <tr>
          <td style="text-align: center;">{idx}</td>
          <td><b>{it.get('product_name', '')}</b> {f"<span style='color:#666;'>({it.get('product_code')})</span>" if it.get('product_code') else ""}</td>
          <td style="text-align: center;">{it_qty:g} {it.get('unit', '')}</td>
          <td style="text-align: end;">{it_price:,.2f} ج.م</td>
          <td style="text-align: end;">{it_disc:,.2f} ج.م</td>
          <td style="text-align: end; font-weight: bold;">{it_total:,.2f} ج.م</td>
        </tr>
        """

    logo_img = f'<img src="{logo_url}" alt="Logo" style="max-height: 56px; max-width: 140px; object-fit: contain;" />' if logo_url else f'<div style="font-size: 20px; font-weight: 900; color: {primary_color};">{store_name}</div>'

    html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8">
  <title>فاتورة ضريبية - {sale.get('invoice_number')}</title>
  <style>
    @page {{ size: A4 portrait; margin: 12mm; }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Segoe UI', Tahoma, Arial, sans-serif; font-size: 13px; color: #111; line-height: 1.5; direction: rtl; }}
    .header {{ display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid {primary_color}; padding-bottom: 12px; margin-bottom: 16px; }}
    .company-title {{ font-size: 20px; font-weight: 800; color: {primary_color}; }}
    .company-sub {{ font-size: 11px; color: #64748b; margin-top: 2px; }}
    .invoice-badge {{ text-align: left; direction: ltr; }}
    .invoice-title {{ font-size: 18px; font-weight: 800; color: #0f172a; }}
    .invoice-meta {{ font-size: 12px; color: #475569; margin-top: 3px; }}
    .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }}
    .card {{ border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px 12px; background: #f8fafc; }}
    .card-title {{ font-weight: 700; font-size: 12px; color: #334155; margin-bottom: 6px; border-bottom: 1px solid #cbd5e1; padding-bottom: 4px; }}
    .card-row {{ display: flex; justify-content: space-between; margin-bottom: 3px; font-size: 12px; }}
    .items-table {{ width: 100%; border-collapse: collapse; margin-bottom: 16px; font-size: 12px; }}
    .items-table th {{ background: #f1f5f9; color: #1e293b; border: 1px solid #cbd5e1; padding: 8px 10px; font-weight: 700; text-align: right; }}
    .items-table td {{ border: 1px solid #e2e8f0; padding: 7px 10px; text-align: right; }}
    .items-table tr:nth-child(even) {{ background: #fafafa; }}
    .totals-box {{ width: 340px; margin-right: auto; border: 1px solid #cbd5e1; border-radius: 6px; overflow: hidden; margin-top: 10px; }}
    .total-row {{ display: flex; justify-content: space-between; padding: 6px 12px; border-bottom: 1px solid #e2e8f0; font-size: 12px; }}
    .total-grand {{ background: #f0fdf4; font-weight: 800; font-size: 15px; color: {primary_color}; border-bottom: none; }}
    .footer {{ margin-top: 32px; text-align: center; font-size: 11px; color: #94a3b8; border-top: 1px dashed #cbd5e1; padding-top: 10px; }}
  </style>
</head>
<body>
  <div class="header">
    <div>
      {logo_img}
      <div class="company-sub">{store_address} {f"| هاتف: {store_phone}" if store_phone else ""} {f"| س.ت: {tax_id}" if tax_id else ""}</div>
    </div>
    <div class="invoice-badge">
      <div class="invoice-title">فاتورة بيع رسمية</div>
      <div class="invoice-meta">رقم الفاتورة: <b>{sale.get('invoice_number')}</b></div>
      <div class="invoice-meta">التاريخ: {_format_ar_date(sale.get('created_at'))}</div>
    </div>
  </div>

  <div class="grid-2">
    <div class="card">
      <div class="card-title">بيانات العميل</div>
      <div class="card-row"><span>الاسم:</span> <strong>{sale.get('customer_name') or 'عميل نقدي'}</strong></div>
      <div class="card-row"><span>رقم الهاتف:</span> <span>{sale.get('customer_phone') or '—'}</span></div>
      <div class="card-row"><span>العنوان:</span> <span>{sale.get('customer_address') or '—'}</span></div>
    </div>
    <div class="card">
      <div class="card-title">تفاصيل العملية والوردية</div>
      <div class="card-row"><span>الفرع / المستودع:</span> <strong>{sale.get('warehouse_name') or 'المركز الرئيسي'}</strong></div>
      <div class="card-row"><span>الكاشير:</span> <span>{sale.get('cashier_name') or sale.get('created_by_name') or '—'}</span></div>
      <div class="card-row"><span>طريقة الدفع:</span> <strong>{'نقدي' if sale.get('payment_method') == 'cash' else 'آجل' if sale.get('is_credit') else sale.get('payment_method') or 'نقدي'}</strong></div>
    </div>
  </div>

  <table class="items-table">
    <thead>
      <tr>
        <th style="width: 35px; text-align: center;">#</th>
        <th>الصنف / البيان</th>
        <th style="width: 85px; text-align: center;">الكمية</th>
        <th style="width: 100px; text-align: end;">السعر</th>
        <th style="width: 85px; text-align: end;">الخصم</th>
        <th style="width: 110px; text-align: end;">الإجمالي</th>
      </tr>
    </thead>
    <tbody>
      {items_html_rows}
    </tbody>
  </table>

  <div class="totals-box">
    <div class="total-row"><span>المجموع الفرعي:</span> <span>{gross_total:,.2f} ج.م</span></div>
    {f'<div class="total-row"><span>إجمالي الخصم:</span> <span>{discount:,.2f} ج.م</span></div>' if discount > 0 else ''}
    <div class="total-row"><span>شامل ضريبة القيمة المضافة:</span> <span>{tax_amount:,.2f} ج.م</span></div>
    <div class="total-row total-grand"><span>الصافي النهائي:</span> <span>{net_total:,.2f} ج.م</span></div>
  </div>

  <div class="footer">
    شكراً لتعاملكم معنا • تُعتبر هذه الفاتورة سند استلام نظامي للبضاعة المبينة أعلاه • صادر عبر منصة Mizan ERP
  </div>
</body>
</html>"""
    return html, sale


@router.get("/{invoice_id}/pdf")
async def get_invoice_pdf(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate and return styled branded PDF for an invoice."""
    import asyncio
    from weasyprint import HTML

    html, sale = await _render_invoice_html(db, invoice_id, current_user.tenant_id)
    loop = asyncio.get_running_loop()
    pdf_bytes = await loop.run_in_executor(None, lambda: HTML(string=html).write_pdf())

    inv_num = sale.get("invoice_number", str(invoice_id))
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="invoice-{inv_num}.pdf"',
        },
    )


@router.post("/{invoice_id}/send")
async def send_invoice_email(
    invoice_id: uuid.UUID,
    data: SendInvoiceEmailIn = SendInvoiceEmailIn(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send branded invoice PDF to customer via email."""
    import asyncio
    from weasyprint import HTML
    from app.models.notification import Notification

    html, sale = await _render_invoice_html(db, invoice_id, current_user.tenant_id)
    loop = asyncio.get_running_loop()
    pdf_bytes = await loop.run_in_executor(None, lambda: HTML(string=html).write_pdf())

    recipient = data.email or sale.get("customer_phone")
    if not recipient or "@" not in recipient:
        recipient = current_user.username if "@" in current_user.username else "customer@example.com"

    inv_num = sale.get("invoice_number", str(invoice_id))
    subject = data.subject or f"فاتورة إلكترونية رقم {inv_num} من منصة ميزان"

    email_body = f"""
    <div dir="rtl" style="font-family: Arial, sans-serif; line-height: 1.6; color: #1e293b;">
      <h2 style="color: #0f766e;">مرحباً بكم،</h2>
      <p>مرفق طيه فاتورة الشراء الإلكترونية رقم <b>{inv_num}</b> الصادرة بتاريخ {_format_ar_date(sale.get('created_at'))}.</p>
      <p><b>إجمالي المبلغ:</b> {float(sale.get('net_total') or 0):,.2f} ج.م</p>
      <p>شكراً لثقتكم بنا، ونتطلع لخدمتكم دائماً.</p>
    </div>
    """

    res = await send_email(
        to_email=recipient,
        subject=subject,
        html_content=email_body,
        attachments=[
            {
                "filename": f"invoice-{inv_num}.pdf",
                "content": pdf_bytes,
                "type": "application/pdf",
            }
        ],
    )

    # In-app notification
    t_id = current_user.tenant_id or sale.get("tenant_id")
    if t_id:
        notif = Notification(
            id=uuid.uuid4(),
            tenant_id=t_id,
            type="invoice_sent",
            severity="info",
            title=f"تم إرسال الفاتورة {inv_num}",
            body=f"تم إرسال الفاتورة عبر البريد الإلكتروني إلى {recipient}.",
            link="/sales",
            is_read=False,
        )
        db.add(notif)
        await db.commit()

    return {
        "ok": True,
        "message": f"تم إرسال الفاتورة {inv_num} بنجاح إلى {recipient}",
        "provider": res.get("provider"),
    }
