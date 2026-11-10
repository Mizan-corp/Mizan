# Mizan module standard

Every module, built or planned, has the same structure. The structure is defined once, as files,
in `shared/backend/app/framework/module_template/`, and applied by
`shared/backend/app/framework/scaffold.py`. This document explains it. Background and direction:
[ADR-006](decisions/ADR-006-module-platform.md).

## Where a module lives

| Kind | Backend | Frontend |
|---|---|---|
| `business` | `shared/backend/app/modules/<activity>/<module_id>/` | `system/frontend/src/modules/<activity>/<module_id>/` |
| `platform` | `shared/backend/app/platform/<module_id>/` | `system/frontend/src/platform/<module_id>/` |
| `integration` | `shared/backend/app/integrations/<module_id>/` | `system/frontend/src/integrations/<module_id>/` |

- `<activity>` is the module's **home activity**, one full word (`pharmacy`, `manufacturing`,
  `petroleum`), defined in `app/activities/<activity>/activity.json`. `general` holds what every
  activity inherits.
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
| `hooks.py` | Extension points (`before_confirm`, `after_confirm`, …) other modules and variants use. | Planned (ADR-006 phase 4). |
| `seed.py` | Demo data for a new workspace (`is_demo`, removable). | Existing demo data still lives in `app/services/demo_seed.py`. |
| `migrations/README.md` | The module's own migrations, in order. | Until the per-module runner exists, migrations go in `app/db/migrations.py`. |
| `templates/README.md` | Print templates, `templates/<category>/<name>.html`. | Rendered by `core/printing`; a variant can replace one. |
| `tests/README.md` | The module's tests. | Until collected here: `system/backend/tests/` and `e2e/`. |
| `variants/<variant>/variant.json` | How the module works for one activity: screens, fields, uses, terms, settings, permissions, templates, widgets. | `standard` fits every activity; others are named after the activity (`pharmacy`). Business modules only. |
| `variants/<variant>/hooks.py` | Rules that variant adds through the module's hooks. | Phase 4. |

### Larger modules

A module with several areas splits them, and keeps the same entry points:

- `routes/<area>.py`, each with its own `APIRouter`; `router.py` combines them
  (e.g. `general/finance`: ledger, finance, safes, wallets, expenses, periods).
- `services/<area>.py` instead of a single `service.py`.

The general modules (the core ERP, always available) keep their historical URLs (`/sales`,
`/stock`, `/hr`…) and are not guarded by `require_module`.

## Frontend files

| File | What goes in it |
|---|---|
| `index.ts` | The module's `ModuleDefinition` (`src/framework/types.ts`): id, activity, kind, status, screens, widgets, navigation entries. Collected by `src/framework/registry.ts` (active modules only). |
| `api.ts` | The module's API calls (paths under `/modules/<module_id>`). |
| `screens/README.md` | Full pages, one file each, `<Name>Page.tsx`. |
| `components/README.md` | Parts used only by this module's screens; shared parts go in `@/components`. |
| `variants/README.md` | `variants/<activity>/`: screens and components that replace or add to the module's for one activity. Business modules only. |

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
| `permissions`, `screens`, `widgets` | | Declared by the module (ADR-006 phases 3–5). |
| `variants` | business | Includes `standard`; one folder each under `variants/`. |
| `srs` | | SRS requirement ids the module implements. |
| `settings_schema` | | Per-workspace settings shown in the module centre. |

## Commands and checks

```
python manage.py module new <activity> <module_id> "<Arabic name>" --name-en "<English>" [--kind ...]
python manage.py module scaffold    # create any missing standard file (never overwrites)
python manage.py module check       # fail if a module is missing part of the structure
```

`system/backend/tests/test_module_registry.py` enforces the structure: folder = id, home activity,
unique ids, frontend mirrors backend, planned modules not offered, Windows-safe names, and that
this document covers every file in the template.
