# ADR-014: Double-entry accounting

## Status
Proposed (2026-11-14), waiting for the owner's approval. Answers #25. Nothing is built yet.

## Context
Mizan has no accounting ledger. Money is tracked in about ten separate places:
- balance columns: `customers.balance`, `suppliers.balance`, `safes.balance`, `payment_wallets.balance`;
- log tables: `drawer_transactions`, `safe_transactions`, `wallet_transactions`, `customer_payments`,
  `supplier_transactions`, `sale_payments`;
- two expense systems: `expenses`, and drawer rows of type `expense`.

Each module updates these on its own, often with raw SQL. The reports each read a different subset, so
they disagree with each other.

The finance screen's "journal entry" and "trial balance" tabs are fake. The account names are hard-coded,
and "posting" a journal entry creates a draft expense.

A full map of today's money flows (2026-11-14, in #25) found these problems:

1. **Money moves without a record.** This happens with bank and cheque sale payments, the amount paid on
   a purchase, supplier payments, payroll "paid", HR advances, customer receipts taken while no shift is
   open, a shift's deposit amount, and quotations confirmed into a safe.
2. **Cancelling and deleting destroy history.** `cancel_sale` deletes the payment, drawer and
   customer-payment rows. Approved expenses can be deleted without reversing the money. Drawer rows can be
   deleted. Deleting a customer deletes their payments (cascade). `reset_stock` deletes stock movements.
3. **Returns have no document of their own.** A full return changes the status of the original sale. A
   partial return stores `total = 0` and links to its sale only by text in its notes.
4. **Confirmed sales can be edited.** Changing an item's quantity or deleting an item leaves the sale's
   totals, the customer's balance and the payments stale.
5. **There is no cost of goods sold.** POS never sends `unit_cost`, so it is stored as 0. A product's
   `cost_price` is simply the last purchase price.
6. **There is no tax data.** The VAT printed on invoices is worked out afterwards (14 % of the total).
   No screen sets the workspace's tax number.
7. **Closing a period blocks nothing.** The guard only checks the current month, and the current month
   can't be closed.
8. **Payroll is inconsistent.** Bonuses are deducted as if they were advances. Approval writes one lump
   expense, and no cash ever leaves.
9. **Clinic payments create sales.** Each clinic payment creates a new `Sale` with the same invoice
   number. Hotel, storefront, school and other modules keep money in their own tables.

## Decision

### D1. A ledger module with an append-only journal
A new module `accounting` (general family) depends on `finance`. It adds three tenant tables, all
`TenantScoped` with RLS, and all amounts are `Numeric(14,2)`, never Float:

- **`acc_accounts`** (the chart of accounts):
  - `code` and `name` / `name_en`;
  - `type`: asset, liability, equity, income or expense;
  - `parent_id`, and `is_group` (group accounts can't take postings);
  - `role`: a stable key such as `cash`, `receivables`, `inventory`, `vat_output` or `cogs`, used by the
    posting rules;
  - `active`.
- **`acc_entries`** (one journal entry):
  - `number`, and `date` (the posting date);
  - `source_type`, `source_id` and `event`, for example `sale` / id / `confirm`;
  - `memo`, `warehouse_id` (the branch), `created_by`;
  - `reverses_id`.
- **`acc_lines`**: `entry_id`, `account_id`, `debit`, `credit`, `party_type` / `party_id` (customer,
  supplier or employee), `warehouse_id`.

Posted entries are never updated or deleted, and the API has no edit or delete for them. A mistake is
corrected by a **reversing entry**. An entry must balance (total debit = total credit). The service
checks this, and so does a deferred constraint trigger in the database.

`(source_type, source_id, event)` is unique, so posting the same document twice does nothing.

### D2. The chart of accounts is data
Mizan ships one standard Egyptian chart at `accounting/charts/eg_standard.json`, in Arabic and English:
1 assets, 2 liabilities, 3 equity, 4 revenue, 5 expenses. It follows the usual layout of Egyptian
practice.

It is copied into a workspace when the module is enabled. The owner (with `accounting:settings`) can
rename accounts and add sub-accounts. **Posting rules find accounts by `role`, never by code**, so a
renumbered chart keeps working.

Activity variants can add accounts, for example insurance receivables for clinics or room revenue for
hotels.

Each safe, wallet, bank account and branch drawer gets its own sub-account, created automatically under
cash or banks, so the ledger shows where the money is.

### D3. Posting rules: one per document, run from hooks
Each money event has one posting function in `accounting/posting/`. Modules don't write journal entries
themselves: they emit the hooks they already emit, plus a few new ones. The accounting module subscribes
to them, in the same transaction, so a document and its entry are saved together or not at all.

| Event | Debit | Credit |
|---|---|---|
| Sale confirmed | Cash / wallet / bank (per payment) or receivables (credit) | Sales revenue (net of discount); VAT output |
| …the same sale, cost | Cost of goods sold | Inventory (at average cost, D5) |
| Sale return | Sales returns; VAT output | Cash / receivables, per refund |
| …the cost of the return | Inventory | Cost of goods sold |
| Sale cancelled | The reversing entry of the sale (D1) | |
| Customer receipt | Cash / wallet / bank | Receivables (party) |
| Purchase received | Inventory; VAT input | Payables (party) |
| Supplier payment | Payables (party) | Cash / wallet / bank |
| Purchase return (new) | Payables | Inventory; VAT input |
| Expense approved | The expense account of its category; VAT input | Cash / wallet / bank / payables |
| Payroll approved | Salaries expense | Salaries payable (and advances recovered) |
| Payroll paid (new: picks a safe) | Salaries payable | Cash / bank |
| HR advance (new: picks a safe) | Employee advances (party) | Cash |
| Stock adjustment or damage | Inventory difference / damage expense | Inventory (or the reverse) |
| Shift closed with a difference | Cash shortage (or the drawer) | The drawer (or cash surplus income) |
| Revenue delivered (drawer → safe), safe ↔ wallet transfers | The receiving account | The giving account |
| Clinic invoice paid | Cash / insurance receivables | Clinic revenue |

Each event maps to one category account through `financial_categories` (each category gets an
`account_id`). A category without an account goes to "other expenses" or "other income", so posting never
fails because of setup.

### D4. Fix the money flows first
The ledger can only be right if the documents are. These changes come before any posting, and each one is
also a fix in its own right:

- **No hard deletes of confirmed money documents.** Cancelling a sale sets its status and keeps the
  payment rows, which are then reversed. An approved expense can be cancelled, which reverses its money,
  but not deleted. A drawer row is cancelled, not deleted. A customer or supplier with transactions can be
  deactivated, not deleted. `reset_stock` is only allowed before the first movement.
- **Returns are their own documents**, with `return_of` pointing to the sale, real totals and their own
  date. The original sale stays `confirmed`, and its `returns_total` is updated.
- **Confirmed sales are not edited.** The quantity-change and delete-item routes on confirmed sales are
  removed; corrections go through a return.
- **Every payment says where the money went.** Bank and cheque payments go to a bank account (a safe of
  type bank). Supplier payments and the amount paid on a purchase come from a safe or wallet. Customer
  receipts without an open shift go to a chosen safe. Payroll payments and advances come from a safe.
- **The cost of a sale is computed on the server** (D5), never taken from the client.
- **Clinics:** one sale per clinic invoice, and payments are recorded as payments, not as new sales.
- **Payroll:** advances, deductions and bonuses are summed separately.
- **The fake journal and trial-balance tabs are removed** from the finance screen until D9 replaces
  them.

### D5. Inventory cost: weighted moving average
Each product gets `avg_cost`, kept for the whole workspace. Each purchase receipt recalculates it:
(old quantity × old average + new quantity × cost) ÷ new quantity. Every outgoing movement records the
average at that moment, and so does the sale line. That figure is the cost of goods sold.

Inventory is **perpetual**: the cost of goods sold is posted with each sale, not worked out at month
end.

`cost_price` stays as "last purchase price" for display. Pharmacy batches keep tracking quantities and
expiry dates; the cost still comes from the average. Costing each batch separately (FIFO) can come later
if customers need it.

### D6. VAT on documents, ready for ETA
- **Workspace settings:** `vat_registered` (default off), `tax_number`, and `prices_include_vat`
  (default on, which is how Egyptian shops price).
- **Products** get a `tax_code`: standard 14 %, zero-rated or exempt.
- **Sales, purchases and expenses** store `tax_amount` per line and in total, taken from the code at the
  time of the document. They are never worked out afterwards.

When the workspace isn't VAT-registered, nothing is taxed and invoices show no VAT. ETA e-invoicing (#91)
will later read these stored amounts; it adds no tax logic of its own.

### D7. Periods that really close
- Every entry has a posting `date`. For documents, this is the document's date, which can't be in the
  future.
- Posting into a **closed month is refused** with a clear Arabic message, from any route, because the
  check sits in the posting service itself and not in a route guard.
- Closing a month requires every earlier month to be closed. Reopening a month requires
  `accounting:close` and a reason, and is logged.
- A **fiscal year start** setting (default January) enables a year-end closing entry: income and expense
  accounts are moved into retained earnings.

The current `accounting_periods` table is kept and gains this enforcement.

### D8. Reports read only the ledger
All reports are computed from `acc_lines`:
- trial balance;
- income statement;
- balance sheet;
- general ledger per account;
- statement per customer, supplier or employee.

Each one can be filtered by date range and by branch.

The operational balances (customers, suppliers, safes, wallets) stay as fast caches for the screens. A
nightly check compares them with their ledger accounts and flags any difference to the owner. The ledger
is the truth.

`/reports/profit` and the cash-flow report are rebuilt on the ledger once it exists.

### D9. Manual journal entries
Holders of `accounting:journal` can save draft entries and then post them. A manual entry must balance
and its accounts can't be group accounts. Control accounts are restricted so the sub-ledgers keep
matching:
- receivables and payables need a party on the line;
- inventory can't be posted manually: use a stock adjustment.

A posted manual entry is corrected by reversing it, as in D1.

### D10. Starting the ledger, and existing workspaces
Enabling the module (or a new workspace that has it) creates an **opening entry** on a start date the
owner picks. It is built from today's balances: customers, suppliers, safes, wallets and banks, and the
stock value at average cost. The difference goes to opening equity. Past documents are not re-posted.

For existing products, the starting `avg_cost` is their current `cost_price`.

### D11. Permissions and roles
New permissions:
- `accounting:view` (reports);
- `accounting:journal` (manual entries);
- `accounting:close` (periods and the year end);
- `accounting:settings` (the chart and account mapping).

The accountant role gets all four, the manager gets view, and the admin gets everything, as with every
permission.

### D12. Order of work
Each step is its own PR with tests:

1. **D4 fixes** to the existing modules (these are bugs today regardless).
2. **The ledger core:** tables, chart, posting service, period check (D1, D2, D7), with posting for
   sales, returns, POS and drawers, customer receipts, safes and wallets, and expenses.
3. **Purchases**, supplier payments and purchase returns, D5 average cost and cost of goods sold, stock
   adjustments, payroll and clinic invoices.
4. **Reports and the opening entry** (D8, D10).
5. **Screens:** chart of accounts, journal (D9), reports, and period close.
6. **VAT data** on documents (D6).

## Alternatives considered
- **Reports over today's tables, with no ledger.** Quick, but it isn't accounting: no balance sheet, and
  every gap above stays. Accountants would still need other software.
- **Modules write their own journal entries.** This spreads accounting rules across a dozen modules.
  One posting function per event, run from hooks, keeps the rules in one place and keeps modules simple.
- **An external accounting engine** (for example Odoo's, or a separate service). That means a second
  database, syncing between the two, and losing tenant isolation guarantees. Mizan is a modular
  monolith (ADR-001).
- **FIFO cost layers.** More exact, but it adds a layer table and makes returns and adjustments more
  complex. The moving average is accepted in Egyptian practice and is enough for now.
- **Posting at month end in a batch.** Simpler hooks, but there are no live balances and an error in
  one document is found late. Posting in the same transaction as the document is safer.

## Consequences
- Accountants get a real trial balance, income statement and balance sheet per branch, and they can
  close months.
- Documents and money get stricter: no deletes, no edits after confirmation, a stated source for every
  payment. Some screens lose actions users have today (deleting an approved expense, editing a confirmed
  sale), and returns or cancellations take their place.
- Every money write gets one more insert (the entry and its lines) in the same transaction. That is a
  small cost.
- Modules outside general sales keep their own invoices (hotel, storefront, school…) until each gets a
  posting rule. Their money is not in the ledger until then; the reports say so.
- Prepares ETA (#91): tax amounts are stored on every document.

## Open questions for the owner
1. Is the average cost **per workspace** (proposed) or **per branch/warehouse**?
2. Should the accounting module be **on by default** for new general workspaces, or something an owner
   enables?
3. Should prices **include VAT** by default (proposed)?
