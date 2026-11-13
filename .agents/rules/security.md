# Security Rules for Antigravity

- **Zero Trust Authorization:** never rely on client-provided roles or permissions. Every backend route that reads or changes data checks `require_perm("<permission>")` (or `can(user, ...)`), with the permission declared in a module's manifest.
- **Clinical Data Isolation:** non-clinical roles (cashiers, HR, inventory clerks) never get clinical permissions; patient history, diagnoses and prescriptions stay behind them. (Break-glass is designed, not built.)
- **PII Protection:** Egyptian National ID (14 digits) and phone numbers are masked in summary exports and non-privileged views.
- **Tokens and secrets:** machine tokens are random, shown once and stored as SHA-256; never log tokens, secrets or passwords.
- **Outside code:** nothing a developer wrote runs inside Mizan; packages are verified (signature, certificate, revoked keys), scopes approved by the owner, webhooks only to public HTTPS hosts, themes validated (docs/SECURITY_STANDARDS.md §6).
