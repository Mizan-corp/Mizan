# settings

Workspace settings (/settings): `router.py`.

## VAT (ADR-014 D6): `vat.py`

The workspace's VAT settings are company settings, kept in `store_settings` with the store's name,
address and phone (where the invoices already read them), not in accounting's `acc_settings`: VAT
applies to every document whether or not the accounting module is on.

| Key | Default | Meaning |
|---|---|---|
| `vat_registered` | `false` | The workspace is registered for VAT. Off: no document carries VAT and nothing prints it |
| `tax_number` | — | The Egyptian tax registration number, stored as 9 digits (dashes, spaces and Arabic digits are accepted and dropped); printed as `123-456-789` |
| `prices_include_vat` | `true` | Selling prices (and, unless a purchase order says otherwise, purchase costs) include VAT |

`PUT /settings` checks them (`_check_vat_settings`): a tax number that isn't 9 digits, or turning
registration on with no tax number, is refused with 422 and an Arabic message; the switches are
stored as `"true"` / `"false"`. `GET /settings/vat` (any signed-in user) returns the three, the
display form of the number and the tax codes with their rates, for the screens. The settings
screen has them under "المتجر والفوترة". A change applies to new documents only.

`vat.py` is the one place for the rates (`TAX_RATES`: `standard` 14 %, `zero` 0 % and still
reported, `exempt` outside VAT) and the rule, used by sales, purchases and the VAT report (the
point of sale mirrors it in `system/frontend/src/lib/vat.ts`, with the rates from the server):

- Each line's amount after its own discount and its share of the invoice discount (shared pro
  rata, each share rounded, the remainder on the largest line); the lines are made to add up to the
  document's own rounded total.
- Prices including VAT: net = round(amount ÷ (1 + rate)) to the piastre, half up; tax = amount −
  net, so the customer pays exactly the price. Excluding: tax = round(amount × rate) on top.
- The document's tax = the sum of its lines. Not registered: code `NULL`, rate 0, tax 0.
- `portion()`: a returned part of a line takes the line's stored value and tax in proportion to
  the quantity, cumulatively rounded, so returning everything gives back exactly what was charged.
