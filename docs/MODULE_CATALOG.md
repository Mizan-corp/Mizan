# Mizan ERP — Module Catalog

## 1. Global Business Activities & Modules Directory
Every module lives under its home activity: `shared/backend/app/modules/<activity>/<module_id>/` (screens in `system/frontend/src/modules/<activity>/<module_id>/`). Activities are defined in `shared/backend/app/activities/<activity_id>/activity.json`. Grouped below by activity:

### A. Healthcare & Hospitals (`healthcare/`)
- `facility_management` (HLT-01): Multi-branch organizations, facilities, buildings, floors, departments, rooms, and schedules.
- `patient_identity` (HLT-02): Master Patient Index, MRN generation, duplicate resolution, and legal guardian relationships.
- `appointments` (HLT-03): Multi-clinic appointment booking and waiting queues.
- `medical_staff` (HLT-04): Physician credentials, clinical privileges, and licenses.
- `emr` (HLT-05): Electronic Medical Records, SOAP notes, ICD-10 diagnoses.
- `consultation` (HLT-06): Outpatient clinical consultations and encounters.
- `admissions` (HLT-07): Inpatient Admission-Discharge-Transfer (ADT).
- `beds` (HLT-08): Ward and bed occupancy management.
- `nursing` (HLT-09): Medication Administration Records (MAR) and nursing shifts.
- `laboratory` (HLT-10): Lab tests, orders, specimen barcodes, and results.
- `radiology` (HLT-11): Imaging orders and PACS reports.
- `pharmacy` (HLT-12): Clinical dispensary and medication management.
- `emergency` (HLT-13): Emergency room triage and trauma workflows.
- `surgery` (HLT-14): Operating rooms and surgical suites.
- `billing` (HLT-15): Inpatient and outpatient clinical billing.
- `insurance` (HLT-16): Insurance policies, claims, and pre-authorizations.
- `inventory_procurement` (HLT-17): Medical equipment, surgical supplies, and medications.
- `accounting` (HLT-18): Healthcare cost accounting and departmental ledgers.
- `hr_workforce` (HLT-19): On-call rotations, night shifts, and locum doctor contracts.
- `equipment_maintenance` (HLT-20): Biomedical equipment calibration and preventive maintenance.
- `patient_portal` (HLT-21): Patient self-service, booking, and lab result downloads.
- `telemedicine` (HLT-22): Virtual consultations and tele-health sessions.
- `notifications` (HLT-23): SMS/WhatsApp appointment reminders and critical lab alerts.
- `analytics` (HLT-24): Clinical KPIs, bed turnover, and financial revenue cycle metrics.

### B. Retail & Point of Sale (`general/pos/`)
- Cashier shifts, barcode scanning, thermal receipt printing, and quick sales.

### C. Wholesale & Distribution (`wholesale/`)
- Bulk pricing, customer credit limits, delivery dispatch, and multi-warehouse transfers.

### D. Hospitality & Hotels (`hotel/`)
- Property Management System (PMS), room reservations, check-in/out, and folio billing.
