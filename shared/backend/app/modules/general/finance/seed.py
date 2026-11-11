"""Finance: demo data for a new workspace (rows marked is_demo, removable by the owner).

Called by app/framework/demo.py in a fixed order with one random generator, so the same
workspace size gives the same data."""
from decimal import Decimal

from app.modules.general.finance.models.payment_wallet import PaymentWallet
from app.modules.general.finance.models.safe import Safe

WALLET_NAMES = ["خزينة الفرع", "محفظة فودافون كاش", "محفظة انستاباي"]


async def seed(db, ctx) -> None:
    db.add_all([
        PaymentWallet(id=ctx.new_id(), name=WALLET_NAMES[0], type="cash", is_demo=True),
        PaymentWallet(id=ctx.new_id(), name=WALLET_NAMES[1], type="mobile", is_demo=True),
    ])
    db.add(Safe(id=ctx.new_id(), name="الخزينة الرئيسية", balance=Decimal("25000"), is_demo=True))
