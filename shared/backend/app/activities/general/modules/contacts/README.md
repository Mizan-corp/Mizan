# Contacts & Partners (`contacts`)

Customers and suppliers, what they owe, and their statements. A core module of the `general`
activity. Suppliers' routes, payments and ledgers are served by the purchases module
(`/suppliers`); this module owns the customer side.

Permission: `customers` (declared here). Writing off debt, stopping and deleting customers and
reversing receipts need more (below).

## Customer routes

| Route | Who | What |
|---|---|---|
| `GET /customers` `?search&include_inactive&limit&offset` | signed in | Customers by name (a bare list: the POS and every picker use it) |
| `GET /customers/summary` `?search&include_inactive` | `customers` | The list's totals over the whole filter: count, debtors, total due, over the credit limit |
| `POST /customers`, `PUT /customers/{id}` | `customers` | Create; change only the fields sent (the name can't be emptied; the balance never changes here) |
| `GET /customers/{id}/account` | `customers` or `finance` | Totals of the statement: invoiced on credit, returned, paid, adjusted, balance due |
| `GET /customers/{id}/ledger` `?page&page_size&newest_first` | `customers` or `finance` | The statement: `{items, total, page, page_size, pages}` |
| `POST /customers/{id}/payments` | `customers` | A receipt: into a safe or wallet, or (cash, none chosen) the cashier's open drawer |
| `POST /customers/payments/{id}/reverse` `{reason}` | `finance` | Undo a receipt into a safe or wallet |
| `PUT /customers/{id}/balance` `{balance, note}` | `finance` or the manager flag | Opening balance or correction, recorded as an adjustment |
| `POST /customers/{id}/deactivate`, `/activate`, `DELETE /customers/{id}` | `finance` or the manager flag | Stop or bring back; delete only without any transaction |

## Rules

- **The statement** is one query over credit invoices, returns, receipts (and their reversals) and
  adjustments, in date order, with the balance after each line computed over the whole
  statement (a page shows the right running balance). An invoice counts what it put on the
  customer's account: its credit payment lines (the net after the invoice discount); a return what
  it took off. `/account` sums the same lines, so the two always agree. A cancelled sale is left
  out (its cancellation took its credit back). Unknown customer: 404.
- **A receipt against an invoice** needs a confirmed credit sale of that customer (not cancelled,
  not a return) with at least the amount still due (credit − credit returned − receipts already on
  it); the sale is locked while it is checked.
- **Receipts are idempotent**: an `Idempotency-Key` header or a `client_id` in the body; a retry
  returns the first receipt.
- **Reversing a receipt** (`service.reverse_payment`): the money goes back out of the safe or
  wallet (refused if it isn't there), the customer owes the amount again, the invoice's paid amount
  goes down, the ledger entry is reversed (`customer_payment.reversed`), and a negative receipt
  pointing to the original (`reverses_id`, unique) records it. A receipt into a cashier's drawer is
  undone by cancelling its drawer movement on the shift screen. A receipt is reversed once.
- **Write-offs**: setting a balance records the difference (`customer_adjustments`, ADR-014 D4),
  posted to the ledger; lowering it writes off debt, so a cashier holding only `customers` can't.
- Amounts: receipts up to 12 digits, balances and limits up to 14, 2 decimals; `method` is one of
  `cash`, `bank`, `cheque`, `card`, `wallet`.

## Files

`routes/parties.py` (the API), `service.py` (receipts, reversal, adjustments, statement),
`models/party.py` (`customers`, `suppliers`), `models/customer_payment.py` (`customer_payments`,
`customer_adjustments`), `schemas.py`. Migration `v99_ready_finance_contacts` added
`customer_payments.reverses_id`.

## Screen

`/customers` (`system/frontend/src/features/customers/CustomersPage.tsx`): paged list with server
totals, create and edit, balance adjustment, stop, delete, receipts, and the statement with its
running balance and the reversal of receipts.

## Not yet

- `default_credit_limit` (manifest setting) is not applied to new customers; no trigram index for
  the name search (CON-7).

## Dependencies
core. Tests: `system/backend/tests/test_money_flows_finance.py`, `test_ready_finance_contacts.py`;
`e2e/api/test_parties.py`.
