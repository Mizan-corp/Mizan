# Production readiness of the general modules

Owner's request (2026-11-17): make every general module production-ready; activity variants are out of
scope for now. Decided the same day: **the 11 built modules first**; the 11 placeholders stay hidden
(status `planned`, never mounted) and are built afterwards one at a time; the storefront becomes the
website builder of ADR-015.

This file is the plan and the record. Each finding has an id (`SAL-3`), a severity and the place in
the code (paths are relative to `system/core/backend/app/activities/general/modules/` unless they start
with `shared/`, `system/` or `e2e/`; frontend `F/` = `system/erp/frontend/src/`). Tick a finding with the PR
that closed it. Line numbers are from the audit of 2026-11-17 and drift; search by the quoted name.

## The bar
A module is ready when all of these hold:
1. **Security:** every route needs a sign-in and a fitting permission (writes and sensitive reads such
   as costs, profit, salaries, balances never with sign-in alone); no cross-workspace access (models
   tenant-scoped, tables with `tenant_id` and RLS, raw SQL only while a workspace is bound, ids from the
   request can't reach another workspace's rows); branch restrictions enforced; public routes bind the
   right workspace and expose only public fields; input validated (types, bounds, lengths, enums);
   nothing secret or personal in logs or error answers.
2. **Data integrity:** multi-step writes in one transaction; balances and stock with row locks or atomic
   SQL; every money movement posts to the ledger (ADR-014) or is documented as not yet posted;
   confirmed documents are cancelled or returned, never edited or deleted; idempotency where retries
   happen (offline sync, payments, callbacks, double clicks).
3. **Errors:** Arabic messages with 4xx codes; no input can cause a 500; not-found is a 404 within the
   workspace.
4. **Tests:** main flows, permission denials and workspace isolation in the backend suite; e2e/api
   covers every route.
5. **Screens:** every capability has a working screen with loading, empty and error states, actions
   gated by permission, Arabic labels; no placeholders, dead buttons or made-up data.
6. **Performance:** lists paginated or bounded; no N+1 in hot paths; indexes for the filters used.
7. **Completeness:** no TODO stubs; every API call of a screen exists; manifest and README accurate;
   settings declared in the manifest are read (or removed).

## Status (2026-11-17)

| Module | Verdict | Size | Notes |
|---|---|---|---|
| accounting | ready, small work | S | ADR-014 steps 1–6 built (#146–#152) |
| sales | not ready | L | price/stock checks, offline duplicates, numbering |
| pos | not ready | M | hand-made drawer rows, revenue delivery |
| inventory | not ready | L | clamped balances, unposted manual movements, missing screens |
| purchases | needs work | M | permissions inverted, totals missing |
| finance | not ready | L | (escalation fixed in #154), no safe/wallet creation, wrong totals |
| contacts | needs work | M | write-off by cashier, ledger paging |
| hr | not ready | L | payroll editable after approval, salaries readable by all |
| operations | needs work | M | goods receipt without ledger, no branch check |
| reporting | not ready | L | permissions, last day dropped, wrong money figures |
| storefront | not ready | → ADR-015 | hide (S0), rebuild as the website builder |
| customer_portal, supplier_portal, subscription_billing, documents, workflow, projects, scheduling, quality, assets, pricing, loyalty | not built | L each | placeholders, hidden; later |

## Done
- **PLAT-1** (critical) PDFs embedded server files (WeasyPrint followed `file://`), invoice HTML unescaped — #153.
- **PLAT-2** print/owner/developer tokens worked as ERP sign-ins — #154.
- **PLAT-3** a token without `tid` left the RLS bypass on for the whole request — #154.
- **PLAT-4** 500 answers carried the exception text (SQL and values); validation logs carried submitted data — #154.
- **FIN-1** `PUT /permissions/{id}` allowed granting `admin` (escalation); the users screen couldn't save most permissions — #154.
- **SET-1** `GET /settings` returned every workspace's settings without sign-in — #151.
- **STO-0** the first storefront taken out of service (status `planned`, not mounted, not offered) — #156.
- **Phase A** (#162, integrating #157–#161, 2026-11-17):
  - sales: SAL-1 to SAL-9; pos: POS-1, POS-2, POS-3, POS-7; PLAT-6 for sales and safe deposits
    (`doc_counters`); PLAT-9 for `sales` and `shifts`.
  - inventory: INV-1, INV-2, INV-3, INV-5, INV-6, INV-7 (part of INV-8); operations: OPS-1 (goods
    receipt removed: 410, through purchases), OPS-2, OPS-3; purchases: PUR-1, PUR-2 (parts of PUR-3, 5, 7).
  - hr: HR-1 to HR-8, HR-10, HR-11; PLAT-5 for HR's reports.
  - reporting: REP-1 to REP-7, REP-11, REP-13, REP-16, REP-17 (parts of REP-8, 9, 10, 12, 14, 15, 18).
  - finance: FIN-2 to FIN-8, FIN-10 to FIN-13 (parts of FIN-14, 15); contacts: CON-1 to CON-6 (part of CON-7).
  - New permissions: `sales:cancel`, `sales:return`, `sales:override_price`, `sales:negative_stock`,
    `inventory:opening`, `purchases` (wider defaults), `payroll:approve`, `payroll:pay`,
    `reports:finance`. Migrations v95 to v99 keep what a workspace's own roles could already do.

- **Phase B** (#164, 2026-11-20): SAL-10, SAL-12, POS-4 (lockout of the guesser only), POS-5, POS-10,
  OPS-5, OPS-6, PLAT-6 for operations; INV-4, INV-8, INV-11, PUR-3, PUR-5, PUR-6, PUR-7; PLAT-5 (every
  print route escaped and permissioned), PLAT-7, PLAT-8 (one workspace clock), FIN-15, CON-7, REP-18,
  ACC-3. Found on the way: `PUT /users/{id}/warehouses` reached other workspaces; any print token printed
  any document; HR settings could be saved by one workspace only.
- **Phase C** (#166): SAL-11, POS-6, POS-8, POS-9 and the price-override control; INV-9, INV-10, PUR-4
  (partial receipts as GRN documents, one ledger entry each), OPS-4, pharmacy batches through purchases;
  FIN-9 (strict safe balance, recurring expenses that recur), FIN-14, HR-9 (carried advances), HR-12,
  HR-15, and the reporting screens (profit, cash flow from the ledger, aging, overview, ledgers).
- **Phase D** (#167, 2026-11-20): the route security sweep (`tests/test_route_security_sweep.py`: every route
  signed in or on a reviewed allow-list, permission denials, cross-workspace reads) and the 15 holes it
  found (module settings exposing secrets, 29 activity modules open to any signed-in user, notifications
  spoofing, customer balances to everyone, demo seeds crashing every workspace but the first, …);
  ACC-2 (accounting e2e); the receipt cancel that left invoices paid; partial module-settings saves;
  collections as an assembly helper (not sold); HR-13, HR-14; ACC-1 (journal numbers from a counter);
  PLAT-9; idempotency keys cleaned nightly.

**In production (2026-11-21):** phases B, C and D were released on 2026-11-21 (release `607534cd`,
migrations through `v107_d_fixes`; latitude's standby replicated). The phase B release first failed twice:
after the move to Mizan-corp the images still went to `ghcr.io/ammar0xff` (fixed by #165), then the
pre-release backup couldn't write because homie's `media` partition hadn't been mounted since the
2026-11-19 boot (mounted again; docker now waits for `/mnt/media`).

**Status after phase D:** every finding of the 2026-11-17 audit for the 11 built modules is closed or
recorded as a known limit below. Known limits kept on purpose: collections can't be sold (a bundle needs a
sales-line redesign); activity modules check that the workspace uses them but declare no permissions
(activity variants are out of scope); rate limits count per worker without REDIS_URL; the workspace clock
is fixed to Africa/Cairo (no setting yet).

## What remains after phase A
- **Phase B (permissions, validation, error codes):** SAL-10, SAL-12; POS-4 (manager password brute
  force), POS-5, POS-10; INV-4, the rest of INV-8; the rest of PUR-3, PUR-5, PUR-7; OPS-5, OPS-6; PLAT-5
  for the other print builders (`/print/inventory` has no permission or branch check yet); PLAT-6 for
  operations (helper `app/platform/archive/numbering.py`); the rest of PLAT-7; PLAT-8 (time zone:
  `require_open_period`, POS); FIN-15 rest; CON-7 rest; REP-18 rest; ACC-3.
- **Phase C (screens and completeness):** SAL-11 (sales screen); POS-6 (summary by `sale_payments`),
  POS-8, POS-9; INV-9, INV-10, INV-11; PUR-4 (order lifecycle, partial receipt); OPS-4 (stock requests);
  FIN-9 (strict balance, recurring expenses), FIN-14 rest (categories, vendors, reject/edit expense,
  wallet reset); HR-9 (unrecovered advances), HR-12 (rules in settings, money in Decimal), HR-15
  (screens); REP-8/9/10/12/14/15 rest and screens for profit, cash flow, aging, ledgers, overview;
  price-override control on the POS screen; operations numbering; the pharmacy batches posting
  (*done: `POST /pharmacy/batches` is 410, batches come in on the purchase receipt*).
- **Phase D (tests and performance):** permission and isolation tests for every route; HR-13 (paging,
  bulk loads), HR-14 (audit); ACC-1 (numbering counter), ACC-2 (e2e for accounting); PLAT-9 rest; old
  idempotency keys clean-up; a test of simultaneous requests with one idempotency key.

## Order of work
1. **Phase A — blockers and money/stock corruption** (one PR per module, tests that fail on the old
   code): SAL-1..5, POS-1..3, INV-1..3, HR-1, HR-4, OPS-1, REP-1..4, FIN-2, CON-1, STO-0, PLAT-5..7.
2. **Phase B — permissions on reads, branch scoping, validation, error codes** across all modules
   (the HIGH and MEDIUM security items).
3. **Phase C — screens and completeness** (missing screens, settings that do nothing, docs).
4. **Phase D — tests to the bar** (permissions, isolation, e2e for every route) and performance (indexes,
   paging, N+1).
5. Then ADR-015 (storefront rebuild) and the placeholders.

## Cross-cutting (platform)
- **PLAT-5** HIGH — other HTML builders escape inconsistently (HR report `month` in
  `hr/services/reports.py`, check every `f"""<html` in printing and modules); escape everything with
  `printing.routes.h()`, add a test that renders each print route with markup in every text field.
- **PLAT-6** MEDIUM — document numbers from the global `invoice_seq` shared by all workspaces (sales
  INV/RET/DEP, operations): per-workspace counters `(tenant, doc_type)` with a row lock.
- **PLAT-7** MEDIUM — many routes type ids and dates as `str` and parse them inside (`uuid.UUID()`,
  `fromisoformat`), so bad input is a 500 and asyncpg rejects string dates: type them as `uuid.UUID` /
  `date` query parameters everywhere (sales, finance, reporting, hr, purchases).
- **PLAT-8** MEDIUM — time zones: naive day boundaries are treated as UTC; reports and periods must use
  the workspace's time zone (Africa/Cairo by default).
- **PLAT-9** LOW — missing indexes: `sales(warehouse_id)`, `sales(status)`, `shifts(cashier_id)`,
  `safe_transactions(safe_id)`, `expenses(tenant_id, date)`, `purchase_order_items(po_id, product_id)`,
  `supplier_transactions(supplier_id)`, `purchase_price_history(product_id)`, `purchase_orders(supplier_id)`.
  *Done: phases A–B made all but `purchase_order_items(po_id, product_id)`, made in phase D (fix/d-fixes,
  `v107_d_fixes`) with the indexes of the HR list and audit log and of the idempotency clean-up.*
- **PLAT-10** LOW — manifests lack `status`; several declare settings that nothing reads (listed per module). *Phase D
  (fix/d-fixes): saving some of a module's settings kept only those (the others went back to their
  defaults); a save is now a merge, each key and value checked against `settings_schema` (422).*

## sales
- **SAL-1** HIGH — client decides price, discount and the stock check: `sales/schemas.py` (`unit_price`
  unbounded, `allow_negative_stock`, `is_offline_sync`, `local_id` disable the check),
  `services/sales.py` (`create_sale`). Fix: `ge=0`, `net_total ≥ 0`, price override only per setting
  `allow_price_override` and a manager permission, negative stock decided on the server
  (`prevent_negative_stock`).
- **SAL-2** HIGH — offline replay posts a sale twice: `F/activities/general/modules/pos/PosPage.tsx` and
  `F/lib/offline.ts` don't send `local_id`; the server matches on `notes` text. Fix: client UUID
  `local_id`, own column, unique index `(tenant_id, cashier_id, local_id)`, return the existing sale.
- **SAL-3** HIGH — sales into closed shifts or none: `services/sales.py` checks only the shift's owner.
  Fix: an open shift of the user in the sale's warehouse for cash; `verify_warehouse_access`; honour
  `require_active_shift`.
- **SAL-4** HIGH — global numbering (PLAT-6) for INV/RET/DEP; drafts burn invoice numbers.
- **SAL-5** MEDIUM — audit rows written after the service's commit are lost
  (`routes/sales.py` create, confirm, quotations, returns); cancel, partial return, quotation edit and
  delete write none. Fix: log inside the service before commit.
- **SAL-6** MEDIUM — reads with sign-in only and no branch filter (`routes/sales.py` list, detail,
  drafts; `routes/invoices.py`); drafts unpaginated.
- **SAL-7** MEDIUM — cancel and return need only `sales`; partial return can refund from another
  cashier's open shift (`_open_shift_for_refund`). Fix: `sales:cancel` / `sales:return`, own shift only.
- **SAL-8** MEDIUM — customer balance clamped at 0 on refunds (`services/sales.py`), ledger credits the
  full amount → receivables disagree.
- **SAL-9** MEDIUM — bad input 500s: date filters as strings, `status` not an enum, unknown ids raise
  IntegrityError.
- **SAL-10** MEDIUM — undeclared dependencies (pos, finance, contacts) in `sales/manifest.json`.
- **SAL-11** MEDIUM — screen gaps (`F/.../sales/SalesPage.tsx`): quotations filtered client-side after
  paging; stat cards use gross `total`; quotation confirm always to the drawer; no confirm dialogs on
  cancel/return; no draft/quotation edit/delete; no total count; no permission gating.
- **SAL-12** LOW — English errors; `[local_id:…]` in notes; email route without rate limit.
- Tests to add: permission denials for every write; another workspace's sale → 404; price and stock
  checks; HTML escaping of the invoice (done in #153).

## pos
- **POS-1** HIGH — any drawer row type by hand (`pos/schemas.py` `DrawerTxType`, `pos/service.py`): a
  cashier can add `return`/`revenue_delivery`/`sale` rows that lower the expected cash and post nothing.
  Fix: only `deposit|expense|withdrawal` by hand; enum `payment_method`; check referenced ids.
- **POS-2** HIGH — revenue delivery updates `safes` with raw SQL, no lock, no cap at the drawer's cash, no
  ownership check (`pos/service.py`). Fix: `safes.deposit`, cap at `compute_summary().expected_balance`.
- **POS-3** MEDIUM — shift opening lock uses Python `hash()` (random per process): two open shifts
  possible. Fix: `hashtext()` in SQL + partial unique index on open shifts; `verify_warehouse_access`;
  validate `supervisor_id`.
- **POS-4** MEDIUM — manager password approval can be brute-forced; rests on `users.is_manager`. Fix:
  rate limit and lockout; permission-based approval.
- **POS-5** MEDIUM — close and transfer inputs: `next_day_drawer` unbounded (negative deposit);
  `transfer_drawer` target not validated.
- **POS-6** MEDIUM — shift summary groups by `sales.payment_method`, split payments miscounted; use
  `sale_payments`.
- **POS-7** MEDIUM — customer balance clamped at 0 on drawer receipts. *Phase D (fix/d-fixes): cancelling
  a receipt's drawer row also gave the invoice its debt back (`sales.paid_amount`), so the invoice, the
  balance and the ledger agree.*
- **POS-8** MEDIUM — shifts screen reads `opened_at`/`tx_type` (backend sends `started_at`/`type`);
  missing screens: close with manager, revenue delivery, drawer handover, summary before closing,
  cancel a drawer row; expense category.
- **POS-9** MEDIUM — manifest settings never read: `require_active_shift`, `allow_price_override`,
  `auto_print_receipt`, `enable_quick_numpad`.
- **POS-10** LOW — English errors; summary/transactions without warehouse check.

## inventory
- **INV-1** HIGH — balances clamped at zero (`inventory/services/stock.py` `GREATEST(…,0)`), out-movements
  not checked (`routes/stock.py` movements and bulk adjustment); products without a
  `warehouse_product_status` row treated as untracked in sales. Fix: check before every out-movement,
  never clamp, "untracked" from the product.
- **INV-2** HIGH — hand-entered movements of any type (`purchase`, `sale`, `return_in`, transfers,
  `opening_stock`) change stock and average cost with no ledger posting. Fix: only
  `adjustment_in|adjustment_out|damage` by hand (`opening_stock` under its own permission), `unit_cost ≥ 0`.
- **INV-3** MEDIUM — stock reset hard-deletes posted movements (`services/warehouses.py`), leaves journal
  entries and the other half of transfers, avg cost not recomputed. Fix: refuse when posted movements
  exist, or post reversals.
- **INV-4** MEDIUM — bad input 500s: category name length and duplicates, product field lengths, barcode
  not unique (`get_product_by_barcode` MultipleResultsFound, returns inactive), warehouse code
  duplicates, collections unknown ids and negative prices.
- **INV-5** MEDIUM — transfers: same warehouse allowed, no access check, no audit, English error,
  service commits itself.
- **INV-6** MEDIUM — `PUT` warehouse can deactivate one that holds stock.
- **INV-7** MEDIUM — valuation at `cost_price` instead of `avg_cost` (disagrees with the ledger).
- **INV-8** MEDIUM — reads with sign-in only (products, movements, balances, collections, movement log)
  include costs.
- **INV-9** MEDIUM — missing screens: categories/subcategories (product create sends `subcategory_id:
  null` → 422), warehouses, adjustments and damage, transfers, barcodes, images, delete, movement log,
  collections. *Done in phase C (fix/c-stock-pur); collections are still sold nowhere (README).*
  *Phase D (fix/d-fixes): decided a stock-assembly helper only (a sale line is one product: selling a
  bundle is a sales/POS redesign); the screen offers no selling price and shows the cost (inventory README).*
- **INV-10** MEDIUM — settings never read: `prevent_negative_stock`, `enable_reorder_alerts`,
  `valuation_method` (offers unimplemented FIFO). *Done in phase C: reorder alerts read the setting,
  FIFO setting removed (average cost).*
- **INV-11** LOW — `list_products` default `page_size=5000`; unbounded bulk reorder list; English errors.

## purchases
- **PUR-1** HIGH — permissions inverted: storekeepers (`inventory`) can pay suppliers from safes, charge,
  receive and return; `purchases` is in no default role except admin while the screen requires it.
  Fix: payments and charges under `purchases`/`finance`; add `purchases` to manager, accountant,
  storekeeper defaults; align the screen guard.
- **PUR-2** MEDIUM — order list shows no total (no column, not computed).
- **PUR-3** MEDIUM — bad input 500s: unbounded paging, string ids, unknown references, unbounded
  `SupplierIn`, negative quick-product prices.
- **PUR-4** MEDIUM — lifecycle: no cancel/delete of drafts, no partial receipt, receipt screen can't enter
  quantities/cost/batch; no order detail/edit, invoice upload, price history, suggestions screens.
  *Done in phase C (goods receipts, v104; the invoice upload is on the order screen).*
- **PUR-5** MEDIUM — reads with sign-in only (supplier balances, ledgers, costs); supplier ledger
  unpaginated; suggestions scan all movements.
- **PUR-6** MEDIUM — indexes (PLAT-9); `receive` lacks `require_open_period`.
- **PUR-7** LOW — English errors; floats in `service.py`; supplier delete under `inventory`;
  supplier-price routes under `operations`; `auto_update_purchase_price` unused.

## finance
- **FIN-2** BLOCKER — no screen creates a safe or wallet; without one no expense can be approved
  (`SOURCE_REQUIRED`). Fix: safes/wallets create, edit, deactivate screens (or a default safe at setup).
- **FIN-3** HIGH — finance Periods tab lists only closed months, can't close a never-closed month, offers
  the current month, ignores order. Fix: reuse `/accounting/periods`.
- **FIN-4** HIGH — `/reports/ledger` totals from the current page only; payment breakdown multiplied by
  items × payments (`services/ledger.py`).
- **FIN-5** HIGH — `/wallets/summary` counts items not invoices, discount per item; date filter 500s.
- **FIN-6** HIGH — `/expenses` and `/expenses/summary` date filters 500 (strings); bad ids 500.
- **FIN-7** HIGH — safe withdrawal checks only the manager flag, not `finance`.
- **FIN-8** HIGH — financial reads with sign-in only and all branches (`/reports/ledger`, `/expenses`,
  `/expenses/summary`, `/wallets/summary`, safe/wallet history, `/expense-vendors`).
- **FIN-9** MEDIUM — `strict_safe_balance` setting unused; recurring expenses don't recur.
- **FIN-10** MEDIUM — manual safe deposit with any `shift_id` credits that drawer in the ledger with no
  drawer movement; unknown ids 500.
- **FIN-11** MEDIUM — no idempotency on safe deposit/withdraw, wallet→safe, wallet reset. *Phase D
  (fix/d-fixes): keys older than 7 days are deleted nightly (`idempotency_cleanup`); two requests with
  one key at once are tested (one effect, the same answer).*
- **FIN-12** MEDIUM — updates wipe fields or 500 (`update_safe`, `update_wallet`, `update_category`).
- **FIN-13** MEDIUM — amounts unbounded (`max_digits`); `/financial-ledger`, `/audit-log` parse strings.
- **FIN-14** MEDIUM — missing screens: categories, expense vendors, reject/edit expense, safe/wallet
  history, wallet edit/deactivate/reset; expense list fixed to page 1, shows `created_at`; treasury tab
  states; buttons not gated.
- **FIN-15** LOW — deleting a category clears history's `category_id`; a rejected expense can be
  approved; wallet delete without lock; server time for periods; dead code; stale manifest/README text.

## contacts
- **CON-1** HIGH — a cashier (`customers`) can set a customer's balance, i.e. write off debt (posts Dr
  other expenses / Cr receivables); delete/deactivate likewise. Fix: `finance` or manager.
- **CON-2** HIGH — customer ledger paging mixes periods (sales oldest-first, payments newest-first, same
  offset); amounts ignore `discount_amount`; unknown customer → `[]`. Fix: one UNION query with a running
  balance, `{items, total}`.
- **CON-3** MEDIUM — payments against an invoice not checked (credit sale, not cancelled, not over-paid).
- **CON-4** MEDIUM — a receipt into a safe/wallet can't be undone; no idempotency on payments.
- **CON-5** MEDIUM — customer screen: no edit, opening balance, delete, paging; totals from the first
  page; no permission gating.
- **CON-6** MEDIUM — unbounded inputs (`limit`, amount digits, free `method`, `name: null`).
- **CON-7** LOW — `/account` and `/ledger` with sign-in only; no trigram index for search; manifest
  `screens: []`; unused `default_credit_limit`; dead `SupplierCreate`.

## hr
- **HR-1** BLOCKER — payroll entries editable after approval and after payment
  (`hr/routes/hr.py` `update_payroll_entry`, `hr/services/payroll.py`): ledger's salaries payable per
  employee breaks; paying recomputes and rewrites the approved expense; `status` settable by hand; edits
  drop the absence proration. Fix: edits only in draft/review with the period locked; net from the
  engine; no `status` in the update; pay exactly the approved amounts.
- **HR-2** HIGH — salaries and HR data readable by any signed-in user (`/hr/employees`, `/hr/payroll`,
  breakdown, attendance, advances, shifts). Fix: `require_perm("payroll")` (or `hr`).
- **HR-3** HIGH — payslips and the monthly report recompute live instead of reading stored entries.
- **HR-4** HIGH — attendance editable after approval/payment; manual saves don't set `edited`, so CSV
  import overwrites corrections.
- **HR-5** HIGH — models don't match the schema (`HrEmployee` lacks `shift_id`, `ignore_lateness`,
  `max_lateness_before_overtime_cancellation`; `hr_shift` id/time types; attendance `shift_override`,
  `edited_by` types): a database built from models breaks payroll.
- **HR-6** MEDIUM — bad input 500s: month unvalidated, GET period inserts rows, string ids, no max
  lengths, shift times, duplicate `emp_code`, non-UTF-8 CSV.
- **HR-7** MEDIUM — settings untyped (`days_in_month="x"` breaks every run).
- **HR-8** MEDIUM — advances: employee not checked (another workspace's id passes the FK), free
  `record_type`, advances in locked months never deducted, no cancel.
- **HR-9** MEDIUM — unrecovered advances dropped when net is clamped at 0.
- **HR-10** MEDIUM — recalculation races approval (no lock).
- **HR-11** MEDIUM — one `payroll` permission for calculate/approve/pay/reopen: split
  `payroll.approve`, `payroll.pay`.
- **HR-12** MEDIUM — hard-coded rules (Egypt, 5 am rollover, Friday weekend, 4 paid leave days, 26 days,
  12-hour shift); money in float.
- **HR-13** MEDIUM — unbounded lists, per-employee queries, `TO_CHAR` filters. *Done in phase D
  (fix/d-fixes): employees paged and searched; a month's calculation loads attendance and HR records in
  bulk (queries independent of the employees); date filters are ranges (no `TO_CHAR` left).*
- **HR-14** MEDIUM — audit log covers only salary changes and advances. *Done in phase D (fix/d-fixes):
  employees (create, edit, stop, start), attendance (hand edits, imports), entry adjustments and every
  payroll month step (calculate, submit, approve, pay, reopen).*
- **HR-15** MEDIUM — missing screens: employee edit/deactivate, shifts, settings, CSV import, audit log,
  adjustments and breakdown, attendance and employee reports; lists cut at 100/60 rows; English statuses;
  period errors swallowed; reopen without confirmation; EGP hard-coded.
- **HR-16** LOW — English errors; dead legacy models and tables (`national_id`); `month` unescaped in
  report HTML (PLAT-5); README minimal.

## operations
- **OPS-1** BLOCKER — goods receipt adds stock and average cost with no ledger entry and no supplier
  (`operations/service.py`). Fix: route through purchases (supplier, payable, `purchase.received`) or
  remove from the UI.
- **OPS-2** MEDIUM — no `verify_warehouse_access` on dispatch, receipt, request.
- **OPS-3** MEDIUM — operations list with sign-in only (costs and suppliers).
- **OPS-4** MEDIUM — stock requests are a dead end (no approve/fulfil/cancel, no audit). *Done in phase C
  (`operations:approve`).*
- **OPS-5** MEDIUM — no idempotency or reversal.
- **OPS-6** LOW — unbounded items and values; shared numbering (PLAT-6); list without total; receipt
  overwrites `cost_price`; no manifest screens; stale README.

## reporting
- **REP-1** BLOCKER — profit, cost, debt and cash-flow reports with sign-in only (`reporting/routes/reports.py`).
  Fix: `require_perm("reports")`; a finance/cost permission for profit, cash flow, aging and stock at
  cost; cashier widget limited to own branch.
- **REP-2** BLOCKER — every date range drops the `to_date` day (`reporting/service.py`, midnight
  `between`). Fix: typed dates, `>= from AND < to + 1 day`, workspace time zone.
- **REP-3** BLOCKER — top products: frontend reads `qty`/`total`/`revenue`, backend sends
  `total_qty`/`total_revenue`; no status filter (quotations, drafts, cancelled, returns counted); no branch.
- **REP-4** BLOCKER — profit includes VAT and ignores approved expenses (payroll included). Fix: net of VAT
  (`sale_items.net_amount`), approved expenses, from the ledger when accounting is on.
- **REP-5** HIGH — branch restriction bypassed when `warehouse_id` is omitted; aging, top products,
  custom-field report and exports have none; monthly tab never sends the branch; cashier widget shows
  the company.
- **REP-6** HIGH — sales totals depend on the VAT setting and ignore returns (daily, monthly, trend,
  by-cashier, custom-field, export).
- **REP-7** HIGH — inventory print returns JSON / 401 with print tokens (use `get_print_user`, render HTML).
- **REP-8** HIGH — cash-flow figures wrong (customer returns as supplier returns, purchase payments twice,
  payroll twice, wallet/bank as cash). Rebuild from money movements or the ledger.
- **REP-9** HIGH — admin overview figures wrong (discount per item row, top-10 debts as totals, last
  purchase price valuation, revenue with VAT).
- **REP-10** HIGH — aging wrong (line sum not `net_total`, `as_of` ignored for later documents, supplier
  payments bucketed by payment date).
- **REP-11** MEDIUM — bad input 500s (string ids/dates, month 13, negative limit; English message).
- **REP-12** MEDIUM — export date filters 500; exports with English headers, text cells for money and
  dates, no row cap; `/export/customers` under `sales`; sales export button 403 silently.
- **REP-13** MEDIUM — time zones (PLAT-8).
- **REP-14** MEDIUM — unbounded scans (periodic ledger, aging, overview, stock export sub-queries).
- **REP-15** MEDIUM — money returned as float.
- **REP-16** MEDIUM — daily items and periodic ledger ignore returns' share of the invoice discount; daily
  items keys returns by product name.
- **REP-17** MEDIUM — tests are smoke-level; `/reports/ledger` in e2e is a 404; no permission or isolation
  tests.
- **REP-18** LOW — reports don't refuse when no workspace is bound (after #154 a session always binds one;
  add the guard anyway); capabilities without screens (profit, cash flow, aging, ledgers, overview,
  exports); stale README; raw SQL into other modules' tables; print/export errors not caught.

## accounting
- **ACC-1** MEDIUM — entry numbering scans `MAX(...)` under a per-workspace lock on every post: a counter
  row (`UPDATE … RETURNING`). *Done in phase D (fix/d-fixes): the workspace's `JE` row of `doc_counters`,
  seeded by `v107_d_fixes`; concurrency tested.*
- **ACC-2** MEDIUM — no e2e/api tests for `/accounting/*` (accounts, category mapping, VAT report, entries).
- **ACC-3** LOW — report routes don't check branch access; party picker capped at 1,000; duplicate account
  code race → 500; a group can be stopped while children stay postable; ledger falls behind if the module
  is turned off after use (the nightly check flags it).

## storefront (→ ADR-015)
- **STO-0** BLOCKER — hide now (not offered) until ADR-015 S4: public order tracking leaks names and
  addresses (4-digit numbers, no sign-in, no rate limit); online sales never reach stock, cash or the
  ledger; fake Fawry and card payment. Every other storefront finding of the audit (duplicate order
  numbers, coupon brute force, unvalidated checkout, unbounded fields leaking SQL, Float money, free
  status transitions, coupon races, no idempotency, suspended workspaces selling, GET writing config,
  every product public, PII in logs, 60-product limit, admin screen issues, duplicate settings sources,
  tests) is a requirement of the ADR-015 rebuild.

## The placeholders (not built, hidden)
customer_portal (XMOD-13), supplier_portal (XMOD-14), subscription_billing (XMOD-06/GYM-02), documents
(XMOD-03, CORE-08), workflow (XMOD-01, CORE-05; note: approvals today can be self-approved, e.g. expense
`decide` doesn't check the approver isn't the creator), projects (XMOD-12), scheduling (XMOD-07), quality
(XMOD-10), assets (XMOD-11; depreciation must post to the ledger), pricing (README points to a removed
file), loyalty. Each needs its own design note before building; portals need a separate principal bound
to one workspace and one customer/supplier, RLS on every table, rate-limited sign-in and isolation tests.
