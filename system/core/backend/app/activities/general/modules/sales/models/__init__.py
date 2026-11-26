"""Sales & Invoicing Module Models."""
from app.activities.general.modules.sales.models.sale import Sale, SaleItem
from app.activities.general.modules.sales.models.sale_payment import SalePayment

__all__ = [
    "Sale",
    "SaleItem",
    "SalePayment",
]
