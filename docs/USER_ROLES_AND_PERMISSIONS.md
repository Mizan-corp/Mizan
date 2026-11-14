# Mizan ERP — Roles, Positions & Permissions

One permission system (ADR-006 phase 3, `shared/backend/app/platform/permissions/`).

## 1. Three ideas, kept apart

1. **Permissions** say what can be done. Modules declare them in their manifest
   (`"permissions": [{"id": "pharmacy.dispense", "name": "…", "name_en": "…"}]`); the core ERP's
   are short ids (`pos`, `sales`, `inventory`, `finance`, `payroll`, `users`, `settings`,
   `designer`…). Routes check them with `require_perm("<id>")`, screens with `can("<id>")`.
   There is no `"*"` and no bypass by role name.
2. **Roles** hold permissions (`sys_roles.grants`):
   - the platform's **standard roles** (`roles.py`): `admin` (every declared permission,
     community modules' and `themes.manage` included), `manager`, `cashier`, `storekeeper`,
     `accountant`, and the clinical `doctor`, `nurse`, `receptionist`, `lab_tech`, `pharmacist`;
   - each workspace's **own roles**, made on the roles screen; nobody can grant a permission their
     own acting role doesn't hold.
   A user may be assigned several roles and **acts as one at a time**; the menu, home screen and
   dashboard follow the acting role (`/settings/screens`, ADR-006 phase 5).
3. **Positions** are job titles (`activities/<activity>/positions.json`: 248 across activities,
   `general`'s inherited by all), each suggesting roles. They describe people; they grant nothing.

## 2. Clinical records

Clinical roles (`doctor`, `nurse`, `lab_tech`, `pharmacist`) are marked `is_clinical`. Access to a
patient's clinical record (encounters, diagnoses, vitals, notes, prescriptions, lab orders,
allergies, chronic conditions, blood group) is decided **per patient** (#113,
`healthcare_clinic/service.py`):

| Who | Reads / writes clinical data of |
|---|---|
| `clinic:doctor` or `clinic:nurse` | The patients whose **care team** they are on (`clinic_care_team`), plus any patient opened by **break-glass** for 60 minutes |
| … with the module setting `patient_access` = `all` (small clinics) | Every patient |
| `clinic:all_patients` | Every patient |
| `clinic:dispense` without `clinic:doctor`/`clinic:nurse` (pharmacist) | Every prescription: the pharmacy queue |
| `clinic:lab` without `clinic:doctor`/`clinic:nurse` (lab technician) | Every lab order: the lab queue |
| Anyone else in the clinic (reception, billing) | No clinical data: the patient list shows demographics with clinical fields hidden; appointments, invoices and claims as before |

- The umbrella `clinic` permission does **not** open clinical records.
- A doctor joins the care team when an appointment is booked with them (`doctor_user_id`) or
  when they register the patient; `clinic:manage` holders add and remove members. Nobody can put
  **themselves** on the team of a patient they don't already reach (that is what break-glass is
  for).
- **Break-glass** (`clinic:doctor`/`clinic:nurse`): a reason of at least 10 characters opens one
  patient for 60 minutes; it is audited and notified to `clinic:privacy` holders.
- `clinic:privacy` (the privacy officer) reads the clinical access log and reviews or revokes
  break-glass grants (the clinic's «الخصوصية والوصول» tab).
- Standard roles: `manager` holds `clinic:all_patients` and `clinic:privacy`; `admin` holds every
  permission; doctors and nurses hold neither. Workspaces' own roles get them only when granted.

## 3. Permissions from the extension platform

| Permission | Who holds it by default | What it allows |
|---|---|---|
| `community.manage` | admin | Install, update and remove developers' modules; issue their connection tokens; see their webhook log |
| `<developer>.<module>.<…>` | admin | Whatever an installed community module declares (e.g. who sees its screens); grantable to custom roles |
| `themes.manage` | admin | Choose the workspace's theme; install and remove theme packages |

## 4. Accounts that aren't workspace users

| Account | Signs in at | Notes |
|---|---|---|
| Owner (`owner_accounts`) | `allmizan.live/login` | Owns workspaces; in each one also has an `admin` user (ADR-004) |
| Platform team (admin panel) | `allmizan.live/admin` | The Mizan team only |
| Developer (`developer_users`) | `dev.allmizan.live/login` | Separate from owners; in a **team** as `owner` (manages members, revokes keys) or `member` (registers keys, signs) |
