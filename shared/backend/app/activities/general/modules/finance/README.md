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
| Expenses | `GET /expenses`, `POST /expenses`, `PUT /expenses/{id}`, `POST /expenses/{id}/approve` (the money leaves its safe or wallet), `POST /expenses/{id}/cancel` (it comes back), `DELETE /expenses/{id}` (drafts and rejected only), `GET /expenses/summary` | `finance` (summary: `finance` or `reports`) |
| Vendors and categories | `/expense-vendors`, `/financial-categories` (type `income` or `expense`; a used category is stopped, not deleted) | `finance` (categories list: signed in) |
| Reports | `GET /reports/ledger` (sale lines, returns and drawer movements of a range, paged; totals over the whole range), `GET /wallets/summary` (confirmed invoices per payment method), `GET /financial-ledger` (drawer movements by category) | `finance` or `reports` (`financial-ledger`: `finance`) |
| Periods | `GET /periods`, `POST /periods/{month}/close`, `POST /periods/{month}/reopen` `{reason}` | read: `finance` or an accounting permission; close and reopen: `accounting:close` or `finance` |
| Users' access | `GET/PUT /permissions/{user_id}` | `users` |
| Audit log | `GET /audit-log` | `admin` |

## Rules

- **Balances change only through movements**, under a row lock, each logged with the document it
  belongs to (`services/safes.py`, `services/wallets.py`, `services/payments.py`). A safe or wallet
  holding money can't be stopped; a stopped one takes no movement.
- **A new workspace gets a main safe** (`ensure_default_safe`, called by
  `platform/tenancy/service.create_workspace` and the on-site setup), so expenses can be approved
  and receipts taken from the first day. Demo data brings its own.
- **Idempotent money writes** (`app/framework/idempotency.py`): deposit, withdraw, wallet → safe and
  wallet reset accept an `Idempotency-Key` header or a `client_id` in the body; a retry returns
  the first answer, the same key with another request is a 422. The screens send a `client_id`
  per attempt.
- **Branches**: reads that cover branches (`/reports/ledger`, `/wallets/summary`, `/expenses`,
  `/expenses/summary`, `/financial-ledger`) check `verify_warehouse_access` for the branch asked
  for; without one, a user who has neither the manager flag, `supervise` nor `finance` (accountants) sees only their own
  branches (and, for expenses, the company-wide ones) (`services/access.py`).
- **Periods** (`services/periods.py`): every month from the first one the books know to the
  current month (Africa/Cairo). With accounting on, the books start at the first journal entry
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

`/finance` (`system/frontend/src/activities/general/modules/finance/FinancePage.tsx`): the cash
book, safes and wallets (create, edit, stop, deposit, withdraw, transfer, history;
`components/TreasuryWorkspace.tsx`), expenses and their approval, and periods
(`components/PeriodsWorkspace.tsx`).

## Not yet

- `strict_safe_balance` (manifest setting) is not read; recurring expenses don't recur (FIN-9).
- No screens yet for categories, expense vendors, rejecting or editing an expense, wallet reset
  (FIN-14).

## Dependencies
core. Tests: `system/backend/tests/test_money_flows_finance.py`, `test_ready_finance_contacts.py`;
`e2e/api/test_expenses.py`, `test_finance.py`, `test_periods.py`, `test_shifts_safes.py`.
