# Activities

One folder per business activity (ADR-006): `activity.json` (family, base modules, the variant
each module runs in, optional modules, terms, positions, roles, settings, home screen) and
`seed.py` (demo data: a `CATALOG` and/or `async seed(db, ctx)`, used by `app/framework/demo.py`;
without a catalogue the retail one is used). `general` is inherited by all.
