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

## Errors and feedback (#48)

Every list on the screen goes through `components/QueryState.tsx`: a loading line while it
loads, and on failure the shared `ErrorBox` with the server's Arabic message and «إعادة المحاولة»
(never a silent empty list); smaller lists (care team, clinicians, patient picker, privacy tables)
use `InlineRetry`. Changes go through `useClinicMutation` / `useDialogMutation`
(`useClinicActions.ts`): `toast("success", …)` or `toast("error", <server detail>)`; a dialog
stays open on an error so the user can correct it, and its submit button waits while sending.

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

## Departments, rooms and rosters (#36)

- `GET /clinic/departments` (seeds the usual departments for a clinic with none), `POST`/`PUT
  /clinic/departments/{id}`; `GET/POST/PUT /clinic/rooms`; `GET/POST/PUT/DELETE /clinic/schedules`
  (doctors' weekly rosters: weekday 0 = Monday … 6 = Sunday, `HH:MM` times, slot length). Reading is
  open to the clinic; changes need `clinic:manage`. Roster rows of the same doctor or room don't overlap.
- Booking: `GET /clinic/clinicians?department_id=` lists the department's rostered doctors,
  `GET /clinic/schedule/slots?doctor_user_id=&date=` the doctor's slots that day and whether each is
  free. `POST /clinic/appointments` takes `department_id` (and keeps `department` = its name), puts a
  rostered doctor's appointment inside the roster (its department and room), stores `time_slot` as
  `HH:MM` ("11:30 AM" is still read) and refuses (409) an appointment overlapping another
  non-cancelled one of the same doctor or room; rescheduling follows the same rules. A doctor with
  no roster is booked at any time, as before. Logic in `scheduling.py`, routes in
  `routes/scheduling.py`; screen: the «الأقسام والجداول» tab (`tabs/SchedulingTab.tsx`) and the
  booking dialog. Migration `v85_clinic_departments_rosters`; tests
  `system/backend/tests/test_clinic_scheduling.py`.

## Referrals (#45)

- `POST /clinic/referrals` (clinic:doctor, with access to the patient's record): department, an
  optional doctor on its roster, priority (`routine`/`urgent`/`emergency`), reason, triage notes and
  the encounter it came from. The receiving doctors are notified.
- `GET /clinic/referrals?box=incoming|outgoing|all`: incoming = named to me, or to a department I'm
  rostered in (any doctor for a department with no roster) with no doctor named; `all` is for
  `clinic:manage`, without the reason and triage notes. Rows with clinical text are logged
  (`referrals`).
- `POST /clinic/referrals/{id}/accept`: the receiving doctor joins the care team (`consultant`) and
  so reaches the record; `/decline` (with a reason) and `/complete`. The sender is notified.
- `GET /clinic/referrals/{id}`: the encounter summary (the referral's encounter or the latest) only
  for those who reach the record, logged as `referral`.
- Screen: the «الإحالات» tab (`tabs/ReferralsTab.tsx`), «إحالة» on patient rows and encounter cards
  (`components/ReferralDialog.tsx`). Migration `v86_clinic_referrals`; tests
  `system/backend/tests/test_clinic_referrals.py`.

Route guards are in `guards.py` (shared by `router.py` and `routes/`); the route areas in
`routes/` are included by `router.py` under `/clinic`.

Migrations: `v79_clinic_patient_access` (tables and columns), `v79b_clinic_care_team_backfill`
(`migrate.py`: links existing records to users by exact doctor name). Tests:
`system/backend/tests/test_clinic_patient_access.py`.
