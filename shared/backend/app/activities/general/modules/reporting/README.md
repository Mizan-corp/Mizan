# Reporting engine

`reporting`, a module of the `general` activity (SRS XMOD-04, CORE-10): the fixed reports, the
Excel exports, the company overview and the dashboard's sales widgets. Custom and scheduled reports
are not built yet.

## Files
- `scope.py` — what a report may cover: the bound workspace, the user's branches, whole days in the
  workspace's time zone, and the `reports:finance` permission.
- `service.py` — the report queries (sales, top products, by cashier, profit, daily items, periodic
  ledger, cash flow, aging, the inventory sheet's data).
- `printing.py` — the printable inventory sheet (HTML, every name escaped with `printing.routes.h()`).
- `routes/reports.py` — `/reports/*`; `routes/export.py` — `/export/*` (Excel);
  `routes/admin_overview.py` — `/admin/overview`.
- Screens: `system/frontend/src/features/reports/ReportsPage.tsx` (daily, monthly, top products, by
  cashier, by custom field, the inventory sheet), the widgets in
  `system/frontend/src/activities/general/modules/reporting/widgets.tsx`, and the profit cards of the
  finance screen's cash movements tab.

## Permissions
| Route | Needs |
|---|---|
| `/reports/sales/daily`, `/reports/sales/trend` (the "today's revenue" widget) | `reports` or `pos` |
| `/reports/sales/monthly`, `top-products`, `by-cashier`, `/reports/ledger/daily-items`, `/reports/ledger/periodic`, `/reports/fields/{record}/{key}`, `/export/sales` | `reports` |
| `/reports/profit`, `/reports/cash-flow`, `/reports/aging` | `reports:finance` |
| `/admin/overview` | `reports:finance` and every branch (manager or `supervise`) |
| `/reports/inventory/print` (print token) | `reports` or `inventory`; costs only with `reports:finance` |
| `/export/products`, `/export/stock` | `inventory` (stock costs only with `reports:finance`) |
| `/export/customers` / `suppliers` / `expenses` / `purchases` | `customers` / `purchases` / `finance` / `purchases` |

`reports:finance` is held by the standard admin, manager and accountant roles. Migration
`v98_ready_reporting` gave it to the workspaces' own roles that held `reports` together with
`finance` or `admin`.

## Branches
A manager or a holder of `supervise` sees every branch, or the one they pick. Anyone else sees only
the branches assigned to them (`user_warehouses`) when no branch is picked, and gets a 403 for
another branch; with no branch assigned their reports are empty. An unknown branch is a 404.
Expenses with no branch (company expenses, salaries), customers' and suppliers' payments and
suppliers' debts appear only in reports of every branch. Applies to every report and export.

## Dates
Dates are `date` parameters; a range covers both days fully (`>= from` and `< to + 1 day`), with day
boundaries in the workspace's time zone (`app/platform/tenancy/clock.py`: Africa/Cairo, the one the
ledger dates its entries in; there is no workspace time zone setting yet). `to` before `from` is a
400; a range longer than ten years is a 400.

## The figures
- **A sale's value** is its `net_total` (after line and invoice discounts) less its VAT
  (`sales.tax_amount`) when the documents carry VAT (ADR-014 step 6; until those columns exist the
  totals are used as they are, `service._vat_sql`). Returns are the return documents (ADR-014 D4),
  dated when made, and are taken off every sales figure (daily, monthly, trend, by cashier, top
  products, custom fields, the overview). Old full returns (the sale itself marked `returned`)
  count neither way. By cashier: the invoices a cashier issued less the returns they made, so the
  rows add up to the period's net sales.
- **A line's value** (top products, daily items): after its own discount and its share of the
  invoice discount, or `sale_items.net_amount` when stored.
- **Profit**: from the ledger (the income statement of the accounting module, summed over the
  user's branches) when the workspace has accounting and the period starts on or after the ledger's
  start (the opening entry's date, else the first entry's); `source: "ledger"`. Otherwise from the
  documents (`source: "operations"`), by the ledger's rules: sales less returns without VAT, the
  lines' cost, approved expenses dated in the period (the payroll's approved salaries expense
  included) without their VAT, and the drawer's expenses and withdrawals entered by hand; deposits
  entered by hand are other income. Expenses (paid from a safe or wallet) and drawer rows are
  separate records, so nothing is counted twice. Not in the operational figure: shift shortages and
  surpluses, safe withdrawals and wallet resets entered by hand.
- **Cash flow**: sales paid other than on credit (per method), customers' payments, purchase
  refunds and drawer deposits in; refunds of returns, supplier payments (once each), approved
  expenses other than salaries, salaries when paid (`hr_payroll_periods.paid_at`) and drawer
  expenses and withdrawals out. Moves between the company's drawers, safes and wallets are not cash
  flow.
- **Aging**: open credit invoices (`net_total` less paid and returned) issued by `as_of`, by the
  invoice's date; supplier invoices and payments up to `as_of`, payments settling the oldest
  invoices first. At most 500 parties are listed; the totals cover all.
- **Stock** (inventory sheet, stock export, overview): quantities from the movements, valued at the
  average cost (the listed cost while there is none), as the ledger values stock.
- Money is computed in `Decimal` and returned rounded to the piastre.

## Exports
Arabic column titles, number cells for money and quantities, date cells; at most 50,000 rows. The
product export's cost price, like the stock export's, only with `reports:finance`.

## Printing and errors
`/reports/inventory/print` is the print system's document (`/print/inventory/{id}` prints the same
sheet): a browser tab gets a refusal or a missing branch as an Arabic page (`PrintRoute`). The screens
open prints and downloads through `system/frontend/src/lib/documents.ts`, which shows the server's
Arabic message as a toast; a print or download nobody caught is still shown (`DocumentError`).

## Other modules' tables
Reports read other modules' tables with raw SQL, always with a workspace bound (RLS; `scope.require_workspace`,
called by `branch_scope`, `company_scope` and every export). They depend on these tables and columns
staying as they are; a change to one of them must update `service.py`, `routes/` and the tests here:

| Module | Tables |
|---|---|
| sales | `sales` (status, return_of, warehouse_id, cashier_id, customer_id, net_total, tax_amount, discount_amount, is_credit, paid_amount, created_at), `sale_items` (net_amount, unit_cost), `sale_payments` |
| pos | `shifts`, `drawer_transactions` (type, category_id, cancelled_at) |
| inventory | `products` (avg_cost, cost_price, retail_price), `categories`, `subcategories`, `stock_movements` (movement_type, `IN_TYPES`), `warehouses` |
| purchases | `purchase_orders`, `purchase_order_items`, `purchase_returns`, `suppliers`, `supplier_transactions` |
| finance | `expenses` (status, date, payment_method, tax_amount, warehouse_id), `expense_vendors`, `financial_categories`, `safes` |
| contacts | `customers`, `customer_payments` |
| hr | `hr_payroll_periods` (paid_at) |
| accounting | `acc_entries` (the ledger's start), and `accounting/services/reports.income_statement` for profit |
| platform | `users`, `user_warehouses`, `store_settings` |

## Known limits
- The aging report uses each invoice's current paid and returned amounts (they are not dated per
  invoice), so an `as_of` in the past still reflects later payments.
- Profit, cash flow, aging, the ledgers and the overview have no screen yet (only the finance
  screen's profit cards).
- The periodic ledger covers the last 52 periods.
