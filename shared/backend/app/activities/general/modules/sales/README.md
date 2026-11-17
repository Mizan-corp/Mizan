# Sales & Invoicing

إصدار أوامر البيع وعروض الأسعار، الفواتير الضريبية، المرتجعات، وتتبع مدفوعات العملاء.

## Module ID
`sales`

## Category
sales

## Dependencies
core, inventory, contacts (customers and their payments), finance (wallets, safes), pos (shifts and
the cash drawer). Installing sales from the module centre adds them, and what they need in turn
(`with_dependencies` in `app/framework/activation.py`).

## VAT (ADR-014 D6, step 6)
A sale's VAT is worked out once, when the document is made (POS sale, draft or quotation) and again
when a draft or quotation is confirmed (the invoice's time), by `app/platform/settings/vat.py`:
each line stores `tax_code` (the product's code then; `NULL` when the workspace isn't
VAT-registered), `tax_rate`, `tax_amount` and `net_amount` (its value after every discount,
without VAT), and the sale `tax_amount`. `net_total` stays what the customer pays: unchanged when
prices include VAT (the default), with the tax added on top when they don't. A return document
takes each original line's value and tax in proportion to the quantity returned, whatever the
product's code is now; returning everything gives back the sale's VAT to the piastre. Sales made
before (or without registration) keep the old return arithmetic. The printed invoice
(`/print/sale/{id}`, "فاتورة ضريبية") and the emailed PDF show the stored figures and the tax
number, and nothing about VAT when the sale has no VAT data; nothing estimates 14 % of a total any
more. The module's old `default_tax_rate` setting, which nothing read, is gone: the rates live in
`vat.py` only.

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

## Invoices (PDF and email)
`GET /invoices/{id}/pdf` needs `sales` or `pos` and the sale's branch (404 for another workspace's
sale). `POST /invoices/{id}/send` (`sales`, the sale's branch) is rate limited: 10 per user every 10
minutes and 100 per workspace an hour (429, `app/core/ratelimit.py`; in Redis when `REDIS_URL` is
set, per process otherwise). The address is required (≤ 254 characters, subject ≤ 200).

## Errors
Every answer is in Arabic (cancel: «تم إلغاء الفاتورة», return: «تم إرجاع الفاتورة»); the offline
key lives in `sales.local_id`, never in the notes.
