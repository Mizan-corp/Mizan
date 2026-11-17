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

## Settings read by the server
- `require_active_shift` (default on): no POS sale without the user's open shift in the branch
  (`sales/services/checks.py`).
- `allow_price_override` (default off): with it on, `sales:override_price` holders may sell at another
  price than the product's.

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

## Manager approvals (POS-4)
Closing with a manager (`/shifts/{id}/close-with-manager`) and revenue delivery take a manager's id
and password (`verify_approver` in `service.py`):
- **Who approves**: an active user of the workspace whose acting role holds `supervise` (managers by
  default), or who is flagged a manager (`users.is_manager`) and holds `shifts`. A manager may approve
  their own request (a one-person shop); the approval is in the audit log (`close_with_manager`,
  `revenue_delivery`).
- **Guessing is stopped**: 10 approval requests per user every 5 minutes; 5 wrong passwords for one
  manager of a workspace, or by one user, lock approvals for 15 minutes (429). Counted in Redis when
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
