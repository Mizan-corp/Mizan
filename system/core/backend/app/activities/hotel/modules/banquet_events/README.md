# Hotel Banquets, Events & Conference Halls

Standalone module `hot_banquet_events` under the Hospitality business activity category.

- **Capabilities**: Event hall reservations, conference rooms, catering packages, guest counts, contracts and deposit tracking.
- **Endpoints**: `/hospitality/banquet/events`, `/hospitality/banquet/events/{event_id}/status`.
- **Database Tables**: `hotel_banquet_events`.
- **Multi-tenancy**: Strict PostgreSQL Row Level Security (`FORCE ROW LEVEL SECURITY`) via `tenant_isolation` policy.
