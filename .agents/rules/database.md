# Database Rules for Antigravity

- **TenantScoped Inheritance:** Every business table must inherit from `TenantScoped` and define `tenant_id` foreign key.
- **Foreign Key Indexing:** Every foreign key column must have `index=True` for join performance under multi-tenancy.
- **Soft Deletes vs. Auditing:** Sensitive clinical and financial records must never be hard-deleted; utilize `is_active` or explicit status transitions with an audit log record.
- **Unique Constraints:** Unique constraints across tenant models must always be composite with `tenant_id` (e.g., `UniqueConstraint("tenant_id", "code")`).
