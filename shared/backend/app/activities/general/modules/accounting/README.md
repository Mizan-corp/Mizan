# Accounting (double-entry ledger)

`accounting`: a business module of the `general` activity, depending on `finance`. Off by default:
the owner enables it (ADR-014, answer 2). Design: [ADR-014](../../../../../../../docs/decisions/ADR-014-double-entry-accounting.md).
Steps 2 and 3 of D12 are built: the ledger core and the posting rules for sales, returns, POS and
drawers, customer receipts, safes and wallets and expenses (step 2), then purchases, supplier
payments, purchase returns, stock adjustments, payroll, HR advances, clinic invoices and the
manager's shift deposit (step 3).

## Parts

| File | What |
|---|---|
| `models.py` | `acc_accounts`, `acc_entries`, `acc_lines`, `acc_money_accounts` (migration `v90_accounting_ledger`) |
| `charts/eg_standard.json` | The standard Egyptian chart (Arabic + English), copied into a workspace on first use |
| `services/chart.py` | `ensure_chart` (idempotent copy), `add_missing_accounts` (accounts the standard chart gained since, added by role; used when a role is missing and by the chart read), `account_by_role`, `money_account` (safe / wallet / branch drawer sub-accounts, created lazily), `default_bank_account`, `category_account` |
| `services/posting.py` | `post()` and `reverse()`: the only writers of entries |
| `services/ledger.py` | Reads: account tree, entries, entry detail, trial balance |
| `posting/*.py` | One posting function per event: `sales`, `pos`, `receipts`, `finance` (step 2); `purchases`, `inventory`, `payroll`, `clinic` (step 3) |
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

### Step 3: purchases, stock, payroll and clinics

Every rule is idempotent through `(source_type, source_id, event)` and posts today's date, in the
document's transaction. The modules emit generic events and never import accounting.

| Event (who emits it) | Entry (source / event) | Debit | Credit |
|---|---|---|---|
| `purchase.received` (`receive_purchase`) | `purchase` / `receive` | inventory (lines × unit cost); and, for the amount paid at receipt, payables (party: supplier) | payables (party: supplier); and, for the amount paid, the safe or wallet it left from |
| `supplier.payment` (`POST /suppliers/{id}/transactions`, `credit`) | `supplier_tx` / `payment` | payables (party: supplier) | the safe or wallet |
| `supplier.charge` (the same route, `debit`) | `supplier_tx` / `charge` | other expenses | payables (party: supplier) |
| `purchase.returned` (`POST /purchases/{id}/returns`) | `purchase_return` / `confirm` | payables (party: supplier) for what lowers the balance; the safe or wallet for a refund | inventory (at the cost the goods came in at) |
| `stock.adjusted` (`apply_movement` of type `adjustment_out` or `damage`) | `stock_movement` / `adjust` | inventory shortage and damage (`inventory_loss`) | inventory, at the movement's unit cost (the average cost when none was given) |
| …`adjustment_in` | | inventory | other income |
| `payroll.approved` (`approve_payroll_period`) | `payroll` (id: the approval's salaries expense) / `approve` | salaries expense = net + withheld | salaries payable per employee (net, party: employee); employee advances per employee (advances recovered, party: employee); other income (deductions, lateness and absence withheld) |
| `payroll.reopened` (reopening an approved, unpaid month) | `payroll` / `reverse` | the approval's entry, reversed | |
| `payroll.paid` (`pay_payroll_period`) | `payroll` (id: the period) / `pay` | salaries payable per employee (party: employee) | the safe or wallet it was paid from |
| `hr_advance.paid` (`POST /hr/advances`, kind سلفة) | `hr_advance` / `pay` | employee advances (party: employee) | the safe or wallet |
| `clinic.invoice_paid` (`POST /clinic/invoices/{id}/pay`) | `clinic_invoice` / `revenue`, once | receivables (the patient's share not yet paid, no party); insurance receivables (the insurer's share) | sales (patient's + insurer's share) |
| …each payment | `clinic_payment` (id: the `sale_payments` row) / `confirm` | cash: the drawer of the branch of the cashier's open shift; bank, card, wallet…: the default bank | receivables |
| `safe.deposited` from `close_shift_with_manager` | `safe_movement` / `deposit` | the safe | the shift's branch drawer |

Decisions where the design was open:
- A supplier **debit** entered by hand ("we owe more" without goods: a service invoice, a fee) is
  an expense: Dr other expenses / Cr payables. An opening supplier balance should come in through
  the opening entry (step 4), not as a manual debit.
- A purchase order with no supplier posts its payables with no party.
- Purchase returns leave stock at the line's cost (`return_out`, a new movement type), recalculating the
  workspace average without those units; the supplier is owed less by the value, minus any refund taken
  into a safe or wallet. A return can't take more than the order received and not yet returned, nor more
  than the warehouse holds; a manual `return_out` stock movement is refused (use the return).
- Payroll: gross = base + overtime + bonus payment + bonus; what the net leaves out of it is
  "withheld"; advances up to that amount are recovered (the rest stays an asset), the remainder
  (deductions خصم, lateness, absence) is other income. Each approval is keyed by its salaries expense,
  so a reopened and re-approved month has its own entry. A month whose net total is 0 posts nothing.
  Deductions and bonuses move no cash and post nothing by themselves.
- Stock adjustments: opening stock is left to the opening entry (step 4); purchases, sales, returns
  are posted with their documents; transfers between branches post nothing (one inventory account).
  A product with no cost at all (average and list cost 0) adjusts with nothing to post.
- Clinics: revenue is posted once, at the first payment the ledger sees, with the patient's whole unpaid
  share as a receivable that each payment then clears (so the invoice can be paid in parts). Payments
  made before accounting was enabled are not part of it. The chart's `insurance_receivables` (127) sits
  beside the customers' receivables account (122), not under it, because 122 takes postings.
- Manager's shift deposit: the request names no safe, so the cash taken out is deposited (with the
  shift, through `finance.services.safes.deposit`) only when the workspace has exactly one active
  non-bank safe; with none or several it stays recorded as `deposit_amount` on the shift and nothing moves.

Not posted yet (later steps of D12): the opening entry (step 4), insurance claim approval and payment
(the insurer's receivable stays open), stock movements entered by hand with type `purchase`, `sale`,
`return_in` or `opening_stock` through `POST /stock/movements`, cancelling a clinic invoice's sale,
and money modules outside general sales (hotel, storefront, school…).

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
