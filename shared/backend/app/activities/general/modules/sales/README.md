# Sales & Invoicing

إصدار أوامر البيع وعروض الأسعار، الفواتير الضريبية، المرتجعات، وتتبع مدفوعات العملاء.

## Module ID
`sales`

## Category
sales

## Dependencies
core, inventory

## What the server decides (`services/checks.py`)
Whatever the client sends:
- **Prices** are the product's (wholesale in wholesale mode when it has one, else retail). Another
  price needs the POS setting `allow_price_override` **and** `sales:override_price` (managers).
  Discounts follow `allow_manual_discount`; a discount larger than the sale is refused.
- **Stock**: a sale can't take more than the branch holds while the inventory setting
  `prevent_negative_stock` is on (the default), except for `sales:negative_stock` holders; an allowed
  shortage is written to the audit log. The old client flags (`allow_negative_stock`,
  `is_offline_sync`) are gone and `local_id` no longer changes the check.
- **Shift**: a sale goes into the user's own open shift in the sale's branch (the `shift_id` sent must
  be that one). Cash needs one; with the POS setting `require_active_shift` on (the default) every POS
  sale and every confirmed draft does. Quotations confirmed into a safe or on credit need none.
- **Branch**: writes check `verify_warehouse_access`; lists show only the user's branches
  (managers and `supervise`: all); reading needs `sales` or `pos`.
- **Ids** (branch, customer, wallets, products) are found in the workspace first (404 in Arabic).

## Offline and retries
The POS sends `local_id`, a UUID made on the device and kept across retries and the offline queue
(`system/frontend/src/lib/offline.ts`). It is stored in `sales.local_id`, unique per (workspace,
cashier); a sale sent again returns the sale already recorded.

## Numbers
Per workspace (`app/platform/archive/numbering.py`): `INV-000001` invoices, `RET-` returns, `QUO-`
quotations, `DRF-` drafts (a draft gets its invoice number only when it is confirmed).

## Cancel and return
`sales:cancel` (manager, admin) cancels; `sales:return` (cashier, manager, admin) returns, refunding
cash from the user's own open shift in the sale's branch — never another cashier's.

## Audit
Every write logs its audit row inside its own transaction: create, draft, confirm draft, quotation
create / update / confirm / delete, cancel, full and partial return, allowed stock shortages.

## Balances
A customer's balance is never clamped at zero: below zero the workspace owes the customer, as the
ledger's receivables say.
