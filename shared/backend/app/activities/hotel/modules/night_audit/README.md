# Hotel Night Audit & Financial Reconciliations

Standalone module `hot_night_audit` under the Hospitality business activity category.

- **Capabilities**: Daily night audit automation, ADR (Average Daily Rate), RevPAR (Revenue Per Available Room), daily room & F&B revenue posting and reconciliation.
- **Endpoints**: `/hospitality/night-audit/audits`, `/hospitality/night-audit/run-audit`.
- **Database Tables**: `hotel_night_audits`, `hotel_rooms`, `hotel_reservations`, `hotel_folio_items`.
- **Multi-tenancy**: Strict PostgreSQL Row Level Security (`FORCE ROW LEVEL SECURITY`) via `tenant_isolation` policy.
