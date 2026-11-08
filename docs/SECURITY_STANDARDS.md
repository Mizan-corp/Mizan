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
