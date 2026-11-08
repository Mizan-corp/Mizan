# Security Rules for Antigravity

- **Zero Trust Role Enforcement:** Never rely on client-provided roles or permissions. Check authorization on every backend endpoint via `has_permission(...)`.
- **Clinical Data Isolation:** Non-clinical personnel (cashiers, HR, inventory clerks) cannot access patient medical history, diagnoses, or prescriptions.
- **Break-Glass Auditability:** Any emergency chart override must be recorded in the audit trail with physician ID, timestamp, and justification.
- **PII Protection:** Egyptian National ID (14 digits) and phone numbers must be masked in summary exports and non-privileged views.
