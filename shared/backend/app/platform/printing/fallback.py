"""PDFs where the server can render them, a printable page where it can't (#118).

WeasyPrint needs pango and cairo. Mizan's server image has them; an on-site install whose machine
lacks them would answer 500 for every PDF. Instead it gets the same document as a page that opens
the print dialog, to save as PDF from the browser (as receipts already do, #69).
"""
from __future__ import annotations

PRINT_HELP = """<div class="no-print" style="margin:0 0 18px;padding:10px 14px;border-radius:8px;background:#F5EBDD;font-size:13px;font-family:Tahoma,Arial,sans-serif" dir="rtl">
لحفظ المستند ملفًا: اختر «حفظ بصيغة PDF» في نافذة الطباعة.</div>
<style>@media print { .no-print { display: none } }</style>
<script>window.addEventListener("load", () => setTimeout(() => window.print(), 400));</script>"""


def printable(html: str) -> bytes:
    """The document's HTML with the save-as-PDF hint and the print dialog."""
    if "<body" in html:
        head, sep, rest = html.partition("<body")
        tag_end = rest.find(">") + 1
        return (head + sep + rest[:tag_end] + PRINT_HELP + rest[tag_end:]).encode()
    return (PRINT_HELP + html).encode()


async def pdf_or_page(html: str, zoom: float = 1.0) -> tuple[bytes, str, str]:
    """(content, media type, extension): the PDF, or the printable page."""
    from app.platform.printing.routes import html_to_pdf

    try:
        return await html_to_pdf(html, zoom=zoom), "application/pdf", "pdf"
    except (OSError, ImportError):
        return printable(html), "text/html; charset=utf-8", "html"
