# Platform

What every workspace has, never switched off (ADR-006):

- **Engines** (folders without a manifest), mounted by `system/backend/system_api/router.py`:
  `auth`, `permissions`, `notifications`, `printing`, `settings`, `billing`, `updates`,
  `archive`, `audit`, `licensing`, `tenancy`, `files`, `storage_quota`, `custom_fields`, and
  `developers` (the developer portal's accounts, teams, keys and CLI tokens, served by the website
  API's `/developers`).
- **Platform modules** (with a manifest), loaded like any module: `core`, `i18n`,
  `automation_worker` (the scheduler), `marketplace` (the module centre, `/modules`),
  `community` (developers' modules: records, screens, `/ext/v1`, webhooks; ADR-007), `themes`
  (theme packs and the workspace's theme; ADR-010); planned: `customization`.
