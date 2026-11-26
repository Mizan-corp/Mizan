# Hotel Housekeeping & Cleaning Operations

Standalone module `hot_housekeeping` under the Hospitality business activity category.

- **Capabilities**: Cleaning task dispatch, stayover/checkout cleanups, priority assignment, automated room state transition back to `vacant_clean`.
- **Endpoints**: `/hospitality/housekeeping/tasks`, `/hospitality/housekeeping/tasks/{task_id}/complete`.
- **Database Tables**: `hotel_housekeeping_tasks`, `hotel_rooms`.
- **Multi-tenancy**: Strict PostgreSQL Row Level Security (`FORCE ROW LEVEL SECURITY`) via `tenant_isolation` policy.
