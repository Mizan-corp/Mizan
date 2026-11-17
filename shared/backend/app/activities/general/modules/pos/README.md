# Point of Sale (POS)

إصدار الفواتير الفوري، دعم قارئ الباركود، الشاشات اللمسية، إدارة أدراج الكاشير والورديات.

## Module ID
`pos`

## Category
retail

## Dependencies
core, inventory

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
