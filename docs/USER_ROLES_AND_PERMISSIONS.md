# Mizan ERP — User Roles, Positions & Permissions Architecture

## 1. Architectural Distinction
1. **Positions (Job Titles):** Real-world job titles (e.g. Hospital Director, Consultant Cardiologist, Staff Nurse, Pharmacist, Chief Accountant). Total: 98 standard positions.
2. **Account Types:** System tier (Executive, Physician, Nurse, Pharmacist, Lab Technician, Receptionist, Accountant, Administrator).
3. **Permissions:** Granular capability tokens (`scope:action`).

## 2. Standard Permission Scopes
- `facility:*`: Facility and organization configuration.
- `patient:*`: Patient intake, demographics, contact details.
- `clinical:*`: EMR, SOAP notes, vital signs, diagnoses (strictly clinical account types).
- `rx:*`: Prescriptions and pharmacy dispensing.
- `lab:*`: Laboratory tests, specimen collection, result verification.
- `billing:*`: Invoices, claims, payments, accounts receivable.
- `admin:*`: User provisioning, role assignment, audit log inspection.
- `emergency:break_glass`: Emergency clinical chart override.
