# Platform

The engine every workspace has, never switched off (ADR-006):

- **Engines** (folders without a manifest), mounted by `system/backend/system_api/router.py`:
  `auth`, `permissions`, `notifications`, `printing`, `settings`, `billing`, `updates`,
  `archive`, `audit`, `licensing`, `tenancy`; still to build: `storage_quota`, `custom_fields`.
- **Platform modules** (with a manifest), loaded like any module: `core`, `i18n`,
  `automation_worker` (the scheduler), `marketplace` (the module centre, /modules); planned:
  `customization`.
