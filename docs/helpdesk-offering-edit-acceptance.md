# Existing offering edit acceptance

24 November 2026, isolated feature branch. LOCAL accepted, hosting pending.

## Contract

PATCH /helpdesk/offerings/{UUID} accepts expected and values, each the strict existing offering shape: name, description, starting_amount, currency. Explicit same-tenant row predicate and row lock. Help Desk activation, enabled service_catalog and catalog manage permission are required. Expected fields prevent stale overwrite; an exact desired-state retry is a no-op without duplicate audit. Changing content does not change offering identity or active/archive state. Audit records changed field names and currency, never service description.

No quote acceptance, invoice, payment, stock or prior-request change is performed. Supported currencies remain EGP/USD/EUR/GBP/SAR/AED/QAR. Starting amounts remain nonnegative fixed two-decimal values.

## Local acceptance observed

- Real JWT: anonymous401, missing manage403; missing row404, feature disabled409, unsupported currency/extra fields/invalid amount422.
- Update all four fields; reload retains them and the original identity.
- Exact desired replay200 without duplicate audit; stale expected-values409.
- Archived offering can be edited without restoring it.
- Actual configured ERP: desktop/mobile390, no horizontal overflow or page errors. Conflict freezes the old draft and offers close/reload before another attempt.
- Temporary users, source rows and settings were inside an outer rolled-back transaction, verified removed. No persistent schema change.

Screenshots are isolated acceptance data. Hosted verification remains a separate gate. Full Help Desk unification remains incomplete.
