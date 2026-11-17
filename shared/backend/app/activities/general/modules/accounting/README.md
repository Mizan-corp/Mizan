# Accounting (double-entry ledger)

`accounting`: a business module of the `general` activity, depending on `finance`. Off by default:
the owner enables it (ADR-014, answer 2). Design: [ADR-014](../../../../../../../docs/decisions/ADR-014-double-entry-accounting.md).
Steps 2 to 5 of D12 are built: the ledger core and the posting rules for sales, returns, POS and
drawers, customer receipts, safes and wallets and expenses (step 2); purchases, supplier
payments, purchase returns, stock adjustments, payroll, HR advances, clinic invoices and the
manager's shift deposit (step 3); the reports (D8), the opening entry (D10) and the year-end
closing (D7) (step 4); manual journal entries (D9), reversals by hand (D1), the nightly
reconciliation check (D8) and the screens (step 5).

## Parts

| File | What |
|---|---|
| `models.py` | `acc_accounts`, `acc_entries`, `acc_lines`, `acc_money_accounts` (migration `v90_accounting_ledger`); `acc_drafts`, `acc_draft_lines` (`v93_accounting_journal_drafts`) |
| `charts/eg_standard.json` | The standard Egyptian chart (Arabic + English), copied into a workspace on first use |
| `services/chart.py` | `ensure_chart` (idempotent copy), `add_missing_accounts` (accounts the standard chart gained since, added by role; used when a role is missing and by the chart read), `account_by_role`, `money_account` (safe / wallet / branch drawer sub-accounts, created lazily), `default_bank_account`, `category_account` |
| `services/posting.py` | `post()` and `reverse()`: the only writers of entries |
| `services/ledger.py` | Reads: account tree, entries, entry detail (its `trial_balance` calls `reports.trial_balance`) |
| `services/reports.py` | The reports of D8 and the reconciliation, from the ledger tables only |
| `services/opening.py` | The opening entry (D10): plan, preview, post |
| `services/closing.py` | The year-end closing entry (D7) and its reversal |
| `services/settings.py` | `acc_settings` (migration `v92_accounting_settings`): `fiscal_year_start`, `start_date` |
| `services/journal.py` | Manual journal entries (D9): drafts, the posting rules, keeping the operational balances along; reversing manual and opening entries (D1) |
| `services/nightly.py` | The nightly reconciliation check (D8), run by the automation job `accounting_reconciliation` |
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

Not posted yet (later steps of D12): insurance claim approval and payment
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
| `GET /accounting/trial-balance?from&to&warehouse_id&include_zero&include_closing` | `accounting:view` | Opening, period debit and credit, closing per account, group roll-up, totals |
| `GET /accounting/income-statement?from&to&warehouse_id&include_closing` | `accounting:view` | Revenue to net profit |
| `GET /accounting/balance-sheet?as_of&warehouse_id&include_closing` | `accounting:view` | Assets, liabilities, equity at a date |
| `GET /accounting/general-ledger/{account_id}?from&to&warehouse_id&include_closing&page&page_size` | `accounting:view` | One account's lines with a running balance |
| `GET /accounting/party-statement/{customer\|supplier\|employee}/{id}?from&to&warehouse_id&page&page_size` | `accounting:view` | A party's lines with a running balance, and the operational balance to reconcile with |
| `GET /accounting/reconciliation` | `accounting:view` | The ledger against the operational balances (flags only) |
| `GET /accounting/settings` | `accounting:view` | `fiscal_year_start`, `start_date` |
| `PUT /accounting/settings` | `accounting:settings` | `fiscal_year_start` (1-12); refused while a year-end closing is in force |
| `GET /accounting/opening/preview?date` | `accounting:view` | The opening entry's lines and totals, nothing posted |
| `POST /accounting/opening` `{date}` | `accounting:settings` | Post the opening entry |
| `POST /accounting/year-end?year=YYYY` | `accounting:close` | Post the year-end closing entry |
| `POST /accounting/year-end/reverse?year=YYYY` | `accounting:close` | Reverse a year's closing entry (the only way to reopen its months) |
| `GET /accounting/periods` | `accounting:view`, `:close` or `:settings` | Every month from the books' first one to the current month (newest first) with its status, who closed or reopened it and why, and `can_close` / `can_reopen` (in order, D7); each fiscal year with its closing entry in force and its open months. Closing and reopening stay on `/periods` (finance) |
| `GET /accounting/drafts?status=draft\|posted&page&page_size` | `accounting:journal` | Manual entries: drafts, or those posted from here |
| `GET /accounting/drafts/{id}` | `accounting:journal` | A draft, its lines with account and party names, totals and `problems` (what stops it from being posted) |
| `POST /accounting/drafts`, `PUT /accounting/drafts/{id}` | `accounting:journal` | Save a draft `{date, memo, warehouse_id, lines: [{account_id, debit, credit, party_type, party_id, warehouse_id}]}`; empty lines are dropped; a posted one is refused |
| `DELETE /accounting/drafts/{id}` | `accounting:journal` | Delete a draft (never a posted one) |
| `POST /accounting/drafts/{id}/post` | `accounting:journal` | Post it (again: the same entry, `already: true`) |
| `POST /accounting/entries/{id}/reverse` `{date?, memo?}` | `accounting:journal` (manual) / `accounting:settings` (opening) | Reverse an entry by hand (below) |

`GET /accounting/settings` also returns `opening_entry` (the one in force, or null: the screens
offer the opening wizard), `first_entry_date` and `year_end_closings`; `GET /accounting/entries/{id}`
also returns `reverses_entry`, `reversed_by_entry`, `created_by_name` and `source_ref` (the document's
number or description); `GET /accounting/accounts` gives each account its `money_kind` (safe, wallet,
drawer, default_bank) when it is a money sub-account. No route edits or deletes a posted entry.

## Manual journal entries (D9)

A draft (`acc_drafts`) is saved and edited freely, even unbalanced; posting writes a normal entry
through `posting.post` (source `manual`, the draft's id, event `post`, dated the draft's date) and
keeps the draft read-only with its `entry_id`. Posting is refused, with every reason in Arabic
(`problems` lists them before posting):

- fewer than two lines, a line both debit and credit, debits ≠ credits;
- a group or stopped account; **inventory** (use a stock adjustment, which moves the quantities too);
  a **cashier drawer's** account (its cash belongs to the open shift);
- **receivables without a customer** or **payables without a supplier** on the line; a party on an
  account that doesn't take one (a customer only on receivables, a supplier only on payables, an
  employee only on employee advances or salaries payable);
- a date in the future, in a closed month (the posting service), or before the opening entry in force.

Decision where the design was open: **the operational balances follow a manual entry**, in the same
transaction, so the sub-ledgers keep matching (D8's nightly check stays quiet): a receivables line
changes the customer's `balance` and records a `customer_adjustments` row (kind `adjustment`, note "قيد
يومية JE-…"); a payables line changes the supplier's `balance` with a `supplier_transactions` row
(`debit` when we owe more, `credit` when less; no safe, `reference_doc` = the entry number); a line on
a safe's or wallet's account moves it through `finance.services.payments` (`ref_type`
`acc_entry`; an overdraft is refused). No event is emitted, so nothing is posted twice.

## Reversing by hand (D1)

`POST /accounting/entries/{id}/reverse` writes the opposite entry (`event = 'reverse'`,
`reverses_id` = the original) through `posting.reverse`; asking again returns the first reversal
(`already: true`) and changes nothing more. Allowed for:

- a **manual entry** (`accounting:journal`): dated today unless a date is given; the operational
  balances it moved are moved back;
- the **opening entry** (`accounting:settings`): dated the opening's own date unless a date is given, so
  the ledger has no opening at all until a new one is posted from the then-current balances.

Refused for a year-end closing (use `/year-end/reverse`), for an entry posted by a document (cancel
the document: sale, expense, drawer row… so the document and its entry stay matched), and for a
reversal itself. The date can't be in the future, before the original, or in a closed month.

## Nightly reconciliation (D8)

The automation job `accounting_reconciliation` (`app/platform/automation_worker/runner.py`, in the
`nightly` group of `deploy/server/mizan-cron.sh`) runs `reports.reconciliation` in every workspace that
has accounting on and at least one entry. When the ledger and the operational balances differ, every
active user whose role holds `accounting:view` gets one notification (type `accounting_reconciliation`,
link `/accounting/reports?tab=reconciliation`, the differences in `data_json`), at most once in 20
hours. It changes nothing. One workspace failing doesn't stop the others.

## Screens (`system/frontend/src/activities/general/modules/accounting/`)

Menus (manifest `screens`, placed after "finance" in every activity menu that has it) appear only
where the module is active and the role holds the screen's permission; the routes are guarded by the
module too (App.tsx), so a workspace without accounting sees nothing of it.

| Screen | Route | Permission | What |
|---|---|---|---|
| `screens/JournalPage.tsx` | `/accounting/journal` | view or journal | Posted entries with filters (date, source, account) and the entry detail (lines, source document link, reverses / reversed by, reverse); drafts and the manual entry form (balance shown as typed, party picker on receivables / payables / employee accounts, save, post) |
| `screens/AccountsPage.tsx` | `/accounting/accounts` | view (settings to edit) | The chart as a tree with today's balances; add a sub-account, rename, stop; the financial categories' accounts |
| `screens/ReportsPage.tsx` | `/accounting/reports?tab=` | view | Trial balance, income statement, balance sheet, general ledger (paged, running balance), party statement, reconciliation; date range and branch; CSV and print |
| `screens/PeriodsPage.tsx` | `/accounting/periods` | close or settings | Months (close in order; reopen with a reason), fiscal years (close, reverse the closing), the fiscal year's first month, the opening entry |
| `screens/OpeningPage.tsx` | `/accounting/opening` | settings | The opening wizard: start date, preview (lines, products skipped for having no cost), post. Every accounting screen shows a reminder while no opening entry is in force |

Export is in the browser (`lib.ts`): CSV with a byte-order mark so Excel reads the Arabic, and a
printable RTL page of the same table; nothing new on the server. The form's checks (`lineIssues`)
mirror the server's rules and are tested in `__tests__/lib.test.ts`; the server checks again.

## Reports (D8)

Every report reads `acc_accounts`, `acc_entries` and `acc_lines` only, takes a date range and an
optional branch (`warehouse_id` on the lines: a line with no branch, such as a customer receipt into a
safe, is left out of a branch report, so a branch trial balance or balance sheet need not balance
and says so with `balanced: false` / `difference`), and returns JSON with Arabic and English names.
Balances are debit minus credit; reports show them in the account's natural direction. The shapes are
typed in `system/frontend/src/activities/general/modules/accounting/api.ts`.

- **Trial balance.** Per account (groups roll their children up, `level` for indentation): `opening`
  = debit − credit of entries before `from`; `debit` / `credit` in `from..to`; `closing` = opening +
  debit − credit, also split into `closing_debit` / `closing_credit`. Accounts with no lines at all
  are hidden unless `include_zero`. `totals` add the postable accounts; `balanced` is true when
  period debits = credits and the opening and closing sides agree.
- **Income statement** (period only; the year-end closing is left out unless `include_closing=true`).
  Sections are chosen by role and group, never by code: `revenue` = income accounts except sales returns
  and the "other income" group; `sales_returns` = role `sales_returns` (debit − credit); `net_sales` =
  revenue − returns; `cogs` = role `cogs`; `gross_profit` = net sales − cogs; `operating_expenses` =
  the group holding `salaries_expense` (so sub-accounts added there count); `operating_profit` = gross
  profit − operating expenses; `other_income` = the group holding `other_income`; `other_expenses` =
  every other expense (cash shortage, other expenses, custom); `net_profit` = operating profit + other
  income − other expenses. Lines list non-zero accounts.
- **Balance sheet** at `as_of` (default today; every entry up to it). Assets = debit − credit, liabilities
  and equity = credit − debit. Equity adds the profit not yet closed into retained earnings, computed
  from the income and expense accounts: `prior_years_profit` (before the fiscal year of `as_of`, which
  starts on `fiscal_year_start`) and `current_year_profit` (from that start to `as_of`). With the
  year-end entry posted both are zero for the closed year. `balanced` is `|assets − (liabilities +
  equity)| < 0.01`; otherwise `difference` is the gap.
- **General ledger** of an account (a group takes its sub-accounts): lines in date, entry-number order;
  `balance` runs from `opening_balance` (before `from`) in the account's natural direction; each line
  carries `entry_id`, `number`, `source_type` / `source_id` / `event`, `memo`, `party_*`, `warehouse_id`.
  Paged; `closing_balance` and the totals cover the whole range.
- **Party statement** for a customer, supplier or employee: the lines carrying that party. The balance
  is what the party owes us (debit − credit) for a customer or employee and what we owe them (credit −
  debit) for a supplier, the sign of `customers.balance` / `suppliers.balance`; `ledger_balance` is the
  whole ledger's, `difference` = operational − ledger and `matches` says whether they agree.
- **Reconciliation** (a check; it changes nothing): receivables vs Σ `customers.balance`, payables vs Σ
  `suppliers.balance`, each safe/bank and each wallet vs its money account, inventory vs Σ on-hand
  quantity × average cost (`products.avg_cost`, else `cost_price`; difference under 1.00 is rounding),
  and up to 50 customers/suppliers whose own balance differs. Cashier drawers are not compared: a
  drawer's cash is the open shift's, which the ledger only learns from the opening entry. Employee
  advances are not compared (HR keeps no open-advance balance). A workspace that never posted an
  opening entry will show differences until it does.

## Opening entry (D10)

`GET /accounting/opening/preview` shows it; `POST /accounting/opening` posts it as source `opening`,
event `opening` (`accounting:settings`). The start date goes to `acc_settings.start_date`.

Lines (each is the operational balance **less what the ledger already holds** for that account or party,
so on an empty ledger it is the balance itself and after documents were already posted it adds only the
missing part):

| Section | Debit | Credit | Party / branch |
|---|---|---|---|
| customers | receivables, customer balance > 0 | receivables, balance < 0 | customer |
| suppliers | payables, balance < 0 | payables, balance > 0 | supplier |
| safes, banks, wallets | its money account (created if needed) | | |
| drawers | each branch's drawer: the open shifts' initial amount + cash sales and deposits − returns, expenses, withdrawals, revenue delivery (wallet rows excluded, cancelled rows excluded) | | branch |
| inventory | inventory: Σ on-hand quantity × average cost per branch (a product with no cost is skipped and listed in `skipped_no_cost`) | | branch |
| equity | opening balance equity (role `opening_equity`) when credits exceed debits | the same when debits exceed credits | |

Rules: the date can't be in the future, must be on or before the first existing entry of the workspace
(opening entries themselves don't count), and its month must be open; only one opening entry may be in
force: a second POST is refused until the first is reversed through the normal reversal, then a new one
is built from the then-current balances (each round has its own source id, so the same call is
idempotent). Employee advances are not carried.

## Year-end closing (D7)

Fiscal year `YYYY` starts on the first day of month `fiscal_year_start` of YYYY and ends a year less a day
later (the calendar year by default). `POST /accounting/year-end?year=YYYY` needs every month from the
year's start (or the first entry's month, if later) to its end to be closed, and the year to be over.
It posts one entry dated the last day (source `year_end`, event `close`; the only entry allowed into a
closed month): each income and expense account's balance for the year (per branch) is cleared and the
profit or loss goes to retained earnings (role `retained_earnings`), per branch. It is refused when the
year is already closed; `POST /accounting/year-end/reverse` reverses it. While a closing is in force the
months it covers can't be reopened (`/periods/{month}/reopen`) and `fiscal_year_start` can't change.
Reports take `include_closing=false` to show the closed year's profit.

Permissions (D11): `accounting:view`, `accounting:journal`, `accounting:close`,
`accounting:settings`; the accountant role holds all four, the manager holds view, the admin
everything. Periods (`/periods`, in finance) close and reopen with `accounting:close` or `finance`.
