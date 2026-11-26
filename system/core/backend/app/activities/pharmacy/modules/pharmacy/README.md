# Pharmacy & Medication Dispensing

منظومة صيدلانية متكاملة: دليل الأدوية بالاسم العلمي والتجاري، تتبع الصلاحيات والتشغيلات (FEFO)، صرف الروشتات، التأمين الطبي، وسجل الأدوية المراقبة (جدول).

## Module ID
`pharmacy`

## Category
vertical_sectors

## Dependencies
inventory, invoicing

## Receiving batches (phase C)
`POST /pharmacy/batches` answers **410**. It put bought stock in as a `purchase` movement with a
free-text supplier: no purchase order, nothing owed to the supplier and no ledger entry. A batch from
a supplier is received on its purchase order (`/purchases`, the receipt takes the batch number and
expiry per line), which owes the supplier and posts `purchase.received`; stock already on the shelf
when the workspace starts is opening stock (`/inventory/adjustments`, with `inventory:opening`).
`GET /pharmacy/batches` (the batches with stock) is unchanged; the batches tab points to purchases.
