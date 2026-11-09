# Mizan ERP — Security & Access Standards

## 1. Multi-Dimensional Authorization (RBAC + ABAC)
To prevent privilege escalation and ensure healthcare compliance, Mizan decouples three distinct concepts:
1. **Organizational Positions (Job Titles):** What the person does in real life (e.g., Chief Surgeon, ICU Nurse, Financial Auditor, Receptionist). Total of 98 standardized positions cataloged across clinical and administrative domains.
2. **Account Types:** License tier and system archetype (e.g., Executive, Doctor/Practitioner, Nurse/Allied Health, Cashier/Front Desk, System Admin).
3. **Roles & Permissions:** Granular capability flags (e.g., `clinical:read`, `clinical:rx_write`, `billing:post`, `admin:facility_configure`).

## 2. Clinical Isolation & Break-Glass Protocol
- Medical records (EMR, diagnoses, prescriptions) are protected by clinical isolation boundaries. Non-clinical staff (administrative, reception) can never view clinical encounter notes or lab results.
- **Break-Glass Emergency Protocol:** In critical life-saving emergencies, an authorized physician or emergency nurse may temporarily override access to locked patient charts by providing an emergency rationale (`patient_critical_unconscious`, `trauma_code_blue`).
- Break-glass events immediately trigger:
  1. High-priority notification to Medical Director & Compliance Officer.
  2. 24-hour time-limited elevated session.
  3. Permanent, tamper-evident record in `clinical_break_glass_events` audit table.

## 3. Cryptographic & Data Protection Controls
- Passwords hashed using Argon2id / bcrypt with high cost factors.
- Session tokens signed with HMAC-SHA256 (or asymmetric RS256 for external integrations).
- Sensitive patient identifiers (Egyptian National ID, Passport) masked in non-clinical views (e.g., `2980101****512`).

## 4. Owner Accounts & Payments (ADR-004)
- Owner tokens carry `scope: owner`: the ERP refuses them, and the owner API refuses ERP tokens.
- Paymob callbacks are verified with HMAC-SHA512 over Paymob's field list before anything is
  activated, and recorded once per Paymob transaction id (idempotent). Plans change only through
  `activate_invoice`, never from inside a workspace.

## 5. On-Site Installs & Licences (ADR-005)
- **Licence signing key.** Licences are signed with Ed25519 (`LICENSE_SIGNING_KEY`, set only on
  the owner and admin APIs in production). It is the platform's most sensitive secret: leaked,
  anyone can mint licences; lost, every install needs an update with a new public key. Keep an
  offline copy. The production public key is built into the app (`app.core.licensing`);
  outside production a development key derived from `SECRET_KEY` is used, which production
  installs never accept.
- **Offline enforcement.** An expired or revoked licence makes the install read-only (sign-in and
  licence endpoints still work). A copied key can't be prevented offline; installs are visible
  to the admin panel once they check in, and device limits are tracked in #92.
- **Database.** The bundled PostgreSQL listens on `127.0.0.1` only, with SCRAM passwords
  generated per install; it is never exposed to the network.
- **Network.** Single device listens on `127.0.0.1` only. LAN serves HTTPS with a certificate
  authority generated per install (server certificates ≤ 397 days, renewed automatically);
  on Windows the firewall rule admits the local subnet only.
- **Files.** `config.json` (database password, secret key) is readable by the service account
  only. On Windows, setup grants explicit access to the data folder (installing account and
  SYSTEM) and read/execute on the PostgreSQL programs, because PostgreSQL drops administrator
  rights when it starts.
- **Data stays on site.** Check-ins send the installation id, host name, OS, version and last
  backup time, never business data. Cloud backup will be opt-in and encrypted (#90).
