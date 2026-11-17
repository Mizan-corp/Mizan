# printing

Documents to print (/print/…) and their PDFs (/print/pdf/…): `router.py` re-exports `routes/` (sales,
purchases, shifts, inventory, dispatch, archive). The template engine and paper profiles: `engine.py`,
`config.json`.

## Opening a document
The screens ask for a print token (`POST /auth/print-token`, 60 seconds, `scope: print`) and open the
document in a new tab with `?token=` (`openPrintDoc`, `system/frontend/src/lib/documents.ts`). A session
token is refused, and a print token opens nothing but documents (#154).

## Who prints what (`guard` in `routes/__init__.py`)
Each document needs its permission and a branch the user works in (a manager, `supervise` or
`reports:finance` reach every branch). An unknown document, or another workspace's (RLS), is a 404.

| Route | Permission | Branch |
|---|---|---|
| `/print/sale/{id}` | `sales`, `pos` or `accounting:view` | the sale's |
| `/print/purchase/{id}` | `purchases` | the order's |
| `/print/shift/{id}` | the shift's own cashier, or a manager / `supervise` | the shift's |
| `/print/dispatch/{doc_number}` | `operations` or `inventory` | a branch the goods left or reached |
| `/print/handover/{doc_number}` | one of the two cashiers, or a manager / `supervise` | the shift's |
| `/print/archive/{id}` | `archive` | the one the document names, if any |
| `/print/inventory/{warehouse_id}` | `inventory` or `reports`; costs only with `reports:finance` (the sheet of `/reports/inventory/print`) | that branch |

A dispatch prints from its archived document and the stock movements it made; a hand-over from the
archived `shift_handover` document (the tables these routes read before never existed).

## Escaping (PLAT-5)
Every text that comes from the workspace (the store's name and address, customers, suppliers,
products and units, users, branches, notes, document numbers, status labels) is escaped with `h()`;
`top_band()` and `wrap()` escape what they are given. The PDF footer goes into a CSS string with
quotes, backslashes and angle brackets removed, and the file name keeps only safe characters. PDFs
load nothing but data: URIs and Mizan's own https hosts (`pdf_url_fetcher`, #153).

## Errors
Routes use `PrintRoute`: a browser tab (`Accept: text/html`) gets a refusal, an expired token, a
missing document or a bad link as an Arabic page with the same status; API clients keep the JSON.
`paper_size` is `A4` (default: the workspace's setting) or a receipt roll (`80mm`).

Tests: `system/backend/tests/test_print_documents.py`, `test_invoice_pdf.py`; `e2e/api/test_print.py`.
