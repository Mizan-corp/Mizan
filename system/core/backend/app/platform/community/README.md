# Community modules

Developers' declarative modules in a workspace (ADR-007). Always on; who sees a module's screens
is decided by the permissions it declares.

- `service.py`: installed modules, their permissions and menu items, records validated against
  their entities (types, required fields, options, references checked to exist), install,
  update, uninstall (keep or delete records), installation tokens.
- `router.py`: `/community/*` for the app (records, the module centre's install from file with
  scope approval, tokens, the webhook log; `community.manage`), and mounts `ext_api.py`.
- `ext_api.py`: `/ext/v1`, the public API for modules' servers (installation token, scopes,
  240 requests a minute).
- `events.py`: signed webhooks, recorded with the change, retried by the `community_webhooks` job.
- Tables: `community_modules`, `ext_records`, `community_webhook_deliveries` (v69–v71).
- Screens: `system/frontend/src/platform/community/` (the generic `/x/<module>/<entity>` page and
  the module centre section). Developer docs: `dev.allmizan.live/docs`.
