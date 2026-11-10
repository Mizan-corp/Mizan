"""Aggregated database models for Healthcare ERP Business Suite (HLT-01 through HLT-24).
Imports all domain models across the 24 standalone healthcare modules.
"""
from .facility_management.models import HealthcareFacility, FacilityDepartment
from .patient_identity.models import PatientIdentity
from .appointments.models import MedicalAppointment
from .medical_staff.models import MedicalStaff
from .emr.models import PatientVitalRecord, PatientAllergyRecord
from .consultation.models import ClinicalEncounter
from .admissions.models import InpatientAdmission
from .beds.models import HospitalWard, HospitalBed
from .nursing.models import MedicationAdminRecord
from .laboratory.models import LabTestItem, LabSpecimenOrder
from .radiology.models import RadiologyStudyOrder
from .pharmacy.models import MedicationProduct, MedicationDispenseRecord
from .emergency.models import EmergencyCase
from .surgery.models import SurgicalCase
from .billing.models import PatientInvoice
from .insurance.models import InsuranceClaimRecord
from .inventory_procurement.models import MedicalSupplyItem
from .accounting.models import HealthcareCostCenter
from .hr_workforce.models import ClinicalCredentialRecord
from .equipment_maintenance.models import BiomedicalDevice
from .patient_portal.models import PatientPortalRequest
from .telemedicine.models import TeleconsultationSession
from .notifications.models import HealthcareAlert
from .analytics.models import HealthcareDailyMetric
