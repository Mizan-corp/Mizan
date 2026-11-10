"""Sales & Invoicing Module Models."""
from app.modules.general.sales.models.sale import Sale, SaleItem
from app.modules.general.sales.models.sale_payment import SalePayment

__all__ = [
    "Sale",
    "SaleItem",
    "SalePayment",
]
