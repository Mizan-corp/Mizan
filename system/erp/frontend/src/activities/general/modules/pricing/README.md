# Pricing engine (planned)

`pricing`, a module of the `general` activity. Not built yet.

From the SRS (`docs/developer/mizan/srs/SRS-Mizan-v1.0.md`):

- **XMOD-08**: Pricing Engine: Price lists, discounts, tiers, and dynamic rules
- **CRM-04**: Pricing rules and price lists
- **CRM-05**: Discounts and promotions

Today: Retail/wholesale price tiers on products (app/api/routers/products.py).

To build it: `python manage.py module new general pricing "<name>"` creates the full
ADR-006 layout here (backend and screens).
