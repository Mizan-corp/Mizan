# Themes

Theme packs and the workspace's one theme (ADR-010 D3). Always on.

- `service.py`: the themes a workspace may use (Mizan's in `app/themes/`, its activity's in
  `activities/<activity>/themes/`, packages installed in it), the resolved current theme (in the
  workspace's `palette["name"]`), choosing one, installing and removing packages, font files,
  the print colour for invoices.
- `router.py`: `GET /themes/current` (everyone), `GET /themes`, `PUT /themes/current`,
  `/themes/packages/inspect|install`, `DELETE /themes/{id}` (`themes.manage`), public font files
  under `/themes/assets/`.
- Checks: `theme_problems` in `app/framework/manifest.py`. Table: `workspace_themes` (v73).
- Applied in the app by `system/core/frontend/src/lib/theme.ts`; chosen in the module centre
  (`system/erp/frontend/src/platform/themes/`).
