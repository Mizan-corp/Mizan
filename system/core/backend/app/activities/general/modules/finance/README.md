# Finance & Treasury (`finance`)

The money that isn't a sale: safes and bank accounts, payment wallets, expenses and their
approval, the daily cash book, and month-end closing. A core module of the `general` activity:
always on. Where money moves it posts to the ledger through events when the accounting module is
on (ADR-014; the posting rules are in `accounting/posting/finance.py`).

Permission: `finance` (declared here). Reports read with `finance` or `reports`.

## What it does

| Area | Routes | Who |
|---|---|---|
| Safes (a bank account is a safe of type `bank`) | `GET /safes` (balances only for `finance`/`reports`; `include_inactive`), `POST /safes`, `PUT /safes/{id}` (only the fields sent), `DELETE /safes/{id}` (stops an empty safe), `POST /safes/{id}/activate`, `GET /safes/{id}/history` | list: signed in; the rest: `finance` |
| Movements by hand | `POST /safes/{id}/deposit` (posted as other income; names no shift), `POST /safes/{id}/withdraw` (other expenses), `POST /safes/transfer` (wallet → safe) | `finance`; withdraw: `finance` and the manager flag |
| Wallets | `GET /wallets`, `POST /wallets`, `PUT /wallets/{id}`, `DELETE /wallets/{id}` (stops an empty wallet), `POST /wallets/{id}/activate`, `POST /wallets/{id}/reset-balance`, `GET /wallets/{id}/history` | list: signed in; the rest: `finance` |
| Expenses | `GET /expenses` (paged: `page`, `page_size` ≤ 200; filters `status`, `search`, dates, branch, vendor, category, `recurring`), `POST /expenses` (dated today in the workspace's time zone when no date is given), `PUT /expenses/{id}`, `POST /expenses/{id}/approve` `{approved}` (approve: the money leaves its safe or wallet; or reject), `POST /expenses/{id}/cancel` (it comes back), `DELETE /expenses/{id}` (drafts and rejected only), `GET /expenses/summary` | `finance` (summary: `finance` or `reports`) |
| Vendors and categories | `/expense-vendors`, `/financial-categories` (type `income` or `expense`; a used category is stopped, not deleted) | `finance` (categories list: signed in) |
| Reports | `GET /reports/ledger` (sale lines, returns and drawer movements of a range, paged; totals over the whole range), `GET /wallets/summary` (confirmed invoices per payment method), `GET /financial-ledger` (drawer movements by category) | `finance` or `reports` (`financial-ledger`: `finance`) |
| Periods | `GET /periods`, `POST /periods/{month}/close`, `POST /periods/{month}/reopen` `{reason}` | read: `finance` or an accounting permission; close and reopen: `accounting:close` or `finance` |
| Users' access | `GET/PUT /permissions/{user_id}` | `users` |
| Audit log | `GET /audit-log` | `admin` |

## Rules

- **An expense's life**: a draft is approved (paid) or rejected; nothing else is decided. Approved
  is final (cancelling puts the money back and keeps it as cancelled); rejected is closed too (not
  approved later, which would pay what was refused; enter it again as a new draft). After a
  decision only the notes and the recurrence change. A draft or a rejected expense can be deleted.
- **A safe's balance** (`strict_safe_balance`, the module's setting, on by default): approving an
  expense larger than its safe's balance is refused (400), and a stopped safe pays nothing. A
  workspace that switches the setting off may take a safe below zero with an expense (only with an
  expense: withdrawals, supplier payments, salaries and advances never overdraw). Wallets never go
  below zero.
- **Recurring expenses** (`services/recurring.py`): an expense marked recurring (weekly, monthly
  by default, or yearly, optionally until an end date) gets its next occurrence every night when
  its date comes (`recurring_expenses` in the automation runner, nightly group of
  `deploy/server/mizan-cron.sh`): a new draft with the same vendor, category, branch, amount, VAT,
  description and source, dated that day, waiting for approval (no money moves by itself). Each
  occurrence is used once (`recurred_at`, under a row lock); the draft carries the series on
  (`recurred_from` points back). The series continues whatever an occurrence's status; it stops at
  its end date, when recurrence is switched off (allowed after a decision too), or when the latest
  draft is deleted. A run catches up missed occurrences. Months add like PostgreSQL's intervals
  (the 31st is followed by the last day of a shorter month, and stays there).
- **Categories**: one that an expense or a drawer movement carries is stopped, never deleted (the
  drawer movements' key would clear their category); an unused one is deleted.

- **Balances change only through movements**, under a row lock, each logged with the document it
  belongs to (`services/safes.py`, `services/wallets.py`, `services/payments.py`). A safe or wallet
  holding money can't be stopped; a stopped one takes no movement.
- **A new workspace gets a main safe** (`ensure_default_safe`, called by
  `platform/tenancy/service.create_workspace` and the on-site setup), so expenses can be approved
  and receipts taken from the first day. Demo data brings its own.
- **Idempotent money writes** (`app/framework/idempotency.py`): deposit, withdraw, wallet → safe and
  wallet reset accept an `Idempotency-Key` header or a `client_id` in the body; a retry returns
  the first answer, the same key with another request is a 422. The screens send a `client_id`
  per attempt. Two requests with one key at once: the second waits for the first (the unique
  index) and gets its answer, with one movement (`tests/test_d_fixes.py`). Keys older than 7 days
  are deleted every night (job `idempotency_cleanup`, nightly group of `deploy/server/mizan-cron.sh`).
- **Branches**: reads that cover branches (`/reports/ledger`, `/wallets/summary`, `/expenses`,
  `/expenses/summary`, `/financial-ledger`) check `verify_warehouse_access` for the branch asked
  for; without one, a user who has neither the manager flag, `supervise` nor `finance` (accountants) sees only their own
  branches (and, for expenses, the company-wide ones) (`services/access.py`).
- **Periods** (`services/periods.py`): every month from the first one the books know to the
  current month in the workspace's time zone (`app/platform/tenancy/clock.py`, Africa/Cairo; the
  same month `require_open_period` checks before a money write). With accounting on, the books start at the first journal entry
  (the same months as `/accounting/periods`); without it, at the first sale, expense, safe,
  wallet or drawer movement or customer receipt. Months close in order, never the current one;
  reopening goes from the latest closed month back, with a reason, logged; a month of a fiscal
  year with a closing entry in force doesn't reopen.
- **Days are the workspace's days**: date filters run from the first day's midnight to the
  midnight after the last day, in Africa/Cairo. Dates and ids are typed query parameters (bad
  input is a 422, unknown ids a 404 with an Arabic message).
- **Amounts** are `Decimal` with at most 14 digits and 2 decimals.

## Files

| File | What |
|---|---|
| `routes/safes.py`, `routes/wallets.py`, `routes/expenses.py`, `routes/finance.py`, `routes/ledger.py`, `routes/periods.py` | The API above |
| `services/safes.py`, `services/wallets.py`, `services/payments.py`, `services/expenses.py` | Money movements (callers commit) |
| `services/ledger.py` | The daily ledger and `day_bounds` |
| `services/periods.py` | The months and their close/reopen rules |
| `services/access.py` | Permissions and branch scoping of the reads |
| `models/` | `safes`, `safe_transactions`, `safe_deposits`, `payment_wallets`, `wallet_transactions`, `expenses`, `expense_vendors`, `financial_categories`, `accounting_periods` |

## Screen

`/finance` (`system/erp/frontend/src/activities/general/modules/finance/FinancePage.tsx`): the cash
book; safes and wallets (create, edit, stop, deposit, withdraw, transfer, history, a wallet's reset
with a confirmation and a client id; `components/TreasuryWorkspace.tsx`); expenses
(`components/ExpensesWorkspace.tsx`: paged and filtered, create and edit a draft, approve, reject
with a reason, cancel, delete, the recurrence; after a decision only the notes and recurrence);
categories and expense vendors (`components/CategoriesVendorsWorkspace.tsx`: create, edit, stop or
delete); and periods (`components/PeriodsWorkspace.tsx`). Amounts show the workspace's currency
(`system/erp/frontend/src/lib/currency.ts`). The rules the screens mirror are in `lib.ts` (tested).

## Not yet

- The manifest still lists the customers (`/customers`) and suppliers (`/suppliers`) screens, which
  belong to contacts and purchases: their screen ids are kept because saved role layouts name them.

## Dependencies
core. Tests: `system/erp/backend/tests/test_money_flows_finance.py`, `test_ready_finance.py`, `test_b_platform.py`, `test_c_finance.py`;
`e2e/api/test_expenses.py`, `test_finance.py`, `test_periods.py`, `test_shifts_safes.py`.

## Expense VAT (ADR-014 D6, step 6)
`expenses.tax_amount` is the input VAT included in `amount`, typed from the supplier's tax invoice
(optional, default 0). It is refused in a workspace that isn't VAT-registered and must be less than
the amount (`services/expenses.check_tax`, on create and update). The ledger posts the category's
account with `amount − tax_amount` and VAT input with the tax; the money leaving is `amount`.
