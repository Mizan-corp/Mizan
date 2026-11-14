# Healthcare & Clinic/Hospital ERP

السجلات الطبية الإلكترونية (EMR)، حجز المواعيد والكشوفات، الروشتات الرقمية (e-Rx)، الفحوصات والتحاليل، وإدارة غرف وأسِرّة التنويم والمطالبات التأمينية.

## Module ID
`clinic`

## Category
healthcare

## Dependencies
core, inventory, finance

## Patient-level clinical access (#113)

Clinical data (encounters, prescriptions, lab orders, allergies, chronic conditions, blood group)
is read and written per patient; the rules are in `service.py`:

- `clinic:doctor` / `clinic:nurse`: patients whose care team they are on (`clinic_care_team`),
  plus break-glass grants (`POST /clinic/patients/{id}/break-glass`, reason ≥ 10 characters,
  60 minutes, audited and notified to `clinic:privacy` holders).
- `clinic:all_patients`, or the setting `patient_access` = `all`: every patient.
- Pharmacy and lab queues: non-clinicians with `clinic:dispense` / `clinic:lab` see every
  prescription / lab order.
- Reception and billing get the patient list with clinical fields set to `null`
  (`clinical_access: false`).
- Booking with `doctor_user_id` (from `GET /clinic/clinicians`) puts the doctor on the care team;
  `clinic:manage` manages the team (`/clinic/patients/{id}/care-team`); nobody adds themselves to
  a patient they don't already reach.
- Every clinical read is logged in `clinic_access_log`. `clinic:privacy`: `GET /clinic/access-log`,
  `GET /clinic/break-glass`, `POST /clinic/break-glass/{id}/review` and `/revoke`.

Migrations: `v79_clinic_patient_access` (tables and columns), `v79b_clinic_care_team_backfill`
(`migrate.py`: links existing records to users by exact doctor name). Tests:
`system/backend/tests/test_clinic_patient_access.py`.
