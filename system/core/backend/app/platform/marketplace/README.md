# Module marketplace and self-configuration (planned)

`marketplace`, in `app/platform/`. Not built yet.

From the SRS (`docs/developer/mizan/srs/SRS-Mizan-v1.0.md`):

- **MOD-01**: Module marketplace UI
- **MOD-02**: Activity-driven module defaults
- **MOD-03**: Module self-configuration per activity
- **MOD-04**: Screenshot previews in marketplace
- **MOD-05**: Business size-based stack
- **MOD-06**: Single page per module boundary
- **MOD-07**: Module dependency declaration
- **MOD-08**: Module deactivation

Today: The module centre (app/api/routers/modules.py); ADR-006 phase 7.

## Launch rules (step 11a)

- Free listings only: `listings.listing_problems()` refuses, before review, a package whose manifest
  carries a price, fee, subscription or currency key (`PAID_KEYS`).
- A listing's name and description change only inside `approve()`, so every text change waits for a manual
  review by the Mizan team. The store has no listing image field yet.
- Package format 2 signs the kind (see `framework/package.py`); format 1 is still read.
