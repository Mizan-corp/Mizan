# Module-based ERP settings

Status: locally accepted prototype,24November2026. Isolated feature branch only; not a Help Desk implementation or a complete builder release.

## Scope

The ERP Settings page now provides a searchable sidebar of registered available modules, with installed modules first and inactive modules marked. Selecting a module loads its own schema and values from the existing settings API. Boolean features, selects, text and numeric options use their declared types. Empty schemas are shown honestly. The effective variation is displayed read-only because activity resolution, including planned-variation fallback, controls it. This refactor does not add a variation selector or change activity.

The existing workspace branding, invoice/VAT, network-device and personal settings remain in the General entry without moving stored keys or changing save semantics. General controls stay mounted when moving between modules so local input is not discarded. Module navigation asks before discarding unsaved changes. Module saves send only changed keys. Failed saves require reloading values before another attempt; there is no automatic write retry.

## Boundaries

- The acting role's existing settings permission governs module reads and writes. No owner-flag, role-name, manager-flag or wildcard shortcut is introduced.
- Manager and custom roles with settings permission keep their existing access. A cashier without it cannot retrieve or modify module values and does not see the module controls.
- Owner account/workspace lifecycle and billing controls stay in the owner panel. They are not copied into employee ERP Settings.
- Module value cache keys include user and acting-role identity, and module panels unmount on identity change. Sensitive-looking credential fields use password inputs. This is not a new secret-storage system or a permission expansion.
- Generic workspace settings writes cannot inject mod_settings_* values. Module keys go through existing schema validation and partial-merge saves. Saved data is not migrated or deleted.
- Inactive-module labels do not install, uninstall or activate anything. The existing module-management workflow remains separate.
- Website publication controls retain their separate reviewed routes and permissions. No catalog toggle is invented for an unlocated Help Desk contract.

## Local acceptance

Actual imported backend against isolated test workspace, under an outer transaction: authenticated owner selected POS, changed one declared Boolean, saved, fully reloaded and verified only that value changed. Unknown keys reject422without changing values. Generic mod_settings_* write rejects422. Existing general settings remain exact. Effective retail variation is returned read-only. UI search, unsaved-change cancel, old general/personal controls and390px layout were exercised. Temporary manager/custom-settings roles passed; temporary cashier had403on module reads/writes and no sidebar. All original settings and page state were checked after rollback.

TypeScript and production ERP build pass. Local screenshots are acceptance evidence, not proof of hosted deployment. Full application route and hosted regression remain separate release gates.

## Outstanding

Help Desk/catalog source and SRS gap are tracked in helpdesk-srs-gap-assessment.md. A working catalog feature, data model, final-price rules, public request workflow and builder service source are not delivered by this settings refactor. Original Astra-like full-site templates remain a separate unfinished outcome.
