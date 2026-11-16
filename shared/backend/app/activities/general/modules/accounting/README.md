# Accounting (double-entry ledger)

`accounting`: a business module of the `general` activity, depending on `finance`. Off by default:
the owner enables it (ADR-014, answer 2). Design: [ADR-014](../../../../../../../docs/decisions/ADR-014-double-entry-accounting.md).
This is step 2 of D12: the ledger core and the posting rules for sales, returns, POS and drawers,
customer receipts, safes and wallets, and expenses.

## Parts

| File | What |
|---|---|
| `models.py` | `acc_accounts`, `acc_entries`, `acc_lines`, `acc_money_accounts` (migration `v90_accounting_ledger`) |
| `charts/eg_standard.json` | The standard Egyptian chart (Arabic + English), copied into a workspace on first use |
| `services/chart.py` | `ensure_chart` (idempotent copy), `account_by_role`, `money_account` (safe / wallet / branch drawer sub-accounts, created lazily), `default_bank_account`, `category_account` |
| `services/posting.py` | `post()` and `reverse()`: the only writers of entries |
| `services/ledger.py` | Reads: account tree, entries, entry detail, trial balance |
| `posting/*.py` | One posting function per event |
| `listeners.py` | The events it listens to (`app/framework/events.py`): they run only in workspaces where accounting is active, in the document's transaction |
| `router.py` | The API (below) |

## The posting service

`post(db, tenant_id, source_type, source_id, event, date, lines, memo, warehouse_id, user_id)`:
lines of zero are dropped; every line is debit or credit; debits = credits > 0; no group or
stopped account; the month of `date` must not be closed (Arabic `BusinessError` otherwise). The
same `(source_type, source_id, event)` returns the existing entry. It flushes, never commits.
`reverse(db, entry, date, user_id)` posts the opposite lines with `event = 'reverse'` and
`reverses_id`. The database also refuses an unbalanced entry at commit (deferred constraint
trigger) and any update of a posted entry or line.

Posting dates: events that happen now (sale, return, cancel, receipt, drawer, shift, safe and
wallet movements) post on today's date in Africa/Cairo; an approved expense posts on its own
`date` (today if that date is in the future); a reversal posts on the day of the cancellation.

## Posting rules (as built)

| Event (who emits it) | Entry (source / event) | Debit | Credit |
|---|---|---|---|
| `sale.confirmed` (sales: POS sale, draft or quotation confirmed) | `sale` / `confirm` | each `sale_payments` line: its safe (`safe_id`), its wallet, the branch drawer (cash), the default bank (bank, cheque, card), or receivables with the customer as party (credit) | sales = the payment lines' total (the sale's `net_total`, after discounts) |
| …its cost (same entry) | | cost of goods sold = Σ `sale_items.unit_cost × qty` | inventory |
| `sale.returned` (full or partial return document) | `sale_return` / `confirm` | sales returns = the refund total | each refund line, as above |
| …cost of the return (same entry) | | inventory | cost of goods sold |
| `sale.cancelled` | `sale` / `reverse` | the sale's entry, reversed | |
| `customer_payment.received` (customers screen, or a drawer deposit for a customer) | `customer_payment` / `confirm` | the safe / wallet / drawer of its shift's branch / default bank | receivables (party: customer) |
| `customer_adjustment.created`, kind `opening` | `customer_adjustment` / `confirm` | receivables (party) — or opening balance equity when the balance goes down | opening balance equity — or receivables |
| …kind `adjustment`, balance up | | receivables (party) | other income |
| …kind `adjustment`, balance down | | other expenses | receivables (party) |
| `drawer.transaction_added`, type `deposit` (not a sale, return or receipt) | `drawer_tx` / `confirm` | the branch drawer (or the wallet when paid to a wallet) | the category's account, else other income |
| …type `expense` or `withdrawal` | | the category's account, else other expenses | the drawer (or the wallet) |
| `drawer.transaction_cancelled` | `drawer_tx` (or `customer_payment`) / `reverse` | the row's entry (or its receipt's), reversed | |
| `drawer.revenue_delivered` (drawer → safe) | `drawer_tx` / `revenue_delivery` | the safe | the branch drawer |
| `shift.closed` (close, close with manager, hand-over) with a difference | `shift` / `close` | short: cash shortage; over: the drawer | short: the drawer; over: cash surplus |
| `expense.approved` (not payroll) | `expense` / `approve` | the category's account, else other expenses | the safe or wallet it was paid from |
| `expense.cancelled` | `expense` / `reverse` | the approval, reversed | |
| `safe.deposited` (`POST /safes/{id}/deposit`) with `shift_id` | `safe_movement` / `deposit` | the safe | that shift's branch drawer |
| …without `shift_id` | | the safe | other income |
| `safe.withdrawn` (`POST /safes/{id}/withdraw`) | `safe_movement` / `withdraw` | other expenses | the safe |
| `wallet.transferred_to_safe` (`POST /safes/transfer`) | `wallet_movement` / `transfer` | the safe | the wallet |
| `wallet.balance_reset` (`POST /wallets/{id}/reset-balance`) | `wallet_movement` / `reset` | other expenses (positive balance) or the wallet | the wallet or other income |

Safe and wallet movements that belong to a document (a sale into a safe, an expense, a receipt…)
are posted with that document only, never twice. VAT lines are not posted yet: documents carry no
tax data until step 6.

Not posted yet (later steps of D12): purchases, supplier payments and purchase returns, stock
adjustments, payroll and HR advances, clinic invoices, the opening entry (step 4), the
manager's shift deposit when it isn't put in a safe with its shift, and money modules outside
general sales (hotel, storefront, school…).

## API (`/accounting`, guarded by the module)

| Route | Permission | What |
|---|---|---|
| `GET /accounting/accounts` | `accounting:view` | The chart as a tree |
| `POST /accounting/accounts` | `accounting:settings` | Add a sub-account under a group (`parent_id`, `name`, optional `code`, `is_group`) |
| `PUT /accounting/accounts/{id}` | `accounting:settings` | Rename; stop/resume an account no posting rule uses |
| `PUT /accounting/categories/{id}/account` | `accounting:settings` | A financial category's account (income ↔ income, expense ↔ expense) |
| `GET /accounting/entries?from&to&source_type&account_id&page&page_size` | `accounting:view` | Entries, newest first, with totals and whether reversed |
| `GET /accounting/entries/{id}` | `accounting:view` | One entry and its lines |
| `GET /accounting/trial-balance?from&to` | `accounting:view` | Debits, credits and balance per account, and the totals |

No route edits or deletes an entry. Manual journal entries and screens come in step 5.

Permissions (D11): `accounting:view`, `accounting:journal`, `accounting:close`,
`accounting:settings`; the accountant role holds all four, the manager holds view, the admin
everything. Periods (`/periods`, in finance) close and reopen with `accounting:close` or `finance`.
