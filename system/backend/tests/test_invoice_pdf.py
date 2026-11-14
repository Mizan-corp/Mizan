"""The sales invoice document (#118): a PDF where the server can render one, otherwise the same
invoice as a printable page, for downloads and email attachments alike."""
import os
from decimal import Decimal

import pytest

import main  # noqa: F401  (loads every model)
from app.db.base import AsyncSessionLocal
from tests.test_business_remediation import _create_sales_test_env

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine

    await engine.dispose()
    yield
    await engine.dispose()


async def _sale():
    from app.activities.general.modules.sales.schemas import SaleCreate, SaleItemCreate
    from app.activities.general.modules.sales.services.sales import create_sale
    from app.platform.tenancy.context import current_tenant_id

    env = await _create_sales_test_env()
    current_tenant_id.set(env["tenant_id"])
    async with AsyncSessionLocal() as session:
        sale = await create_sale(session, SaleCreate(
            warehouse_id=env["warehouse_id"], payment_method="cash", shift_id=env["shift_id"], discount_amount=Decimal("0"),
            items=[SaleItemCreate(product_id=env["product_id"], qty=Decimal("1"), unit_price=Decimal("100"),
                                  unit_cost=Decimal("60"), discount=Decimal("0"))],
        ), env["cashier_id"])
    return env, sale.id


async def test_invoice_pdf_and_the_printable_fallback(monkeypatch):
    from types import SimpleNamespace

    from app.activities.general.modules.sales.services import invoices
    from app.platform.printing import routes as printing

    env, sale_id = await _sale()
    async with AsyncSessionLocal() as db:
        content, media, ext, sale = await invoices.render_file(db, sale_id, env["tenant_id"])
    assert content[:5] == b"%PDF-" and media == "application/pdf" and ext == "pdf"

    # A server without WeasyPrint's libraries: the invoice as a page that opens the print dialog.
    async def no_pdf(html, zoom=1.0):
        raise OSError("cannot load library 'libpango-1.0-0'")

    monkeypatch.setattr(printing, "html_to_pdf", no_pdf)
    async with AsyncSessionLocal() as db:
        content, media, ext, _ = await invoices.render_file(db, sale_id, env["tenant_id"])
    page = content.decode()
    assert ext == "html" and media.startswith("text/html") and "window.print()" in page and "حفظ بصيغة PDF" in page

    sent = []

    async def fake_send(to_email, subject, html_content, attachments=None, text=None, reply_to=None):
        sent.append(attachments)
        return {"ok": True}

    monkeypatch.setattr(invoices, "send_email", fake_send)
    async with AsyncSessionLocal() as db:
        user = SimpleNamespace(tenant_id=env["tenant_id"], id=env["cashier_id"], full_name="كاشير")
        await invoices.email_invoice(db, sale_id, "customer@example.com", None, user)
    assert sent[0][0]["filename"].endswith(".html") and sent[0][0]["type"] == "text/html"
