# Reporting engine (planned)

`reporting`, a module of the `general` activity. Not built yet.

From the SRS (`docs/developer/mizan/srs/SRS-Mizan-v1.0.md`):

- **XMOD-04**: Reporting Engine: Custom reports, filters, and scheduled reports
- **CORE-10**: Dashboard and configurable reporting

Today: Fixed reports in app/api/routers/reports.py.

To build it: `python manage.py module new general reporting "<name>"` creates the full
ADR-006 layout here (backend and screens).
