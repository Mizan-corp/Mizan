# Website builder and storefront (planned)

The public website and online shop of a workspace, with a page designer (the studio), themes, and the
ERP screens that run it (orders, shoppers, CRM, catalogue online, shipping and payments, marketing,
content, analytics). Designed in docs/decisions/ADR-015-website-builder-and-storefront.md; not built.

## Why it is planned again
The first version (a single public shop page with an admin screen) was taken out of service on
2026-11-17 (ADR-015 step S0) before any workspace used it, because the module audit found
(docs/PRODUCTION_READINESS.md, STO-0):
- public order tracking returned customers' names and addresses to anyone guessing a 4-digit order
  number, with no sign-in or rate limit;
- online orders never reached stock, cash or the ledger;
- Fawry and card payment were placeholders (made-up payment codes, orders unpaid forever).

Its code stays in this folder as a reference for the rebuild; it is not mounted (status `planned`), so
none of its routes answer and no workspace can switch it on. Its tables (`storefront_*`) are kept, empty.

## Module ID
`storefront`

## Dependencies
core, inventory (the rebuild adds sales, finance, contacts)
