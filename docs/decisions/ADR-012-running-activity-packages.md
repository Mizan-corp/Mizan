# ADR-012: Running developers' activity packages in a workspace

## Status
Accepted and built (2026-11-14). Second part of #107; completes ADR-010 D2 ("an existing workspace can
switch to it"). Builds on the marketplace (ADR-007 milestone 2, #105).

## Context
A developer can build, check, sign and package a whole business activity (`kind: "activity"`,
ADR-010 D2): an `activity.json`-like manifest (family, Mizan modules it runs, menus, dashboards,
roles, terms, settings, positions), its own declarative modules (`modules/<team>.<module>/`),
variants of Mizan's modules (`variants/<module>/variant.json`: fields, terms, settings only),
themes and seed records. Nothing could run one: uploads were refused.

Everything a workspace's activity decides is read at run time by activity id: `variants.activity()`
and `all_variants()` (variants, terms, settings, menus through `framework.screens`),
`catalog.family_of()` and `composition.base_modules()/installable()` (which modules it may run),
`permissions.positions` (positions), the themes service (its theme). They read Mizan's activity
folders and cache them for the process. A workspace's activity is `tenants.sector`.

## Decision

### D1. Activities come from the marketplace, reviewed, and a change is approved
Developers publish activity packages like modules and themes (`mizan publish`, the portal); the
Mizan team reviews them (ADR-007 milestone 2). An approved, listed activity can be chosen by an
owner in the existing activity-change request (#107), which the Mizan team approves as today.
No private upload of an activity for now: it reshapes a whole workspace, so it goes through review
twice (the package, then each workspace's change). Activities don't appear in the store's
"install" list: switching activity is how they are used.

### D2. A registry overlay, not a copy into the code tree
`app/framework/package_activities.py` keeps, per process, the definitions of approved activity
packages: for each activity listing, its current approved version (also when delisted, if a
workspace still runs it), re-verified like a store install. Every lookup above falls back to it
when the id isn't a Mizan activity folder, so menus, terms, variants, positions and installability
work unchanged for `acme.laundry`. The overlay is loaded at startup, reloaded in the process that
approves a version, and re-checked at most once a minute elsewhere (a cheap
`max(reviewed_at)` query), clearing the caches built from it.

### D3. Workspaces follow the listed version
Like Mizan's own activities, a workspace runs the activity's current approved version: an approved
update reaches every workspace running it (the reviewer sees how many). On approval, workspaces
running it get the update's new own modules and new Mizan modules; nothing leaves on an update.
Pinning versions per workspace would thread a version through every lookup; it can come later if
developers need staged rollouts.

### D4. What switching to a package activity does
The #107 change, plus the package's own parts:
- Mizan modules: the manifest's `modules` that are Mizan's join (and incompatible ones leave),
  exactly as between Mizan's activities. Variants come from the package's `variants/`.
- Its own modules install as community modules (ADR-007), with the scopes they declare; the owner
  sees those scopes in the request's preview and the team in the review. Menus may point at their
  screens (`<module>/<entity>`), resolved to `/x/<module>/<entity>`.
- Its themes install into the workspace (`workspace_themes`); the manifest's theme becomes the
  workspace's when the current theme belonged to the old activity (as in #107).
- Positions, terms, settings defaults, home, menus, dashboards and role layouts are read from the
  overlay. Seed records are not added to a live workspace (they are demo data for new workspaces).
- Switching away from a package activity removes its own modules like any leaving module: records
  are kept (hidden) or deleted as the owner chose.

### D5. Limits
Cloud workspaces only (as #107). New workspaces can't start from a package activity yet (signup
lists Mizan's activities; with it, seed data applies). Free only (paid after #65). If the
developer's key is revoked, workspaces keep running the activity (like installed modules) but no
workspace can switch to it, and its updates are refused.

## Consequences
- One code path for every activity: Mizan's from folders, developers' from reviewed packages.
- `tenants.sector` and `activity_changes` hold ids up to 80 characters (`<team>.<activity>`).
- A bad update reaches every workspace on that activity at once; review is the guard, and
  delisting stops new switches without breaking running workspaces.
- Developer activities can't run code (no hooks), as for modules, until the cluster (ADR-007).

## As built (2026-11-14)

- **Overlay**: `app/framework/package_activities.py` (`PackageActivity`: manifest, the activity as
  `variants.activity()` returns it (Mizan modules only in `modules`/`optional`, `own_modules`,
  `variants` → the activity's id, `source: "package"`), variants, own modules and themes as
  `Package`s for the existing install code, seed). Loaded by every app's startup
  (`factory.create_app` → `start()`, once per process), re-checked every 60 s against a stamp
  (approved activity versions, latest review, latest listing change, revoked keys), reloaded at
  once in the admin API after an approval or (de)listing. Caches cleared on reload:
  `variants.activity`, `variants.all_variants`, `screens.catalogue`, `positions.activity_of`,
  `positions.declared_positions`, and the standard positions are written again.
- **Fallbacks**: `variants.activity`, `variants.all_variants`, `catalog.family_of`,
  `positions.activity_of/declared_positions`, the slug resolver's first page; `hooks` skips variants
  without a folder. Menus: `screens.resolve(..., extra)` takes the user's community screens by
  `"<module>/<entity>"`, so an activity's menu places them; the rest stay in «وحدات إضافية».
- **Marketplace**: `kind: "activity"` accepted; not in the store's list (`STORE_KINDS`). The admin
  review shows family, home, Mizan modules, variants (fields, terms, settings), positions, themes,
  each own module's scopes and webhook host, and how many workspaces run it; approving reloads the
  overlay and runs `activity_change.follow_update` (new own modules, themes and Mizan modules for
  every workspace on it; nothing leaves).
- **Activity change**: `check_target` accepts listed, unrevoked package activities; `plan` adds
  `own_joining` (with scopes and webhook host), `own_leaving` and `package` (developer, version,
  themes); `apply` installs the own modules (their declared scopes approved by the owner's
  request) and themes, and uninstalls the old activity's own modules keeping their records.
  `theme_after` counts a package's themes as its activity's.
- **Owner panel**: `GET /account/activities/developers`; the change dialog lists them under
  «من المطورين», shows the developer, version, own modules and what they access, and needs the
  owner's agreement; workspace payloads carry `sector_name`. **Admin**: the change review and the
  marketplace review show the package parts; "Needs you" names the activity.
- **v76**: `tenants.sector`/`business_type`, `activity_changes.from/to_activity`,
  `org_positions.activity/category` widened to 80 characters.
- **Tests**: `admin/backend/tests/test_activity_packages.py` (publish → review → switch → menus,
  terms, variants, positions → update → delist → switch back). Checked in the browser end to end
  with the SDK's starter activity.
