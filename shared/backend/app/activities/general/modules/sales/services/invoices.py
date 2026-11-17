"""Invoices: the branded invoice document (HTML, PDF) and sending it by email.

Every text that goes into the document (customer, product, store, branch, user) is HTML-escaped
where it is read: it is rendered by the server's PDF engine, and on servers without one served
as a page from the API's origin."""
import html as _html
import re
import uuid
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.notifications.service import send_email

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


COLOR = re.compile(r"^#[0-9a-fA-F]{3,8}$")


def _esc(v):
    return _html.escape(v) if isinstance(v, str) else v


def _safe_logo(url: str) -> str:
    """Only an https address or one of the app's own paths, escaped (no file:, data: or javascript:)."""
    url = (url or "").strip()
    return _html.escape(url) if url.startswith(("https://", "/")) and not url.startswith("//") else ""


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
    sale = {k: _esc(v) for k, v in sale_row._mapping.items()}

    items_res = await db.execute(text("""
        SELECT si.*, p.name as product_name, p.unit, p.code as product_code
        FROM sale_items si
        JOIN products p ON p.id = si.product_id
        WHERE si.sale_id = :id
        ORDER BY si.id
    """), {"id": invoice_id})
    items = [{k: _esc(v) for k, v in r._mapping.items()} for r in items_res.fetchall()]

    # Fetch store / tenant settings
    store_name = "ميزان لإدارة الموارد"
    store_phone = ""
    store_address = ""
    logo_url = ""
    primary_color = "#0f766e"  # Teal default, when nothing else applies
    explicit_color = False
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
            explicit_color = True

    # Check tenant palette if available
    if tenant_id:
        # The logo is a workspace setting (read above); tenants has no logo column.
        t_row = (await db.execute(text("SELECT name, palette FROM tenants WHERE id = :tid"), {"tid": tenant_id})).fetchone()
        if t_row:
            if t_row.name:
                store_name = t_row.name
        # The workspace theme's brand colour, unless the workspace set a print colour (ADR-010 D3).
        if not explicit_color:
            from app.platform.tenancy.models import Tenant
            from app.platform.themes.service import print_color

            tenant = await db.get(Tenant, tenant_id)
            primary_color = (await print_color(db, tenant) if tenant else None) or primary_color

    store_name, store_phone, store_address, tax_id = map(_esc, (store_name, store_phone, store_address, tax_id))
    logo_url = _safe_logo(logo_url)
    if not COLOR.match(str(primary_color or "")):
        primary_color = "#0f766e"

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


async def render_file(db: AsyncSession, invoice_id: uuid.UUID, tenant_id) -> tuple[bytes, str, str, dict]:
    """(content, media type, extension, sale): the invoice PDF, or a printable page where the
    server can't render PDFs (#118)."""
    from app.platform.printing.fallback import pdf_or_page

    html, sale = await _render_invoice_html(db, invoice_id, tenant_id)
    content, media, ext = await pdf_or_page(html)
    return content, media, ext, sale


async def email_invoice(db: AsyncSession, invoice_id: uuid.UUID, to_email: str | None, subject: str | None, user) -> dict:
    """Email the invoice PDF to the address given. Customers have no email on file, so the address
    must be given; there is no fallback (it used to send to the user or to customer@example.com)."""
    recipient = (to_email or "").strip()
    if not EMAIL.match(recipient):
        raise HTTPException(400, "أدخل بريدًا إلكترونيًا صحيحًا للعميل")
    content, media, ext, sale = await render_file(db, invoice_id, user.tenant_id)
    inv_num = sale.get("invoice_number", str(invoice_id))
    body = f"""
    <div dir="rtl" style="font-family: Arial, sans-serif; line-height: 1.6; color: #1e293b;">
      <h2 style="color: #0f766e;">مرحباً بكم،</h2>
      <p>مرفق طيه فاتورة الشراء الإلكترونية رقم <b>{inv_num}</b> الصادرة بتاريخ {_format_ar_date(sale.get('created_at'))}.</p>
      <p><b>إجمالي المبلغ:</b> {float(sale.get('net_total') or 0):,.2f} ج.م</p>
      <p>شكراً لثقتكم بنا، ونتطلع لخدمتكم دائماً.</p>
    </div>
    """
    res = await send_email(to_email=recipient, subject=subject or f"فاتورة إلكترونية رقم {inv_num} من منصة ميزان",
                           html_content=body,
                           attachments=[{"filename": f"invoice-{inv_num}.{ext}", "content": content, "type": media.split(";")[0]}])
    if not res.get("ok", True):
        raise HTTPException(502, "تعذر إرسال البريد الإلكتروني، حاول مرة أخرى")

    from app.platform.notifications.models.notification import Notification

    tenant_id = user.tenant_id or sale.get("tenant_id")
    if tenant_id:
        db.add(Notification(id=uuid.uuid4(), tenant_id=tenant_id, type="invoice_sent", severity="info",
                            title=f"تم إرسال الفاتورة {inv_num}",
                            body=f"تم إرسال الفاتورة عبر البريد الإلكتروني إلى {recipient}.", link="/sales", is_read=False))
    return {"ok": True, "message": f"تم إرسال الفاتورة {inv_num} بنجاح إلى {recipient}", "provider": res.get("provider")}
