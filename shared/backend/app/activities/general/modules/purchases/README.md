# Purchases & Procurement

أوامر الشراء، استلام البضائع، سجل أسعار الموردين التاريخية، ومتابعة فواتير الشراء.

## Module ID
`purchases`

## Category
purchases

## Dependencies
core, inventory

## Purchase returns (ADR-014 step 3)
`POST /purchases/{id}/returns` sends received goods back to the supplier (`GET` lists the returns and what
can still be returned per product). Stock leaves with a `return_out` movement at the line's cost, the
supplier's balance goes down by the value (or `refund_amount` goes into a safe or wallet), and the
ledger posts it when the accounting module is on. Receiving an order, paying a supplier and returns emit
`purchase.received`, `supplier.payment` / `supplier.charge` and `purchase.returned`.

## VAT (ADR-014 D6, step 6)
At receipt each line stores `tax_code` (the product's code then), `tax_rate`, `tax_amount` and
`net_amount` (its received value without VAT), and the order `tax_amount`. Whether the unit costs
include VAT is said by the receipt (`prices_include_vat`), else by the order, else by the workspace's
setting, and is kept on the order. The supplier is owed the value plus the VAT; stock, the average
cost and `cost_price` take the cost without VAT. A purchase return takes the order's own value and
VAT for that product in proportion to the quantity (`vat.portion`), never the product's code at the
time of the return, and stores them on `purchase_returns.tax_amount` and its lines. Orders received
while the workspace wasn't VAT-registered behave as before. The printed purchase invoice shows the
stored VAT and the workspace's tax number.
