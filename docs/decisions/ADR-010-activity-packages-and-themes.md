# ADR-010: Business activities as packages, and theme packs

## Status

Accepted (2026-11-13, owner). Changes ADR-006's folder layout (modules by home activity) and
extends ADR-007 (community packages) to whole activities and themes.

Owner's decisions (2026-11-13):
- Every business activity becomes one self-contained folder (modules, variants, themes, seed
  data and everything else that makes it modular), so a developer can build a **full Mizan
  business activity with the Mizan framework**. This is what Mizan advertises to developers.
- All existing activities move now; module ids, URLs and stored data don't change.
- Theme packs (colours, fonts, radii, shadows, animations) are new: free now (Mizan's, the
  activity's own, and signed theme packages installed from file), paid ones when the
  marketplace and Paymob are live (#105, #65).
- A workspace has **one theme**, chosen by its admin, for everyone in it.

## Context

ADR-006 put modules in `app/modules/<home_activity>/<module_id>/` and the activity itself in
`app/activities/<activity>/` (activity.json, seed, positions). How an activity adapts another
activity's module (pharmacy's POS rules) lived inside that module (`pos/variants/pharmacy/`).
The system app's screens sat in `src/modules/<activity>/<module>/`. One activity was spread over
four places, and nothing about it could be handed to someone else as a unit.

Theming was six palettes hard-coded in CSS (`data-theme`), chosen per device, plus a brand hue
per workspace. Nothing could be added without a release.

## Decision

### D1. One folder per activity

```
shared/backend/app/activities/<activity>/
  activity.json        identity, family, base and optional modules, menus and dashboards per
                       role, positions, terms, home screen, default theme
  positions.json       (as before)
  seed.py              demo data (as before; packages use seed/*.json)
  modules/<module>/    the activity's own modules, in the standard structure (MODULE_STANDARD)
  variants/<module>/   how this activity adapts other activities' modules: variant.json
                       (fields, settings, terms) and hooks.py
  themes/<theme>/      theme packs that come with the activity (D3)
  i18n/, assets/       optional
system/frontend/src/activities/<activity>/
  modules/<module>/    the module's screens (as before, moved)
  variants/<module>/   screens a variant adds, if any
```

- `general` is an activity like the others (`activities/general/modules/pos`, …); every
  workspace has it. Platform engines (`app/platform/`) and connectors (`app/integrations/`) stay
  where they are: they belong to no activity.
- A module's **standard** variant (its own defaults, `variants/standard/`) stays in the module.
  Variants named after an activity move to that activity (`general/pos/variants/pharmacy/` →
  `pharmacy/variants/pos/`): the activity owns how it changes things.
- Imports become `app.activities.<activity>.modules.<module>…`. Module ids are unique across
  activities (as before), so routes, permissions, stored module lists and data are unaffected.
- `manage.py module new <activity> <id>` creates the module in its activity;
  `manage.py activity new <id>` creates an activity with the full layout.

### D2. Activity packages (developers)

The same layout is a package (`.mzm`, `kind: "activity"`), built, checked and signed by the
`mizan` CLI like a module package (ADR-007 D1/D5): `activity.json`, `modules/` (community
modules, declarative), `variants/` (variant.json only: extra fields, settings, terms),
`themes/`, `seed/*.json`. Until code modules can run in containers (ADR-007), an activity package
is declarative: no `hooks.py`, no Python, no frontend code. Installing one is designed with the
activity change work (#107): a new workspace can start from it, an existing one can switch to it.

### D3. Theme packs

A theme is a folder with `theme.json`:

```
{"id": "mizan.classic", "name": "ميزان", "name_en": "Mizan classic", "version": "1.0.0",
 "kind": "theme",
 "colors": {"light": {"primary": "#651E2C", "background": "…", …},
            "dark":  {"primary": "…", …}},
 "fonts":  {"body": "IBM Plex Sans Arabic", "display": "…", "files": ["assets/…woff2"]},
 "radius": "0.75rem",
 "shadows": "soft" | "flat" | "raised",
 "motion": "full" | "reduced" | "none",
 "density": "comfortable" | "compact"}
```

- The colour keys are the app's design tokens (`globals.css` variables); a theme sets them
  for light and dark, so every screen follows without code. Fonts are files in the theme
  (or system fonts); no outside font service is required (on-site installs work offline).
- Where themes come from: Mizan's own (`app/themes/`, today's six palettes become these),
  activities' `themes/`, and theme packages (`.mzm`, `kind: "theme"`, signed, installed from
  file into a workspace). Paid themes come with the marketplace.
- A workspace's admin (permission `themes.manage`) chooses its theme; everyone in the workspace
  sees it, printed documents and the storefront included. Users keep only light/dark and
  density on their device. A theme is validated (colour formats, contrast between text and
  background tokens, known keys) before it is installed.

### D4. Order of work

1. The activity layout (D1): move every activity, update the loader, scaffold, frontend
   registry, tests and docs.
2. Theme packs (D3): format and validator, Mizan's themes from today's palettes, the workspace
   theme, the themes section in the module centre, theme packages from file, activities' themes.
3. Activity packages (D2): the CLI (`mizan activity new`, `check`, `package`), validation and
   verification; installing them with #107.

## As built

- **Step 1 (2026-11-13)**: all 30 activities moved (149 modules; pharmacy, restaurant, retail and
  salon now own their POS variants, pharmacy its inventory one). Loader, variants, hooks,
  scaffold, frontend registry (`@activities/…`), tests and docs follow the layout.
- **Step 2 (2026-11-13)**: theme packs.
  - Format and checks: `theme_problems()` in `app/framework/manifest.py` (so the CLI checks the
    same way): required and optional tokens, `#hex` / `rgb()` / `oklch()` only, WCAG contrast
    (4.5 for body text on background, card and sidebar; 3 for the rest), font families and files
    (`fonts.files: [{family, src, weight, style}]`), radius, shadows, motion, density.
  - Mizan's themes: `app/themes/<id>/theme.json`, today's six palettes extracted from the CSS so
    their look is unchanged. Activities' themes: `activities/<activity>/themes/<id>/` (ids start
    with the activity). Packages: `.mzm` with `kind: "theme"` (its manifest is the theme, fonts in
    `assets/`), table `workspace_themes` (v73, RLS), installed from the module centre.
  - Platform engine `app/platform/themes/`: `GET /themes/current` (everyone), `GET /themes`,
    `PUT /themes/current`, packages inspect/install, `DELETE /themes/{id}` (permission
    `themes.manage`), public font files. The workspace's theme is `tenants.palette["name"]`; the
    resolve and `/auth/me` payloads carry the resolved theme, which `shared/frontend/src/lib/theme.ts`
    turns into CSS variables, `@font-face`, radius, shadows and motion (`data-motion`). The
    appearance dialog keeps only device choices (dark mode, layout, density). Printed invoices use
    the theme's brand colour (as hex) unless the workspace set a print colour.
  - SDK: `mizan theme new`, `check` and `package` for themes; docs article "Theme packs".
- **Step 3**: activity packages (to do).

## Consequences

- An activity is a unit a team can own, review, test, and later hand to a developer as a
  template: the folder Mizan's own teams work in is the shape third parties build.
- A large one-time move (about 300 Python files' imports and 170 frontend files). Nothing
  stored refers to folders, so it is a code change only; open branches need rebasing.
- Themes become data: new looks ship without a release, and a workspace can't break the app's
  layout with one (only tokens, fonts and motion presets are themable).
