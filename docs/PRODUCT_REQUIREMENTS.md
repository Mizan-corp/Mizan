# Mizan ERP — Product Requirements Document (PRD)

## 1. Product Mission & Value Proposition
Provide an all-in-one ERP that eliminates fragmented point solutions for business operators, offering:
- **Instant SaaS Onboarding:** Self-serve tenant creation with automatic database schema setup, default chart of accounts, and industry seed data.
- **Unified Master Data:** Shared patient/customer identity across authorized branches without data leakage.
- **Deep Compliance:** ETA e-Invoicing (UBL 2.1 JSON), Egyptian Healthcare Accreditation (GAHAR), Labor Law payroll tax rules.
- **Zero-Latency Interactions:** Keyboard-first shortcuts, optimistic UI updates, responsive layouts that run smoothly on tablets and desktop workstations.

## 2. Platform Foundations
1. **Multi-Tenancy & Isolation:** Complete cryptographic or RLS-enforced logical separation across organizations and branches.
2. **Global Access Control (RBAC + ABAC):** Distinguish Job Positions (what employees do), Account Types (license level), and granular Permissions (what system actions they can execute).
3. **Unified Audit Trail:** Every sensitive data read, mutation, export, or authorization override is logged with user, IP, timestamp, and delta diff.
4. **Offline Resilience & Sync:** Essential checkout (POS) and clinical intake queues can operate gracefully through transient connectivity drops.

## 3. High-Priority Functional Requirements (HLT Suite)
- **HLT-01:** Healthcare Organization & Facility Management (Multi-branch, buildings, floors, departments, units, rooms, operating hours, accreditations).
- **HLT-02:** Patient Registration & Master Patient Index (MRN generation, 14-digit Egyptian National ID validation, guardian relations, duplicate detection, record merge).
- **HLT-03:** Appointment Scheduling & Multi-Doctor Queue Management (Consultations, walk-ins, triage prioritization, multi-slot bookings).
- **HLT-04:** Medical Staff & Credentialing (Physicians, nurses, specialists, license expiry tracking, clinical privileges).
- **HLT-05:** Electronic Medical Record (EMR) & Clinical Encounters (SOAP notes, ICD-10 coding, vital signs history, allergies).
- **HLT-06:** e-Prescriptions & Clinical Dispensary (e-Rx, dosage checking, drug-drug interaction warnings).
- **HLT-07:** Inpatient Admissions & Discharge-Transfer (ADT).
- **HLT-08:** Bed Management & Ward Operations (Bed turnover, cleaning, oxygen/ventilator attributes).
- **HLT-09:** Nursing Station & Care Plans (MAR, nursing shifts, fluid balance).
- **HLT-10:** Laboratory Information System (LIS) (Test ordering, specimen barcode tracking, reference ranges, critical value alerts).
- **HLT-11:** Radiology Information System (RIS) & PACS integration.
- **HLT-12:** Hospital Pharmacy & Automated Formulary Control.
- **HLT-13:** Emergency Department (ED) & Emergency Triage (ESI 1-5).
- **HLT-14:** Operating Rooms (OR) & Surgical Suite Scheduling.
- **HLT-15:** Healthcare Billing, Insurance Claims & Universal Health Insurance (UHIA) Integration.
- **HLT-16:** Insurance Contracts & Pre-Authorization Workflows.
