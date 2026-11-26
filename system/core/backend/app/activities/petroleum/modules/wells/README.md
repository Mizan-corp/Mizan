# Fields, sites, wells and assets (planned)

`wells`, a module of the `petroleum` activity. Not built yet.

From the SRS (`docs/developer/mizan/srs/SRS-Mizan-v1.0.md`):

- **OIL-01**: Field and site operations management
- **OIL-02**: Well and asset hierarchy management

Today: Well tree in the oil_gas module (petroleum/oil_gas).

To build it: `python manage.py module new petroleum wells "<name>"` creates the full
ADR-006 layout here (backend and screens).
