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
- Costs (`cost_price`, `avg_cost`, and the items' `cost_price` and `avg_cost` in collections) only to `inventory`,
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

## Screens (phase C, INV-9)
The inventory tabs (`InventoryHeader`): balances and valuation (`/inventory`), products (`/products`),
categories (`/inventory/categories`), adjustments and transfers (`/inventory/adjustments`),
collections (`/inventory/collections`) and warehouses (`/inventory/warehouses`, `settings`).
- **Products:** filter by category and active / stopped (`GET /products?status=active|inactive|all`;
  stopped ones only for `inventory`, 403 otherwise). A product may have no category
  (`subcategory_id` optional on create; `clear_subcategory` on update takes it out of one); the
  picker groups subcategories by category. A product's card: stock per branch, extra barcodes
  (add, delete), its picture (upload; `DELETE /products/{id}/image` takes it off and deletes the
  file), its movement log (paged, by dates), its purchase prices (`purchases` or `finance`), and
  stopping it (`DELETE /products/{id}`, audited, never erased) or bringing it back
  (`PUT is_active`). `ProductOut` carries `image_url` (the till shows it).
- **Categories:** add, rename, move a subcategory to another category, delete one no active product
  uses (stopped products are left without a category).
- **Warehouses:** `GET /stock/warehouses?include_inactive=true` (`settings`) lists stopped ones too,
  each with `is_active`. Add (audited), edit, stop (`PUT is_active=false`: refused while it holds
  stock or an open shift) and bring back; bringing one back counts against the plan's branches like
  adding one (403 past the limit).
- **Adjustments and transfers:** adjustment in / out, damage (reason required), opening stock (with
  `inventory:opening`), batch and expiry for stock coming in; a transfer between two branches with
  the source's available quantity shown; the branch's latest movements.
- **Collections:** add, edit, delete, what one costs (its items at average cost, for those who see
  costs) and how many can be assembled in a branch. No selling price (see Collections).

## Settings (INV-10)
- `prevent_negative_stock` (on by default): see Stock rules.
- `enable_reorder_alerts` (on by default): when on, a sale that leaves a product at or below its
  reorder level raises a `low_stock` notification (and the optional e-mail), and the system scan
  (`POST /notifications/generate-system-alerts`) reports the active tracked products whose stock in
  all branches is at or below their reorder level (`services/stock.products_at_reorder_level`; it
  used to report any product with a reorder point, whatever its stock). Off: neither.
- `valuation_method` was removed: it offered FIFO, which was never built. Stock is valued at the
  weighted average cost (ADR-014 D5) everywhere: valuation, the ledger, cost of sales.

## Collections: a stock-assembly helper, not sold (phase D)
A collection (`product_collections`, `collection_items`) is a named set of products and quantities
(a gift box's contents, a kit): the screen shows its items, its cost and how many a branch can
assemble (`GET /collections/{id}/availability`). It is **not sold**: the till and the sales invoice
sell products, and to sell a box its items are added to the invoice. Decided in phase D against
selling it as a bundle: a sale line is one product (`sale_items.product_id`), and prices are
checked per product, returns are made per product line, drafts and quotations are rebuilt from
product lines, and the invoice, the receipt and the offline till print and store product lines.
Selling a bundle (each item leaving stock at its own cost, the sale showing the collection, VAT
per item's code) needs a parent line or a grouping of lines that every one of those paths
understands: a sales/POS redesign, not a fix. The screen therefore offers no selling price; the
API still accepts `retail_price` / `wholesale_price` (kept for older clients and data), and a `PUT`
that doesn't send them keeps the stored ones (it used to zero them).

## Known limits
- The availability of a collection whose items are all untracked is answered as 999 (the screen
  shows «not tracked»).
- Workspaces whose balances were clamped at zero before this rule keep those rows: history is not
  rewritten. A clamped row shows `stock_balances.qty` above the sum of its movements; correct it with an
  adjustment after a count.
- `/stock/balance/breakdown/{id}` lists every warehouse's quantity (no costs) to anyone who reads the
  catalogue, without a branch filter.
- Product codes (`code`) are not unique.
