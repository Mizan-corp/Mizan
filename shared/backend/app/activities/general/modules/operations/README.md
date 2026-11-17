# Stock Operations

`operations`: a business module of the `general` activity (active). Its contract is
`manifest.json`; the layout and rules are in docs/MODULE_STANDARD.md.

## What it does (`/operations`, permission `operations`)
- `POST /operations/dispatch` (إذن صرف): goods move from one warehouse to another, both of which the
  user works in (`verify_warehouse_access`); the source must hold the stock; the same batches arrive.
  Archived as `dispatch_order` and audited.
- `POST /operations/stock-request` (طلب نواقص): a request document into a warehouse the user works in;
  no stock moves.
- `GET /operations/?limit&offset`: the documents, newest first.

## Goods receipt removed (OPS-1)
`POST /operations/goods-receipt` answers **410**. It put stock and its cost into a warehouse with a
free-text supplier, no payable and no ledger entry. Goods from a supplier come in through a purchase
order (`/purchases`: the supplier is owed the amount and the ledger posts `purchase.received`). Earlier
receipts stay in the list and the archive as `goods_receipt` documents.

## Known limits
- Stock requests can't be approved, fulfilled or cancelled yet (OPS-4); documents have no reversal
  (OPS-5); numbers come from the shared `invoice_seq` (PLAT-6).
