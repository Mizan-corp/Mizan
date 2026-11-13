# Framework

The module runtime (ADR-006) and the package format (ADR-007, ADR-010).

| File | What it does |
|---|---|
| `loader.py` | Finds every module (`activities/*/modules/*`, `platform/*`, `integrations/*`) by its manifest, checks it, mounts its router. The only way a module is mounted. |
| `activation.py`, `composition.py` | What a workspace has on: install, uninstall, dependencies, what an activity turns on. |
| `variants.py`, `hooks.py` | How an activity adapts a module: a module's `variants/standard/` and activities' `variants/<module>/`; `emit("<module>.<moment>")` runs the workspace's variant's `hooks.py`. |
| `fields.py`, `screens.py`, `layouts.py` | Extra fields on shared records; screens, widgets and each role's menu and dashboard; the screen builder's saved layouts. |
| `demo.py`, `files.py`, `storage.py` | Demo data for new workspaces; uploaded files (Vercel Blob or disk); storage use by module. |
| `scaffold.py`, `module_template/` | The module standard and its tool: `manage.py module new|scaffold|check|catalog`. |
| `manifest.py` | The checks for what developers ship: community modules and entities, theme packs, activity packages. Copied byte for byte into the SDK. |
| `package.py` | `.mzm` packages: build, sign, verify (developer certificate, file hashes, revoked keys checked by the caller), and Mizan's catalogue for activity packages. |
| `isolation.py`, `licences.py`, `migrations.py`, `scopes.py`, `settings.py` | Reserved, one line each saying what they'll hold and when. |
