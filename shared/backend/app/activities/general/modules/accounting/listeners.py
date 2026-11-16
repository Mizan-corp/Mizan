"""Accounting: the events it posts journal entries for (app/framework/events.py). Each runs in the
transaction of the document that raised it, only in workspaces where accounting is active."""
from app.activities.general.modules.accounting.posting import finance, pos, receipts, sales

LISTENERS = {
    "sale.confirmed": sales.on_sale_confirmed,
    "sale.returned": sales.on_sale_returned,
    "sale.cancelled": sales.on_sale_cancelled,
    "customer_payment.received": receipts.on_customer_payment,
    "customer_adjustment.created": receipts.on_customer_adjustment,
    "drawer.transaction_added": pos.on_drawer_transaction,
    "drawer.transaction_cancelled": pos.on_drawer_cancelled,
    "drawer.revenue_delivered": pos.on_revenue_delivered,
    "shift.closed": pos.on_shift_closed,
    "expense.approved": finance.on_expense_approved,
    "expense.cancelled": finance.on_expense_cancelled,
    "safe.deposited": finance.on_safe_deposited,
    "safe.withdrawn": finance.on_safe_withdrawn,
    "wallet.transferred_to_safe": finance.on_wallet_to_safe,
    "wallet.balance_reset": finance.on_wallet_reset,
}
