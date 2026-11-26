# Activities

One folder per business activity (ADR-010): everything that makes the activity, in one place.

```
activities/<activity>/
  activity.json      family, base and optional modules, the variant each module runs, terms,
                     positions, menus and dashboards per role, settings, home screen
  positions.json     the activity's positions
  seed.py            demo data: a CATALOG and/or async seed(db, ctx) (app/framework/demo.py)
  modules/<id>/      the activity's own modules, in the standard structure (docs/MODULE_STANDARD.md)
  variants/<module>/ how this activity adapts another activity's module: variant.json (fields,
                     terms, settings, screens, uses) and hooks.py (rules at the module's hooks)
  themes/<theme>/    theme packs that come with the activity (ADR-010 D3)
```

The system app mirrors it: `system/frontend/src/activities/<activity>/modules/<id>/` (screens) and
`variants/<module>/` (screens a variant adds). `general` is inherited by every workspace; its
modules are the core ERP. A module's own defaults are its `standard` variant
(`modules/<id>/variants/standard/`).

Create modules with `python manage.py module new <activity> <id> "<name>"`. Activity packages
from developers use the same layout (ADR-010 D2).
