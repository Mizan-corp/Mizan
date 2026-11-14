# Healthcare & Clinic/Hospital ERP

السجلات الطبية الإلكترونية (EMR)، حجز المواعيد والكشوفات، الروشتات الرقمية (e-Rx)، الفحوصات والتحاليل، وإدارة غرف وأسِرّة التنويم والمطالبات التأمينية.

## Module ID
`healthcare_clinic`

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

## Screen (system/frontend/src/activities/healthcare/modules/healthcare_clinic/)

- `ClinicHealthcarePage.tsx`: routing (`?tab=`, `/clinic/:moduleSlug`), permissions, data and the
  open dialog only; `ClinicContext.tsx` (typed `useClinic()`) hands them to the parts.
- `types.ts`: the API records (Patient, Appointment, Encounter, Prescription, LabOrder, Bed,
  Invoice, Claim, Clinician); `useClinicData.ts`: the queries; `useClinicActions.ts`: row actions
  and the mutation helper (typed toasts with the server's `detail`); `permissions.ts`:
  `useClinicPerms()`; `healthcareModules.ts`: the suite's 24 standalone screens.
- `tabs/`: one file per tab. `components/`: the dialogs (`RegisterPatientDialog`,
  `BookAppointmentDialog`, `EncounterDialog`, `PrescriptionDialog`, `LabOrderDialog`,
  `AdmitBedDialog`, `LabResultDialog`, each owning its form and request; `ClinicDialogs` picks the
  open one), the page parts (`ClinicHeader`, `ClinicKpis`, `HealthcareSuiteNav`, `ClinicTabsBar`,
  `StandaloneModuleView`), and the #113 dialogs (`BreakGlassDialog`, `CareTeamDialog`).

## Search and pagination (#39)

`GET /clinic/patients` (search: name, MRN, national id, phone) and `GET /clinic/appointments`
(search: patient, doctor, reference; filters `doctor_name`, `appointment_date`, `status`) take
`page` (from 1) and `page_size` (default 25, at most 100) and always return
`{items, total, page, pages}`. Patient rows keep the #113 redaction, and a page read clinically is
logged. On the screen the search box is debounced (300 ms) and sent to the server, each list has
a pager, and the dialogs pick patients with `PatientPicker` (the same search, 20 at a time).
Tests: `system/backend/tests/test_clinic_pagination.py`.

## Role separation (#131)

Every route checks the permission its guard names (`require_clinic_manage`, `_booking`, `_queue`,
`_doctor`, `_ward`, `_lab`, `_dispense`, `_billing`); the umbrella `clinic` (admin, manager) passes
them all, and the standard clinical roles don't hold it. The table of who does what is in
`docs/USER_ROLES_AND_PERMISSIONS.md` (§2). The screen mirrors the guards with `useClinicPerms()`
(`permissions.ts`). Dispensing and lab invoices carry neutral line text (no medication or test
name). `GET /clinic/summary` returns the money figures only to `clinic:billing`. Migration
`v84_clinic_role_separation`; tests `system/backend/tests/test_clinic_role_separation.py`.

Migrations: `v79_clinic_patient_access` (tables and columns), `v79b_clinic_care_team_backfill`
(`migrate.py`: links existing records to users by exact doctor name). Tests:
`system/backend/tests/test_clinic_patient_access.py`.
