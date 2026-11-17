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
