# Stock Operations

`operations`: a business module of the `general` activity (active). Its contract is
`manifest.json`; the layout and rules are in docs/MODULE_STANDARD.md.

## What it does (`/operations`, permission `operations`)
- `POST /operations/dispatch` (إذن صرف): goods move from one warehouse to another, both of which the
  user works in (`verify_warehouse_access`); the source must hold the stock; the same batches arrive.
  Archived as `dispatch_order` and audited.
- `POST /operations/stock-request` (طلب نواقص): a request document into a warehouse the user works in;
  no stock moves.
- `POST /operations/{id}/cancel` (`operations:cancel`: managers, admin): cancels a dispatch. What
  arrived at the destination goes back to the source by the same path (transfer out and in,
  batches followed), as `dispatch_cancel` movements under the dispatch's reference; refused when the
  destination no longer holds it. Both warehouses must be the user's. The document stays, marked
  `cancelled` (who, when, reason), and the cancel is audited.
- `GET /operations/?doc_type&page&page_size` (≤ 200): `{items, total, page, pages}`, newest first;
  each item has its `status` (`done`, `pending`, `cancelled`).

## Retries (OPS-5)
A dispatch or stock request sent again with the same `Idempotency-Key` header or `client_id` in the
body returns the first answer (`app/framework/idempotency.py`); the same key with another body is
a 422. The screen sends a new `client_id` per document.

## Bounds and numbers (OPS-6)
1 to 500 lines; quantities > 0 with at most 3 decimals and ≤ 999,999,999 (a document's total ≤
9,999,999,999); notes ≤ 1000, line notes ≤ 500, batch numbers ≤ 64. Numbers count per workspace
(`DSP-000001`, `REQ-000001`, `app/platform/archive/numbering.py`); the first one continues after the
highest the workspace already had.

## Goods receipt removed (OPS-1)
`POST /operations/goods-receipt` answers **410**. It put stock and its cost into a warehouse with a
free-text supplier, no payable and no ledger entry. Goods from a supplier come in through a purchase
order (`/purchases`: the supplier is owed the amount and the ledger posts `purchase.received`). Earlier
receipts stay in the list and the archive as `goods_receipt` documents.

## Known limits
- Stock requests can't be approved, fulfilled or cancelled yet (OPS-4).
- The screen lives in the inventory manifest (`inventory.operations`), not in this one.
- Documents from before the counter keep the numbers the shared `invoice_seq` gave them.
