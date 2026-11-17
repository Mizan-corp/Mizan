# Inventory & Supply

تتبع الأرصدة اللحظية، إدارة الفروع والمستودعات، تسويات الجرد، وأوامر الشراء والتوريد.

## Module ID
`inventory`

## Category
retail

## Dependencies
core

## Tax code (ADR-014 D6, step 6)
`products.tax_code`: `standard` (14 %), `zero` (0 %, still reported) or `exempt` (outside VAT);
default and every existing product `standard` (migration `v94_vat`, with a check constraint). It is a
field of the product form ("ضريبة القيمة المضافة"), in `ProductOut` and the create/update schemas.
Documents copy it onto their lines when they are made; changing it never changes a past document.
