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

## Who reads the catalogue (INV-8)
- Products (`GET /products`, `/products/{id}`, `/products/barcode/{code}`), categories, subcategories,
  collections and the stock balances (`/stock/balance/*`) need one of `inventory`, `purchases`,
  `operations`, `pos`, `sales`, `quotations`, `reports` (`services/products.READ_PERMISSIONS`): a
  cashier still finds what to sell, with its price and the branch's stock.
- Costs (`cost_price`, `avg_cost`, and the items' `cost_price` in collections) only to `inventory`,
  `purchases` or `reports` (`COST_PERMISSIONS`); for the others they are `null`. The till's scan
  (`/pos/scan/{code}`) follows the same rule.
- A product's movement log (`/products/{id}/movements`, with costs) needs `inventory`; its dates are
  `from_date` / `to_date` (`YYYY-MM-DD`, `to_date` included whole).

## Input and errors (INV-4, INV-11)
- Names and fields are bounded as their columns (category and subcategory names 128, product name
  256, code 32, barcode 64, unit 32…), trimmed; prices and quantities ≥ 0. Longer or negative input
  is a 422; unknown categories, subcategories, products, barcodes and collections are an Arabic 404.
- A category name is unique in the workspace, a subcategory name within its category (two categories
  may both have «أخرى»): a duplicate is a 409.
- A barcode belongs to one **active** product of the workspace, as its main barcode or one of its
  extra ones (409 naming the product that holds it). A deactivated product's main barcode may be
  given to a new one (it can't be reactivated while the barcode is taken). The partial unique index
  `uq_products_tenant_barcode_active` (v101) backs this up; it is made only where the workspace has
  no duplicates already, so old duplicates stay and the service refuses new ones.
  `GET /products/barcode/{code}` and the till's scan find active products only.
- Collections: each item a product of the workspace, once; at most 200 items; prices ≥ 0.
- `GET /products` pages by 50 (at most 500) and returns `total`; the stock comes from the maintained
  balances. `POST /products/bulk-reorder-level` takes 1 to 500 ids and a level ≥ 0.

## Known limits
- Workspaces whose balances were clamped at zero before this rule keep those rows: history is not
  rewritten. A clamped row shows `stock_balances.qty` above the sum of its movements; correct it with an
  adjustment after a count.
- `valuation_method` offers FIFO, which is not implemented (average cost is used); `enable_reorder_alerts`
  is not read yet (INV-10).
- `/stock/balance/breakdown/{id}` lists every warehouse's quantity (no costs) to anyone who reads the
  catalogue, without a branch filter.
- Product codes (`code`) are not unique.
