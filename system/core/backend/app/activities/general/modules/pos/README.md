# Point of Sale (POS)

إصدار الفواتير الفوري، دعم قارئ الباركود، الشاشات اللمسية، إدارة أدراج الكاشير والورديات.

## Module ID
`pos`

## Category
retail

## Dependencies
core, inventory, contacts (customer payments at the drawer), finance (safes and wallets).

## VAT (ADR-014 D6, step 6)
The point of sale shows the VAT the server will store (`system/frontend/src/lib/vat.ts`, same rule
and the rates from `GET /settings/vat`): "منها ضريبة" when prices include VAT, the tax added to the
total to collect when they don't. The receipt (`/print/sale/{id}`) prints the stored amounts.

## Settings (POS-9)
Read by the server (`sales/services/checks.py`) and by the POS screen (`GET /modules/pos/settings`,
`usePosSettings` in the frontend's `pos/api.ts`, rules in `pos/lib.ts`):
- `require_active_shift` (default on): no POS sale without the user's open shift in the branch. The
  screen says so and offers to open one; with it off and no shift, only non-cash payments are
  offered (cash always needs the shift).
- `allow_price_override` (default off): with it on, `sales:override_price` holders may sell at another
  price than the product's; the screen then shows a price edit on each cart line (marked «سعر
  معدّل»), and no edit to anyone else.
- `auto_print_receipt` (default off): the screen opens the receipt (`/print/sale/{id}`) as soon as a
  sale is recorded, in a tab opened during the click or key press so the browser allows it.
- `enable_quick_numpad` (default on): shows or hides the numpad in the payment dialog.

## Shifts
- One open shift per cashier and branch: an advisory lock keyed with `hashtext()` in SQL serialises
  concurrent opens, and the partial unique index `uq_shifts_open_cashier_warehouse` refuses a second
  one. Opening checks the branch (exists, active, `verify_warehouse_access`) and the supervisor.
- Drawer rows by hand are only `deposit`, `expense` or `withdrawal`, paid `cash` or by `wallet`; the
  wallet, category and customer named are found in the workspace. Sale and return rows come only from
  their documents, revenue delivery only from its route.
- Revenue delivery (drawer → safe) goes through the finance safes service (row lock, numbered `DEP-`
  document per workspace), into an active safe, never more than the drawer's expected cash, from the
  user's own shift (managers and `supervise`: a shift of a branch they reach), with a manager's
  password.
- A customer paying at the drawer lowers their balance without clamping at zero.

## The shift summary (POS-6)
`GET /shifts/{id}/summary` counts the shift's sales by their payment lines (`sale_payments`): a split
payment counts each part under its own method and wallet (it used to count the whole sale under the
first method); sales recorded before payment lines existed count whole under their payment method.
`wallet_total` is what came in other than cash or on credit.

## The shifts screen (POS-8)
`system/frontend/src/activities/general/modules/pos/screens/ShiftsPage.tsx`: the open shift's summary
(expected cash before closing), drawer rows by hand with the expense category
(`/financial-categories`, type `expense`) and cash or wallet, cancelling a row, revenue delivery to a
safe with a manager's password, handing the drawer to a colleague, closing alone or with a manager
(who receives what isn't left for the next shift), the report, and the branch's history (paged,
with each shift's summary for its cashier and supervisors).
- `GET /shifts/{id}/people` (the shift's cashier, managers and `supervise` holders, in reach):
  `approvers` (who can approve at the counter, `can_approve`) and `receivers` (who can take the drawer
  over: the rules of `transfer`, without an open shift in the branch).
- `DELETE /shifts/transactions/{id}` cancels a row entered by hand: those who approve at the counter
  (`supervise`, or the manager flag with `shifts`; it used to be the manager flag alone), in a branch
  they reach; audited (`cancel_drawer_tx`). A row that took a customer's receipt is undone through
  contacts (`reverse_drawer_receipt`): the customer and the invoice the receipt paid owe the amount
  again (`sales.paid_amount` goes down), and the ledger entry is reversed, so the three agree.

## Manager approvals (POS-4)
Closing with a manager (`/shifts/{id}/close-with-manager`) and revenue delivery take a manager's id
and password (`verify_approver` in `service.py`):
- **Who approves**: an active user of the workspace whose acting role holds `supervise` (managers by
  default), or who is flagged a manager (`users.is_manager`) and holds `shifts`. A manager may approve
  their own request (a one-person shop); the approval is in the audit log (`close_with_manager`,
  `revenue_delivery`).
- **Guessing is stopped**: 10 approval requests per user every 5 minutes; 5 wrong passwords by one
  user lock that user's approvals for 15 minutes (429); colleagues are not locked out. Counted in Redis when
  `REDIS_URL` is set, otherwise per process.

## Closing and handing over (POS-5)
- `next_day_drawer` (what stays for the next shift) is between 0 and the counted closing balance;
  closing with a manager deposits the rest.
- `/shifts/{id}/transfer` hands the drawer only to an active user of the workspace, not the shift's
  own cashier, whose role holds `shifts` and who works in the shift's branch (assigned, or a manager /
  `supervise` holder), with no open shift there. The closed shift, the new one and the `HND-` handover
  document name people (no ids in notes); the document is made by whoever handed over, and audited.

## Reading drawers (POS-10)
`/shifts/current`, `/shifts/last-drawer`, `/shifts/{id}/summary` and `/shifts/{id}/transactions`
need `shifts` or `pos`; a shift of someone else only for managers and `supervise` holders, always
within the branches the user reaches. Errors are in Arabic.
