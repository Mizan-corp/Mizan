# Inventory & Supply

تتبع الأرصدة اللحظية، إدارة الفروع والمستودعات، تسويات الجرد، وأوامر الشراء والتوريد.

## Module ID
`inventory`

## Category
retail

## Dependencies
core

## Tax code (ADR-014 D6, step 6)
`products.tax_code`: `standard` (14 %), `zero` (0 %, still reported) or `exempt` (outside VAT);
default and every existing product `standard` (migration `v94_vat`, with a check constraint). It is a
field of the product form ("ضريبة القيمة المضافة"), in `ProductOut` and the create/update schemas.
Documents copy it onto their lines when they are made; changing it never changes a past document.

## Stock rules
- **One stock path:** stock changes only through `services/stock.apply_movement`, which writes the
  movement, updates `stock_balances` atomically and runs the variant's batch rules. Balances are never
  clamped: `stock_balances.qty` is always the sum of the product's movements in that warehouse.
- **Out-movements are checked** (`sale`, `damage`, `adjustment_out`, `transfer_out`, `return_out`):
  the balance row is locked and a tracked product can't go below zero (400, Arabic). Exceptions: the
  product is untracked (`products.stock_status = 'untracked'`, e.g. a service; decided by the product,
  never by a missing `warehouse_product_status` row), the workspace switched off
  `prevent_negative_stock`, or the calling document passes `allow_negative` (offline sale sync).
  Transfers and dispatches always need the stock, whatever the setting.
- **By hand** (`POST /stock/movements`, `POST /stock/adjustment/bulk`): only `adjustment_in`,
  `adjustment_out` and `damage` (posted to the ledger as `stock.adjusted`), and `opening_stock` with
  the `inventory:opening` permission. Purchases, sales, returns and transfers are refused (400): they
  come from their documents. Costs and prices are ≥ 0; the warehouse must be active and one the user
  works in.
- **Opening stock** is not posted while the ledger has no opening entry (the opening entry takes the
  stock in at average cost, ADR-014 D10); entered after it, it posts Dr inventory / Cr opening balance
  equity.
- **Transfers** (`POST /stock/transfer`): two different active warehouses, both reachable by the user;
  a `transfer_out` and its `transfer_in` with one reference (the same batches arrive), audited; the
  route commits.
- **Stock reset** (`DELETE /stock/movements?warehouse_id=`): only while every movement of the
  warehouse is opening stock, an adjustment or damage, and none is in the ledger (the accounting
  module refuses through `stock.resetting` when one is posted or the opening entry is in force).
  The workspace average cost of the products concerned is rebuilt from their remaining movements.
- **Warehouses:** codes are unique per workspace (409); a warehouse holding stock (any non-zero
  balance) or an open shift can't be deactivated (409).
- **Valuation** (`GET /stock/valuation`) is at the weighted average cost (`avg_cost`, ADR-014 D5), the
  listed `cost_price` only for a product that never had a costed receipt; it needs `inventory` or
  `reports`. Movements need `inventory`, low stock `inventory` or `purchases`.

## Known limits
- Workspaces whose balances were clamped at zero before this rule keep those rows: history is not
  rewritten. A clamped row shows `stock_balances.qty` above the sum of its movements; correct it with an
  adjustment after a count.
- `valuation_method` offers FIFO, which is not implemented (average cost is used); `enable_reorder_alerts`
  is not read yet (INV-10).
- Product, category and collection reads still need only a sign-in (INV-8); categories, barcodes and
  collections inputs are not all bounded yet (INV-4).
