# Mizan module standard

Every module, built or planned, has the same structure. The structure is defined once, as files,
in `shared/backend/app/framework/module_template/`, and applied by
`shared/backend/app/framework/scaffold.py`. This document explains it. Background and direction:
[ADR-006](decisions/ADR-006-module-platform.md).

## Where a module lives

| Kind | Backend | Frontend |
|---|---|---|
| `business` | `shared/backend/app/activities/<activity>/modules/<module_id>/` | `system/frontend/src/activities/<activity>/modules/<module_id>/` |
| `platform` | `shared/backend/app/platform/<module_id>/` | `system/frontend/src/platform/<module_id>/` |
| `integration` | `shared/backend/app/integrations/<module_id>/` | `system/frontend/src/integrations/<module_id>/` |

- `<activity>` is the module's **home activity**, one full word (`pharmacy`, `manufacturing`,
  `petroleum`), defined in `app/activities/<activity>/activity.json`, with its demo data in
  `seed.py` and its job titles in `positions.json` (`[{"code", "name", "name_en",
  "suggested_roles"}]`, roles from `platform/permissions/roles.py`). `general` holds what every
  activity inherits, including the positions every business has; an activity doesn't repeat them.
- `<module_id>` is the **folder name**: unique across all modules (built and planned), lowercase
  words joined by `_`, full words (`drug_interactions`, not `drg_int`), valid on Windows.
- Renamed ids stay in `app/catalog/legacy_ids.json` forever.

## Status

| Status | Meaning |
|---|---|
| `active` | Built. Mounted by the loader, listed in the module centre, can be switched on. |
| `planned` | Described (usually by the SRS) and laid out with the full structure, but not built. Never mounted, never offered. Its `README.md` says what it will do and quotes the SRS requirements (`srs` in the manifest). |

`python manage.py module new <activity> <id> "<name>"` on a planned module makes it `active`.

## Backend files

| File | What goes in it | Rules |
|---|---|---|
| `manifest.json` | The module's contract (fields below). | Checked at startup and in tests. |
| `README.md` | What the module does, for whom; for planned modules, the SRS requirements. | Keep it current. |
| `models.py` | Database tables (SQLAlchemy). | Every table belongs to a workspace (TenantScoped: `tenant_id` filtered and stamped, row-level security); table names start with the module id; money is `Numeric`, never float; important records are archived, never deleted. |
| `schemas.py` | Request and response schemas (Pydantic). | Routes accept and return schemas, never models. |
| `service.py` | Business logic. | One business operation per function, in one transaction; raises `HTTPException` with an Arabic message; the only place other modules call into. Never touches another module's tables. |
| `router.py` | API routes, `prefix="/modules/<module_id>"`, guarded by `require_module`. | Thin: parse, check permission (`require_perm`), call the service. Older modules keep their historical URLs. |
| `hooks.py` | Names the module's extension points (`before_confirm`, `after_confirm`, …). | The module calls `await emit("<module>.<moment>", db, ...)` (`app/framework/hooks.py`); only the workspace's variant of the module runs. |
| `listeners.py` (optional) | `LISTENERS = {"sale.confirmed": fn, …}`: business events from other modules this module reacts to (`app/framework/events.py`). | A module announces facts with `await notify("<event>", db, ...)` without knowing who listens; only modules active in the workspace run, in the caller's transaction (e.g. the accounting module's postings). |
| `seed.py` | Demo data for a new workspace (`is_demo`, removable). | Called by `app/framework/demo.py` in a fixed order with one shared random generator; activities add a `CATALOG` and/or `seed(db, ctx)` in `app/activities/<id>/seed.py`. |
| `migrations/README.md` | The module's own migrations, in order. | Until the per-module runner exists, migrations go in `app/db/migrations.py`. |
| `templates/README.md` | Print templates, `templates/<category>/<name>.html`. | Rendered by the print engine (`platform/printing/engine.py`); a variant can replace one. |
| `tests/README.md` | The module's tests. | Until collected here: `system/backend/tests/` and `e2e/`. |
| `variants/<variant>/variant.json` | How the module works for one activity. In the module only `<variant>` = `standard`, its own defaults for every activity. | Business modules only. An activity's variant is **not** in the module: it lives in that activity, `app/activities/<activity>/variants/<module_id>/variant.json` (ADR-010; the scaffold puts it there), with the same fields: screens, fields, uses, terms, settings, permissions, templates, widgets. `"status": "planned"` until built (the module then runs `standard`). `fields`: `{"product": [{"key", "label", "type": text\|number\|date\|boolean\|select, "required", "options", "searchable", "readonly"}]}` on the records in `app/framework/fields.py` (stored in their `extra` JSON; workspaces can change and add fields). `uses`: modules the variant relies on (they can't be removed while it runs). |
| `variants/<variant>/hooks.py` (`standard` here; an activity's in `activities/<activity>/variants/<module_id>/hooks.py`) | Rules the variant adds: one function per extension point, `async def before_confirm(db, activity_id=None, **ctx)`. | Raise `HTTPException` to refuse; e.g. `activities/pharmacy/variants/pos/hooks.py`. |

### Larger modules

A module with several areas splits them, and keeps the same entry points:

- `routes/<area>.py`, each with its own `APIRouter`; `router.py` combines them
  (e.g. `general/finance`: ledger, finance, safes, wallets, expenses, periods).
- `services/<area>.py` instead of a single `service.py`.
- `models/<area>.py` and `schemas/<area>.py` instead of `models.py` / `schemas.py`
  (`models/__init__.py` may re-export the classes). `module check` accepts either form.

The general modules (the core ERP, always available) keep their historical URLs (`/sales`,
`/stock`, `/hr`…) and are not guarded by `require_module`.

## Frontend files

| File | What goes in it |
|---|---|
| `index.ts` | The module's `ModuleDefinition` (`src/framework/types.ts`): id, activity, kind, status, screens, and `widgets` (widget id → lazy component, for every widget the manifest declares). Collected by `src/framework/registry.ts` (active modules only). Menus are not here: they come from the manifest's `screens` through `/settings/screens`. |
| `api.ts` | The module's API calls (paths under `/modules/<module_id>`). |
| `screens/README.md` | Full pages, one file each, `<Name>Page.tsx`. |
| `components/README.md` | Parts used only by this module's screens; shared parts go in `@/components`. |
| `variants/README.md` | Business modules only. Screens an activity adds to this module live in the activity: `src/activities/<activity>/variants/<module_id>/` (e.g. the pharmacy counter at `src/activities/pharmacy/variants/pos/`, imported as `@activities/pharmacy/variants/pos`). |

Older modules keep some screens at the module root (`PosPage.tsx`) until they are reworked.

## Manifest fields

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Same as the folder name. |
| `name`, `name_en` | yes | Arabic and English names. |
| `activity` | yes | Home activity (decides the folder and the family). |
| `kind` | yes | `business`, `platform`, `integration`. |
| `status` | yes | `active` or `planned`. |
| `version` | yes | Semantic version. |
| `icon`, `description` | | Shown in the module centre. |
| `dependencies` | | Module ids that must be on too (checked at startup). |
| `permissions` | | What the module's routes check: `[{"id": "pharmacy.dispense", "name": "…", "name_en": "…"}]`. Roles grant these ids; `require_perm("<id>")` checks them. An id is declared by one module only. |
| `screens` | | Pages the module offers: `[{"id": "<module>.<name>", "path": "/products", "label", "icon": "<lucide name>", "permission": "inventory\|purchases"}]`. Activities arrange them into menus (`activity.json` "menu"); a role only sees those its permissions allow (ADR-006 phase 5). |
| `widgets` | | Dashboard widgets: `[{"id": "<module>.<name>", "label", "permission", "size": "s\|m\|l"}]`; each id is registered to a component in the module's `index.ts`. |
| `forms` | | A record's form and its built-in fields, which the screen builder arranges with the workspace's custom fields: `{"product": {"label", "fields": [{"key", "label", "locked"?, "hidden"?}]}}` (`locked`: can't be hidden; `hidden`: off until the builder shows it). |
| `variants` | business | Includes `standard` (in the module's `variants/standard/`) and each activity that adapts the module (in `app/activities/<activity>/variants/<module_id>/`). |
| `srs` | | SRS requirement ids the module implements. |
| `settings_schema` | | Per-workspace settings shown in the module centre. |

## Commands and checks

```
python manage.py module new <activity> <module_id> "<Arabic name>" --name-en "<English>" [--kind ...]
python manage.py module scaffold    # create any missing standard file (never overwrites)
python manage.py module check       # fail if a module is missing part of the structure
python manage.py module catalog     # regenerate docs/MODULE_CATALOG.md from the manifests
```

`system/backend/tests/test_module_registry.py` enforces the structure: folder = id, home activity,
unique ids, frontend mirrors backend, planned modules not offered, Windows-safe names, activity
folders holding only their known parts, activities' variants adapting real modules that list
them, and that this document covers every file in the template.

## Community modules (outside developers)

Developers' modules are declarative, not in this structure: a `manifest.json` (`kind:
"community"`) and `entities/*.json`, checked by `app/framework/manifest.py` and installed into
one workspace from a signed `.mzm` (ADR-007). Theme packs and whole activities use the same
package format (ADR-010). See the developer docs at `dev.allmizan.live/docs`.
