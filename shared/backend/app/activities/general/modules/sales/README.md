# Sales & Invoicing

إصدار أوامر البيع وعروض الأسعار، الفواتير الضريبية، المرتجعات، وتتبع مدفوعات العملاء.

## Module ID
`sales`

## Category
sales

## Dependencies
core, inventory

## VAT (ADR-014 D6, step 6)
A sale's VAT is worked out once, when the document is made (POS sale, draft or quotation) and again
when a draft or quotation is confirmed (the invoice's time), by `app/platform/settings/vat.py`:
each line stores `tax_code` (the product's code then; `NULL` when the workspace isn't
VAT-registered), `tax_rate`, `tax_amount` and `net_amount` (its value after every discount,
without VAT), and the sale `tax_amount`. `net_total` stays what the customer pays: unchanged when
prices include VAT (the default), with the tax added on top when they don't. A return document
takes each original line's value and tax in proportion to the quantity returned, whatever the
product's code is now; returning everything gives back the sale's VAT to the piastre. Sales made
before (or without registration) keep the old return arithmetic. The printed invoice
(`/print/sale/{id}`, "فاتورة ضريبية") and the emailed PDF show the stored figures and the tax
number, and nothing about VAT when the sale has no VAT data; nothing estimates 14 % of a total any
more. The module's old `default_tax_rate` setting, which nothing read, is gone: the rates live in
`vat.py` only.
