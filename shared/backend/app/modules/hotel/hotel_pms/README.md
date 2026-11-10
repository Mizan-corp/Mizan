# Hotel Property Management System (PMS) - Front Desk & Room Inventory

Standalone module `hot_pms` under the Hospitality business activity category.

- **Capabilities**: Interactive room rack, room inventory management, guest check-in & check-out, status transitions (`vacant_clean`, `vacant_dirty`, `occupied`, `out_of_order`).
- **Endpoints**: `/hospitality/pms/rooms`, `/hospitality/pms/reservations`, `/hospitality/pms/reservations/{res_id}/checkin`, `/hospitality/pms/reservations/{res_id}/checkout`.
- **Database Tables**: `hotel_rooms`, `hotel_reservations`.
- **Multi-tenancy**: Strict PostgreSQL Row Level Security (`FORCE ROW LEVEL SECURITY`) via `tenant_isolation` policy.
