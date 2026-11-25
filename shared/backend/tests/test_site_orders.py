"""Offline tests for the Website tab's orders surface (app/platform/site/orders.py):
the list stays inside the caller's workspace, an unknown status filter is a 422, a
foreign or missing order is a 404, and completing a COD order marks it paid."""

import os
import sys
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://unused:unused@127.0.0.1/unused")
os.environ.setdefault("SECRET_KEY", "offline-test-not-used-for-signing")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException

from app.models.registry import load_all_models

load_all_models()  # mapper configuration cascades across the full registry

from app.platform.site import orders
from app.platform.site.orders import OrderStatusIn

TID = uuid.uuid4()
OTHER_TID = uuid.uuid4()


def make_order(**over):
    o = SimpleNamespace(
        id=uuid.uuid4(), tenant_id=TID, order_number="WEB-1001", customer_name="عميل",
        customer_phone="0100", customer_email=None, delivery_type="delivery",
        delivery_address="عنوان", table_number=None, notes=None, subtotal=100.0,
        delivery_fee=30.0, discount_amount=0.0, coupon_code=None, total_amount=130.0,
        status="pending", payment_method="cod", payment_status="unpaid",
        created_at=None,
        items=[SimpleNamespace(product_name="عصير", unit_price=25.0, quantity=2.0,
                               total_price=50.0, notes=None)],
    )
    for k, v in over.items():
        setattr(o, k, v)
    return o


def db_returning(value, mode="all"):
    db = AsyncMock()
    result = MagicMock()
    if mode == "all":
        result.scalars.return_value.all.return_value = value
    else:
        result.scalar_one_or_none.return_value = value
    db.execute.return_value = result
    return db


class ListOrdersTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_filters_by_caller_workspace(self):
        db = db_returning([make_order()])
        user = SimpleNamespace(tenant_id=TID)
        out = await orders.list_orders(page=1, page_size=50, db=db, user=user)
        self.assertEqual(len(out["items"]), 1)
        self.assertEqual(out["items"][0]["order_number"], "WEB-1001")
        self.assertEqual(out["items"][0]["items"][0]["product_name"], "عصير")
        self.assertEqual(out["statuses"], list(orders.ORDER_STATUSES))
        # The workspace filter is on the statement, not applied in Python.
        compiled = str(db.execute.call_args[0][0].compile(compile_kwargs={"literal_binds": True}))
        self.assertIn(TID.hex, compiled.replace("-", ""))

    async def test_unknown_status_filter_is_422(self):
        db = db_returning([])
        user = SimpleNamespace(tenant_id=TID)
        with self.assertRaises(HTTPException) as ctx:
            await orders.list_orders(status_filter="refunded", page=1, page_size=50, db=db, user=user)
        self.assertEqual(ctx.exception.status_code, 422)
        db.execute.assert_not_called()

    async def test_search_stays_workspace_scoped(self):
        db = db_returning([])
        user = SimpleNamespace(tenant_id=TID)
        await orders.list_orders(search="WEB", page=1, page_size=50, db=db, user=user)
        compiled = str(db.execute.call_args[0][0].compile(compile_kwargs={"literal_binds": True}))
        self.assertIn(TID.hex, compiled.replace("-", ""))
        self.assertIn("%WEB%", compiled)


class UpdateStatusTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_or_foreign_order_is_404(self):
        db = db_returning(None, mode="one")
        user = SimpleNamespace(tenant_id=TID)
        with self.assertRaises(HTTPException) as ctx:
            await orders.update_order_status(uuid.uuid4(), OrderStatusIn(status="confirmed"), db=db, user=user)
        self.assertEqual(ctx.exception.status_code, 404)
        # The lookup was constrained to the caller's workspace.
        compiled = str(db.execute.call_args[0][0].compile(compile_kwargs={"literal_binds": True}))
        self.assertIn(TID.hex, compiled.replace("-", ""))

    async def test_completing_cod_order_marks_paid(self):
        order = make_order()
        db = db_returning(order, mode="one")
        user = SimpleNamespace(tenant_id=TID)
        out = await orders.update_order_status(order.id, OrderStatusIn(status="completed"), db=db, user=user)
        self.assertEqual(order.status, "completed")
        self.assertEqual(order.payment_status, "paid")
        self.assertEqual(out["status"], "completed")
        db.commit.assert_awaited_once()

    async def test_completing_non_cod_order_leaves_payment(self):
        order = make_order(payment_method="fawry")
        db = db_returning(order, mode="one")
        user = SimpleNamespace(tenant_id=TID)
        await orders.update_order_status(order.id, OrderStatusIn(status="completed"), db=db, user=user)
        self.assertEqual(order.payment_status, "unpaid")

    async def test_status_values_are_whitelisted(self):
        with self.assertRaises(Exception):
            OrderStatusIn(status="hacked")


if __name__ == "__main__":
    unittest.main()
