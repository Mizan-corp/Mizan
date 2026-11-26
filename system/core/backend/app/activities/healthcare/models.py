"""Aggregated database models for Healthcare ERP Business Suite (HLT-01 through HLT-24).
Imports all domain models across the 24 standalone healthcare modules.
"""
from .modules.facility_management.models import HealthcareFacility, FacilityDepartment
from .modules.patient_identity.models import PatientIdentity
from .modules.appointments.models import MedicalAppointment
from .modules.medical_staff.models import MedicalStaff
from .modules.emr.models import PatientVitalRecord, PatientAllergyRecord
from .modules.consultation.models import ClinicalEncounter
from .modules.admissions.models import InpatientAdmission
from .modules.beds.models import HospitalWard, HospitalBed
from .modules.nursing.models import MedicationAdminRecord
from .modules.laboratory.models import LabTestItem, LabSpecimenOrder
from .modules.radiology.models import RadiologyStudyOrder
from .modules.hospital_pharmacy.models import MedicationProduct, MedicationDispenseRecord
from .modules.emergency.models import EmergencyCase
from .modules.surgery.models import SurgicalCase
from .modules.medical_billing.models import PatientInvoice
from .modules.health_insurance.models import InsuranceClaimRecord
from .modules.medical_supplies.models import MedicalSupplyItem
from .modules.medical_accounting.models import HealthcareCostCenter
from .modules.medical_workforce.models import ClinicalCredentialRecord
from .modules.equipment_maintenance.models import BiomedicalDevice
from .modules.patient_portal.models import PatientPortalRequest
from .modules.telemedicine.models import TeleconsultationSession
from .modules.patient_notifications.models import HealthcareAlert
from .modules.hospital_analytics.models import HealthcareDailyMetric
