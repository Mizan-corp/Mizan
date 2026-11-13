# Database Rules for Antigravity

- **TenantScoped Inheritance:** every workspace table inherits `TenantScoped` and gets row-level security (`ENABLE` and `FORCE`, the tenant_isolation policy) in its migration.
- **Foreign Key Indexing:** every foreign key column is indexed for joins under multi-tenancy.
- **Soft Deletes vs. Auditing:** clinical and financial records are never hard-deleted; use `is_active` or status transitions with an audit record.
- **Unique Constraints:** unique constraints on workspace tables include `tenant_id` (e.g. `UniqueConstraint("tenant_id", "code")`); a primary key spanning workspaces must include it too.
- **Models match migrations:** same primary key and `server_default`s in the model as in the migration (docs/DATABASE_DESIGN.md §4).
