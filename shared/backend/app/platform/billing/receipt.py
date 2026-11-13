"""PDF receipts for paid subscription invoices (#69): what an owner downloads for their records.

Rendered with WeasyPrint, like the sales invoices, using fonts bundled with the backend
(app/platform/printing/fonts, Noto Sans and Noto Sans Arabic, OFL): the cloud functions have
no Arabic fonts of their own. Not an ETA e-invoice (see TASKS.md, ETA integration).
"""
from __future__ import annotations

import asyncio
import html
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.platform.billing.models import BillingInvoice
from app.platform.billing.plans import PLANS_CONFIG

FONTS = Path(__file__).resolve().parent.parent / "printing" / "fonts"
CAIRO = ZoneInfo("Africa/Cairo")
CYCLES = {"monthly": "شهري", "yearly": "سنوي", "annual": "سنوي"}
METHODS = {"card": "بطاقة بنكية", "wallet": "محفظة إلكترونية", "manual": "تحويل / سداد مباشر", "cash": "نقدًا"}


def _date(value: datetime | None) -> str:
    return value.astimezone(CAIRO).strftime("%Y-%m-%d") if value else "—"


def _font_faces() -> str:
    faces = []
    for family, stem in (("Mizan Arabic", "NotoSansArabic"), ("Mizan Latin", "NotoSans")):
        for weight, style in ((400, "Regular"), (700, "Bold")):
            faces.append(f"@font-face {{ font-family: '{family}'; font-weight: {weight}; "
                         f"src: url('{(FONTS / f'{stem}-{style}.ttf').as_uri()}'); }}")
    return "\n".join(faces)


def receipt_html(invoice: BillingInvoice, workspace_name: str, owner_name: str | None) -> str:
    e = lambda v: html.escape(str(v)) if v not in (None, "") else "—"  # noqa: E731
    plan = PLANS_CONFIG.get(invoice.plan, {}).get("name") or invoice.plan
    company = [line.strip() for line in settings.MIZAN_COMPANY_DETAILS.split("|") if line.strip()]
    reference = (invoice.payment_gateway_ref or "").removeprefix("paymob-order:")
    rows = [
        ("مساحة العمل", workspace_name),
        ("الباقة", plan),
        ("دورة الفوترة", CYCLES.get(invoice.billing_cycle, invoice.billing_cycle)),
        ("الفترة", f"من {_date(invoice.period_start)} إلى {_date(invoice.period_end)}"),
        ("طريقة الدفع", METHODS.get(invoice.payment_method, invoice.payment_method)),
        ("مرجع عملية الدفع", reference or None),
    ]
    rows_html = "".join(f"<tr><th>{e(k)}</th><td>{e(v)}</td></tr>" for k, v in rows)
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8"><title>إيصال {e(invoice.invoice_ref)}</title>
<style>
{_font_faces()}
@page {{ size: A4; margin: 18mm 16mm; }}
body {{ font-family: 'Mizan Arabic', 'Mizan Latin', sans-serif; color: #262321; font-size: 12.5px; line-height: 1.7; }}
.top {{ display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #35151D; padding-bottom: 12px; }}
.brand {{ font-size: 24px; font-weight: 700; color: #35151D; }}
.muted {{ color: #77716E; font-size: 11px; }}
h1 {{ font-size: 18px; margin: 18px 0 4px; }}
.paid {{ display: inline-block; background: #E7F4EC; color: #1E6B3A; border-radius: 6px; padding: 1px 10px; font-weight: 700; font-size: 11.5px; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 14px; }}
th, td {{ text-align: start; padding: 8px 10px; border-bottom: 1px solid #EDE6DC; vertical-align: top; }}
th {{ width: 34%; color: #77716E; font-weight: 400; }}
.total {{ margin-top: 18px; display: flex; justify-content: space-between; align-items: baseline; background: #FAF6F0; border: 1px solid #EDE6DC; border-radius: 8px; padding: 12px 14px; }}
.total b {{ font-size: 20px; }}
.ltr {{ direction: ltr; unicode-bidi: embed; font-family: 'Mizan Latin', 'Mizan Arabic', sans-serif; }}
.foot {{ margin-top: 28px; color: #77716E; font-size: 10.5px; }}
</style></head><body>
<div class="top">
  <div><div class="brand">ميزان</div><div class="muted">نظام إدارة الأعمال · <span class="ltr">allmizan.live</span></div>
    {"".join(f'<div class="muted">{e(line)}</div>' for line in company)}</div>
  <div style="text-align:end"><div class="muted">رقم الإيصال</div><div class="ltr" style="font-weight:700">{e(invoice.invoice_ref)}</div>
    <div class="muted" style="margin-top:6px">تاريخ السداد</div><div>{_date(invoice.paid_at)}</div></div>
</div>
<h1>إيصال سداد اشتراك <span class="paid">مدفوع</span></h1>
<div class="muted">صادر إلى: {e(owner_name)}</div>
<table>{rows_html}</table>
<div class="total"><span>المبلغ المدفوع</span><b><span class="ltr">{invoice.amount_egp:,.2f}</span> ج.م</b></div>
<div class="foot">إيصال سداد لاشتراك في منصة ميزان، وليس فاتورة ضريبية إلكترونية. للاستفسار: من لوحة المالك على <span class="ltr">allmizan.live/owner</span>.</div>
</body></html>"""


async def receipt_pdf(invoice: BillingInvoice, workspace_name: str, owner_name: str | None) -> bytes:
    """The receipt as PDF bytes (paid invoices only; the caller checks)."""
    from weasyprint import HTML

    page = receipt_html(invoice, workspace_name, owner_name)
    return await asyncio.get_running_loop().run_in_executor(None, lambda: HTML(string=page).write_pdf())


_PRINT_HELP = """<div class="no-print" style="margin:0 0 18px;padding:10px 14px;border-radius:8px;background:#F5EBDD;font-size:13px">
لحفظ الإيصال ملفًا: اختر «حفظ بصيغة PDF» في نافذة الطباعة.</div>
<style>@media print { .no-print { display: none } }</style>
<script>window.addEventListener("load", () => setTimeout(() => window.print(), 400));</script>"""


async def receipt_file(invoice: BillingInvoice, workspace_name: str, owner_name: str | None) -> tuple[bytes, str, str]:
    """(content, media type, file extension): the PDF, or where WeasyPrint's system libraries
    aren't installed (serverless hosting) the same receipt as a page that opens the print dialog,
    to save as PDF from the browser."""
    try:
        return await receipt_pdf(invoice, workspace_name, owner_name), "application/pdf", "pdf"
    except (OSError, ImportError):
        page = receipt_html(invoice, workspace_name, owner_name).replace("<body>", "<body>" + _PRINT_HELP, 1)
        return page.encode(), "text/html; charset=utf-8", "html"
