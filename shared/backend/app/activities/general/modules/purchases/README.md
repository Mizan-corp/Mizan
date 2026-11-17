# Purchases & Procurement

أوامر الشراء، استلام البضائع، سجل أسعار الموردين التاريخية، ومتابعة فواتير الشراء.

## Module ID
`purchases`

## Category
purchases

## Dependencies
core, inventory

## Permissions (PUR-1)
- `purchases`: orders (create, edit drafts, receive, return), invoice upload, quick products,
  suppliers (create, edit, (de)activate, delete), supplier prices, and the reads (orders, returns,
  price history, suggestions, a supplier's ledger). The storekeeper, accountant and manager roles hold
  it. Orders are for an active warehouse the user works in; unknown warehouses, suppliers and products
  are a 404.
- `finance`: money in or out of a safe or wallet: supplier payments and charges
  (`POST /suppliers/{id}/transactions`), paying on receipt (`amount_paid` > 0, also when planned on the
  order) and a refund on a return. A storekeeper receives with `amount_paid` = 0; the supplier is owed
  the total.
- The supplier list needs `purchases`, `finance` or `accounting:view` (the ledger's party picker,
  up to 1,000 a page); `search` matches the name or the phone.
- Reads of orders, their totals and costs, returns, price history, supplier prices, suggestions and a
  supplier's ledger need `purchases` or `finance` (PUR-5); a cashier reads none of them.

## Supplier ledger (PUR-5)
`GET /suppliers/{id}/ledger?page&page_size&newest_first` → `{supplier, items, total, page,
page_size, pages}`: the supplier's movements (invoices and charges as debits, payments and returns as
credits), oldest first unless `newest_first`, each with `balance`, what we owe after it, summed over
the whole account in one query so every page is right. `page_size` 1–500 (100 by default).

## Input and errors (PUR-3, PUR-6, PUR-7)
- Paging: `page` ≥ 1, `page_size` 1–200 on orders; ids are typed (a malformed one is a 422); unknown
  orders, suppliers, warehouses, products, subcategories and supplier prices are an Arabic 404.
- `SupplierIn`: name 1–128, phone 32, address 500, notes 2000; `type` one of `supplier`,
  `manufacturer`, `distributor`, `service`. Quick products: prices ≥ 0, in `Decimal`.
- Receiving (`POST /purchases/{id}/receive`), like creating an order or a return, is refused in a
  closed accounting month (`require_open_period`).
- Suggestions (`GET /purchases/suggestions`): active tracked products whose stock in all warehouses
  (`stock_balances`) is at or below their reorder point, lowest first, at most 500.
- Indexes for the filters used: `purchase_order_items(po_id)`, `(product_id)`,
  `supplier_transactions(supplier_id)`, `purchase_price_history(product_id)`,
  `purchase_orders(supplier_id)`, declared in the models and made by v101 where missing.

## Settings
- `auto_update_purchase_price` (on by default): a receipt sets the product's listed cost
  (`cost_price`) to the purchase price (without VAT when registered). Off, the listed cost stays as it
  is; the price history still records the purchase price and the average cost (`avg_cost`) follows
  every receipt either way.

## Order totals (PUR-2)
`GET /purchases` and `GET /purchases/{id}` return `total`: Σ quantity × unit cost of the lines, the
received quantities once received, the ordered ones before.

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
