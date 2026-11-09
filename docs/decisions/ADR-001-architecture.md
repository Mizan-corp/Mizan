# ADR-001: Hybrid Modular Monolith Architecture

## Status
Accepted

## Context
Mizan serves diverse industries (Healthcare, Retail, Hospitality, Wholesale) that require high integration (e.g., Hospital Pharmacy integrating with central Inventory and Billing). Pure microservices introduce network latency, distributed transaction complexity, and excessive DevOps overhead for early SaaS growth.

## Decision
Adopt a **Modular Monolith** architecture:
- Shared FastAPI kernel and PostgreSQL database with Row Level Security (RLS).
- Strong domain modularity under `shared/backend/app/modules/<business_activity>/<module_name>/` (superseded in layout, not in principle, by ADR-003).
- Each module maintains its own backend routers, schemas, services, and frontend presentation views while sharing the central enterprise data layer.

## Consequences
- High development velocity and single-command local testing.
- Strong transactional guarantees across modules (e.g. inventory deduction during pharmacy checkout).
- Strict module folder conventions prevent circular dependencies and Spaghetti code.
