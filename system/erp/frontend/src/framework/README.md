# Framework (frontend)

The module runtime on the app side (ADR-006):

- `types.ts`: what a module provides (`ModuleDefinition`): screens and widgets.
- `registry.ts`: collects every module's `index.ts`; `widgetComponent(id)` finds a widget.
- `widgets.tsx`: the frames widgets draw in (`KpiCard`, `PanelCard`).
- `forms.tsx`: record forms as the workspace arranged them (`useRecordForm`, `RecordFormFields`,
  custom field inputs).

Menus, the home screen and the dashboard come from the backend for the role the user acts as
(`/settings/screens`, read by `useRoleScreens` in `lib/nav.ts`); the screen builder is
`features/designer`. Routes are still registered in `App.tsx`.
