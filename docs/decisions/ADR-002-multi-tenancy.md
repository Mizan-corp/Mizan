# ADR-002: Multi-Tenancy via PostgreSQL Row-Level Security (RLS)

## Status
Accepted

## Context
Mizan operates as a multi-tenant SaaS platform where multiple organizations, hospitals, clinics, and companies share cloud infrastructure. Data isolation is a life-critical and legal requirement under Egyptian Data Protection and Healthcare regulations.

## Decision
Implement a **defense-in-depth multi-tenancy model**:
1. All application models inherit from `TenantScoped` (`tenant_id` UUID foreign key).
2. SQLAlchemy async session checks out connections and binds `SET LOCAL app.tenant_id = '<current_tenant_id>'`.
3. PostgreSQL Row-Level Security (RLS) enforces queries at the database engine level, rejecting any query that lacks the matching tenant ID.

## Consequences
- Guaranteed tenant data isolation even if an application bug omits a filter clause.
- Seamless multi-tenancy with a unified schema, simplifying database migrations.
