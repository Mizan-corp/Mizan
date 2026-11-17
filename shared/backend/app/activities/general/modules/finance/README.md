# Accounting & Finance

إدارة الخزائن النقدية، المحافظ الإلكترونية، المصروفات، بنود الصرف، وسجل القيود المحاسبية.

## Module ID
`finance`

## Category
finance

## Dependencies
core

## Expense VAT (ADR-014 D6, step 6)
`expenses.tax_amount` is the input VAT included in `amount`, typed from the supplier's tax invoice
(optional, default 0). It is refused in a workspace that isn't VAT-registered and must be less than
the amount (`services/expenses.check_tax`, on create and update). The ledger posts the category's
account with `amount − tax_amount` and VAT input with the tax; the money leaving is `amount`.
