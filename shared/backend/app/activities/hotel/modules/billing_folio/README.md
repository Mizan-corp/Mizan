# Guest Folio & Incidentals Room Posting

Standalone module `hot_billing_folio` under the Hospitality business activity category.

- **Capabilities**: Guest ledger, incidentals room charge posting (F&B, mini-bar, laundry, spa), VAT calculation, folio item settlement.
- **Endpoints**: `/hospitality/billing/folios`, `/hospitality/billing/folios/{folio_id}/settle`.
- **Database Tables**: `hotel_folio_items`, `hotel_reservations`.
- **Multi-tenancy**: Strict PostgreSQL Row Level Security (`FORCE ROW LEVEL SECURITY`) via `tenant_isolation` policy.
