# Integrations

Connectors to outside systems (ADR-006), mirrored for screens in `system/erp/frontend/src/integrations/`.

| Folder | What it is | Status |
|---|---|---|
| `pos_hardware` | Barcode scanners and ESC/POS thermal printers | module, active |
| `whatsapp_gateway` | WhatsApp Business receipts | module, active (live sending queued) |
| `paymob` | Owner subscriptions through Paymob (checkout, signed callbacks, reconciliation); used by the owner API (ADR-004) | service, not a module |
| `fawry`, `instapay` | Payments in a workspace | modules, planned |
| `webhooks` | A general integration engine for workspaces | module, planned (developers' modules already get signed webhooks: `platform/community/events.py`) |
| `eta_einvoice` | Egyptian Tax Authority e-invoicing and e-receipts | described, deferred |

The `zk_attendance` device sync was removed (#110).
