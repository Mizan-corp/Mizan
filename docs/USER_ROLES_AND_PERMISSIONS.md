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

### Clinic actions by role (#131)

Each clinic action checks one permission (`require_clinic_*` in `healthcare_clinic/router.py`,
`useClinicPerms()` on the screen). The umbrella `clinic` passes every action check; only `admin`
and `manager` hold it. The clinical roles hold their own permissions only.

| Action | Permission (any of) | doctor | nurse | receptionist | lab_tech | pharmacist | accountant | manager / admin |
|---|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| See the clinic (patient list without clinical fields, appointments, beds) | `clinic:view` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Register / edit / delete patients, cancel and reschedule, manage care teams | `clinic:manage` | | | ✓ | | | | ✓ |
| Book an appointment | `clinic:manage`, `clinic:doctor` | ✓ | | ✓ | | | | ✓ |
| Move a patient through the queue (waiting, in consultation, completed) | `clinic:manage`, `clinic:doctor`, `clinic:nurse` | ✓ | ✓ | ✓ | | | | ✓ |
| Record an encounter, prescribe, order a lab test | `clinic:doctor` (+ patient access) | ✓ | | | | | | ✓ |
| Admit, discharge, ready a bed | `clinic:nurse`, `clinic:manage` | | ✓ | ✓ | | | | ✓ |
| Record and sign off a lab result | `clinic:lab` | | | | ✓ | | | ✓ |
| Dispense a prescription | `clinic:dispense` | | | | | ✓ | | ✓ |
| Invoices, payments, insurance claims, the summary's money figures | `clinic:billing` | | | ✓ | | | ✓ | ✓ |

- Invoice lines don't name the medication or the test: dispensing bills «صرف أدوية — روشتة RX-…»,
  a lab result «رسوم فحص مخبري — طلب LAB-…» (billing staff see invoices, not clinical data).
- Doctors no longer hold `finance`, `clinic:manage`, `clinic:billing`, `clinic:dispense` or
  `clinic:lab`; nurses no longer hold `clinic:manage`. A small clinic where the doctor also runs
  the front desk gives that user a second role (e.g. `receptionist`) or a workspace role.
- **Workspace roles and new permissions.** The standard roles are platform rows (no workspace),
  re-synced from `roles.py` by `ensure_standard_roles` when the API starts, so a change there
  reaches every workspace at once. Roles a workspace made itself (`ws-…`) are never changed by an
  update: a new permission reaches them only when the workspace's admin grants it on the roles
  screen. The personal copies migration v54 made of a standard role for users whose access
  differed (`doctor-1a2b3c4d`) are kept as they were too, except that
  `v84_clinic_role_separation` removed the umbrella `clinic` from the copies of the five clinical
  roles (keeping `clinic:view`).

## 2a. Sales and the POS

| Permission | Who holds it by default | What it allows |
|---|---|---|
| `sales` / `pos` | cashier, manager, admin | Sell, read sales (in the branches the user is assigned; managers and `supervise` holders: all) |
| `sales:return` | cashier, manager, admin | Full and partial returns; cash is refunded from the user's **own** open shift in the sale's branch |
| `sales:cancel` | manager, admin | Cancel a confirmed sale |
| `sales:override_price` | manager, admin | Sell at another price than the product's, only while the POS setting `allow_price_override` is on; discounts when the sales setting `allow_manual_discount` is off |
| `sales:negative_stock` | manager, admin | Sell more than the branch's stock while the inventory setting `prevent_negative_stock` is on |
| `shifts` / `pos` | cashier, manager, admin (pharmacist: `pos`) | Read a drawer (current shift, summary, rows, last amount): one's own, or any in reach for managers and `supervise` holders |
| `supervise` (or the manager flag with `shifts`) | manager, admin | Approve at the counter with one's password: closing a shift with a manager, revenue delivery to a safe |

Manager approvals (POS-4) used to rest on `users.is_manager` alone. Now the approver's acting role
must hold `supervise`, or the user must be flagged a manager **and** hold `shifts` (so managers
flagged before keep approving). Ten approval requests per user every 5 minutes; five wrong passwords
for one manager, or by one user, lock approvals for 15 minutes. A drawer is handed over (`shifts`)
only to an active user holding `shifts` who works in the shift's branch.

Until v95 cancelling and returning needed only `sales`. The personal copies of the manager and cashier
roles (`manager-1a2b3c4d`, `cashier-…`) that held `sales` were given `sales:cancel` + `sales:return`
and `sales:return` respectively, so they keep what they did; workspaces' own roles (`ws-…`) that held
`sales` got both, for the same reason (their admin can take them away).

## 2b. Stock, purchases and paying suppliers

| Action | Permission | storekeeper | accountant | manager | admin |
|---|---|:-:|:-:|:-:|:-:|
| Adjustments and damage by hand, transfers, movements, valuation | `inventory` | ✓ | ✓ | ✓ | ✓ |
| Opening stock by hand | `inventory:opening` | | | ✓ | ✓ |
| Dispatch and stock requests | `operations` | ✓ | | ✓ | ✓ |
| Cancel a dispatch (the stock goes back to the source) | `operations:cancel` | | | ✓ | ✓ |
| Purchase orders, receipts, purchase returns, suppliers and their prices | `purchases` | ✓ | ✓ | ✓ | ✓ |
| Paying a supplier or charging their account, paying on receipt, a refund on a return | `finance` (with `purchases` for the order) | | ✓ | ✓ | ✓ |

Every write on stock also needs access to the warehouse (`verify_warehouse_access`: assigned
warehouses, or `supervise` / managers for all). Migration `v96_ready_stock_ops` gave workspaces' own
roles holding `inventory` the new `purchases`, and those also holding `settings` `inventory:opening`;
none got `finance` from it. `operations:cancel` is new (a dispatch couldn't be undone before), so
workspaces' own roles get it only when their admin grants it.

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
