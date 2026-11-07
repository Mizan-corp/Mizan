"""Aggregated database models for Healthcare ERP Business Suite (HLT-01 through HLT-24).
Imports all domain models across the 24 standalone healthcare modules.
"""
from .facility_management.backend.models import HealthcareFacility, FacilityDepartment
from .patient_identity.backend.models import PatientIdentity
from .appointments.backend.models import MedicalAppointment
from .medical_staff.backend.models import MedicalStaff
from .emr.backend.models import PatientVitalRecord, PatientAllergyRecord
from .consultation.backend.models import ClinicalEncounter
from .admissions.backend.models import InpatientAdmission
from .beds.backend.models import HospitalWard, HospitalBed
from .nursing.backend.models import MedicationAdminRecord
from .laboratory.backend.models import LabTestItem, LabSpecimenOrder
from .radiology.backend.models import RadiologyStudyOrder
from .pharmacy.backend.models import MedicationProduct, MedicationDispenseRecord
from .emergency.backend.models import EmergencyCase
from .surgery.backend.models import SurgicalCase
from .billing.backend.models import PatientInvoice
from .insurance.backend.models import InsuranceClaimRecord
from .inventory_procurement.backend.models import MedicalSupplyItem
from .accounting.backend.models import HealthcareCostCenter
from .hr_workforce.backend.models import ClinicalCredentialRecord
from .equipment_maintenance.backend.models import BiomedicalDevice
from .patient_portal.backend.models import PatientPortalRequest
from .telemedicine.backend.models import TeleconsultationSession
from .notifications.backend.models import HealthcareAlert
from .analytics.backend.models import HealthcareDailyMetric
