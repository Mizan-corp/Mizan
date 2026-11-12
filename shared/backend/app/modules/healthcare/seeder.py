"""Seed complete realistic Arabic demo data across all 24 Healthcare ERP modules (HLT-01 through HLT-24).
Idempotent script: safely checks and seeds clinic facilities, patients, encounters, wards, beds,
laboratory tests, specimens, surgeries, invoices, pharmacy, and analytics KPIs for tenant 'a7a-clinic'.
"""
import asyncio
import os
import sys
import uuid
from datetime import date, datetime, timedelta

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import AsyncSessionLocal
from app.platform.tenancy.models import Tenant
from app.modules.healthcare.models import (
    HealthcareFacility, FacilityDepartment,
    PatientIdentity, MedicalStaff, MedicalAppointment,
    PatientVitalRecord, PatientAllergyRecord, ClinicalEncounter,
    InpatientAdmission, HospitalWard, HospitalBed, MedicationAdminRecord,
    LabTestItem, LabSpecimenOrder, RadiologyStudyOrder,
    MedicationProduct, EmergencyCase, SurgicalCase, PatientInvoice, InsuranceClaimRecord,
    MedicalSupplyItem, HealthcareCostCenter, ClinicalCredentialRecord,
    BiomedicalDevice, PatientPortalRequest, TeleconsultationSession,
    HealthcareAlert, HealthcareDailyMetric
)

async def seed_healthcare(session: AsyncSession | None = None, tenant_slug: str | None = None):
    if session is not None:
        await _seed_impl(session, tenant_slug)
    else:
        async with AsyncSessionLocal() as sess:
            await _seed_impl(sess, tenant_slug)

async def _seed_impl(session: AsyncSession, tenant_slug: str | None = None):
        # Enable RLS bypass for seeding
        await session.execute(text("SELECT set_config('app.bypass', 'on', false)"))
        
        # 1. Resolve or create tenant 'a7a-clinic'
        target_slug = tenant_slug or "a7a-clinic"
        res = await session.execute(select(Tenant).where(Tenant.slug == target_slug))
        tenant = res.scalar_one_or_none()
        
        if not tenant:
            res_hc = await session.execute(select(Tenant).where(Tenant.sector == "healthcare"))
            tenant = res_hc.scalar_one_or_none()
            
        if not tenant:
            print(f"Creating tenant '{target_slug}' (مجمع ومستشفى صحة الأمل التخصصي)...")
            tenant = Tenant(
                id=uuid.uuid4(),
                name="عيادات ومجمع صحة الأمل التخصصي",
                slug=target_slug,
                sector="healthcare",
                scale="enterprise",
                plan="enterprise",
                palette="warm_editorial",
                features={
                    "healthcare_suite": True,
                    "inpatient_hospital": True,
                    "lis_laboratory": True,
                    "ris_radiology": True,
                    "er_triage": True,
                    "surgery_ot": True,
                    "insurance_claims": True,
                }
            )
            session.add(tenant)
            await session.commit()
            await session.refresh(tenant)
            
        print(f"🏥 Seeding Healthcare Suite for Tenant: {tenant.name} ({tenant.slug}) -> ID: {tenant.id}")
        await session.execute(text("SELECT set_config('app.tenant_id', :tid, false)"), {"tid": str(tenant.id)})

        # 2. HLT-01: Facilities & Departments
        res_fac = await session.execute(select(HealthcareFacility).where(HealthcareFacility.tenant_id == tenant.id))
        fac = res_fac.scalars().first()
        if not fac:
            fac = HealthcareFacility(
                tenant_id=tenant.id,
                name="مجمع الأمل الطبي التخصصي — الفرع الرئيسي",
                name_en="Al-Amal Specialized Medical Center",
                code="HOSP-MAIN",
                facility_type="hospital",
                phone="0224158900",
                email="info@alamal-health.eg",
                license_no="MOH-CAIRO-8942",
                accreditation="GHAAR Standard",
                currency="EGP",
                operating_hours={"weekdays": "24/7", "clinics": "09:00 - 22:00"},
                is_active=True
            )
            session.add(fac)
            await session.commit()
            await session.refresh(fac)
            
            depts = [
                FacilityDepartment(tenant_id=tenant.id, facility_id=fac.id, name="قسم الباطنة والسكر", name_en="Internal Medicine & Diabetes", code="INT-MED", dept_type="outpatient", floor="الطابق الثاني"),
                FacilityDepartment(tenant_id=tenant.id, facility_id=fac.id, name="قسم القلب والأوعية الدموية", name_en="Cardiology", code="CARDIO", dept_type="outpatient", floor="الطابق الثاني"),
                FacilityDepartment(tenant_id=tenant.id, facility_id=fac.id, name="قسم الجراحة العامة والعمليات", name_en="General Surgery", code="SURG", dept_type="surgery", floor="الطابق الثالث"),
                FacilityDepartment(tenant_id=tenant.id, facility_id=fac.id, name="قسم الطوارئ والحالات الحرجة", name_en="Emergency", code="ER-DEPT", dept_type="emergency", floor="الطابق الأرضي"),
                FacilityDepartment(tenant_id=tenant.id, facility_id=fac.id, name="قسم المختبرات وبنك الدم", name_en="Laboratory", code="LIS-LAB", dept_type="laboratory", floor="الطابق الأول"),
                FacilityDepartment(tenant_id=tenant.id, facility_id=fac.id, name="قسم الأشعة والتصوير الطبي", name_en="Radiology", code="RAD-DEPT", dept_type="radiology", floor="الطابق الأرضي"),
            ]
            session.add_all(depts)
            await session.commit()
            print("  ✅ [HLT-01] Seeded facilities and departments.")

        # 3. HLT-02: Patient Identity (MPI)
        res_pts = await session.execute(select(PatientIdentity).where(PatientIdentity.tenant_id == tenant.id))
        existing_patients = res_pts.scalars().all()
        if not existing_patients:
            pts_data = [
                PatientIdentity(
                    tenant_id=tenant.id, mrn="MRN-2026-0811", national_id="29408120104822",
                    first_name="فاطمة الزهراء", last_name="علي محمد", date_of_birth=date(1994, 8, 12),
                    gender="female", phone="01019283741", email="fatima.ali@gmail.com", blood_group="O+",
                    emergency_contact_name="علي محمد (الأب)", emergency_contact_phone="01228491029"
                ),
                PatientIdentity(
                    tenant_id=tenant.id, mrn="MRN-2026-0812", national_id="28805200109153",
                    first_name="طارق", last_name="عبد الحميد محمود", date_of_birth=date(1988, 5, 20),
                    gender="male", phone="01158291043", email="tarek.mahmoud@yahoo.com", blood_group="A+",
                    emergency_contact_name="هدى عبد الحميد (الأخت)", emergency_contact_phone="01004928172"
                ),
                PatientIdentity(
                    tenant_id=tenant.id, mrn="MRN-2026-0813", national_id="29911040108871",
                    first_name="مروان", last_name="أحمد إبراهيم", date_of_birth=date(1999, 11, 4),
                    gender="male", phone="01284920194", email="marwan.khalil@outlook.com", blood_group="B+",
                    emergency_contact_name="أحمد إبراهيم (الأب)", emergency_contact_phone="01129481029"
                ),
                PatientIdentity(
                    tenant_id=tenant.id, mrn="MRN-2026-0814", national_id="27503150106644",
                    first_name="سعاد", last_name="إبراهيم الدسوقي", date_of_birth=date(1975, 3, 15),
                    gender="female", phone="01098492018", email="soad.desouky@gmail.com", blood_group="AB+",
                    emergency_contact_name="كريم حسن (الابن)", emergency_contact_phone="01229401827"
                ),
                PatientIdentity(
                    tenant_id=tenant.id, mrn="MRN-2026-0815", national_id="28207190103321",
                    first_name="محمود", last_name="صبري حسن الشافعي", date_of_birth=date(1982, 7, 19),
                    gender="male", phone="01558291049", email="m.sabry@alshafey.com", blood_group="O-",
                    emergency_contact_name="سلوى صبري (الزوجة)", emergency_contact_phone="01019284710"
                ),
            ]
            session.add_all(pts_data)
            await session.commit()
            res_pts = await session.execute(select(PatientIdentity).where(PatientIdentity.tenant_id == tenant.id))
            existing_patients = res_pts.scalars().all()
            print(f"  ✅ [HLT-02] Seeded {len(existing_patients)} master patient profiles.")

        p1, p2, p3 = existing_patients[0], existing_patients[1], existing_patients[2]

        # 4. HLT-04: Medical Staff & Doctors
        res_staff = await session.execute(select(MedicalStaff).where(MedicalStaff.tenant_id == tenant.id))
        staff_list = res_staff.scalars().all()
        if not staff_list:
            staff_list = [
                MedicalStaff(tenant_id=tenant.id, staff_type="doctor", first_name="هشام", last_name="الشناوي", specialty="أمراض الباطنة والسكري", license_number="EG-MOH-14201", license_expiry=date(2028, 12, 31), phone="01001122334", email="dr.hesham@mizan-health.com", consultation_fee=350.0),
                MedicalStaff(tenant_id=tenant.id, staff_type="doctor", first_name="منى", last_name="سراج الدين", specialty="أمراض القلب وقسطرة الشرايين", license_number="EG-MOH-18920", license_expiry=date(2027, 6, 30), phone="01112233445", email="dr.mona@mizan-health.com", consultation_fee=450.0),
                MedicalStaff(tenant_id=tenant.id, staff_type="doctor", first_name="شريف", last_name="العطار", specialty="الجراحة العامة والمناظير", license_number="EG-MOH-22410", license_expiry=date(2029, 3, 15), phone="01223344556", email="dr.attar@mizan-health.com", consultation_fee=400.0),
                MedicalStaff(tenant_id=tenant.id, staff_type="doctor", first_name="وائل", last_name="منصور", specialty="طب الطوارئ والحالات الحرجة", license_number="EG-MOH-25890", license_expiry=date(2028, 9, 30), phone="01554433221", email="dr.wael@mizan-health.com", consultation_fee=300.0),
            ]
            session.add_all(staff_list)
            await session.commit()
            res_staff = await session.execute(select(MedicalStaff).where(MedicalStaff.tenant_id == tenant.id))
            staff_list = res_staff.scalars().all()
            print(f"  ✅ [HLT-04] Seeded {len(staff_list)} medical staff & consultant profiles.")

        doc1, doc2, doc3 = staff_list[0], staff_list[1], staff_list[2]

        # 5. HLT-03: Medical Appointments
        res_apts = await session.execute(select(MedicalAppointment).where(MedicalAppointment.tenant_id == tenant.id))
        if not res_apts.scalars().first():
            today = date.today()
            apts = [
                MedicalAppointment(tenant_id=tenant.id, appointment_number="APT-2026-101", patient_id=p1.id, doctor_id=doc1.id, service_type="كشف باطنة دوري وتظبيط سكر", appointment_date=today, start_time="10:00 AM", end_time="10:30 AM", status="in_progress", queue_number=1, notes="مريض سكر نوع 2 - متابعة قياسات تراكمي"),
                MedicalAppointment(tenant_id=tenant.id, appointment_number="APT-2026-102", patient_id=p2.id, doctor_id=doc2.id, service_type="استشارة وفحص موجات صوتية للقلب", appointment_date=today, start_time="10:30 AM", end_time="11:00 AM", status="confirmed", queue_number=2, notes="تسجيل خفقان متكرر مع مجهود بسيط"),
                MedicalAppointment(tenant_id=tenant.id, appointment_number="APT-2026-103", patient_id=p3.id, doctor_id=doc3.id, service_type="كشف جراحة عامة ومتابعة فتق إربي", appointment_date=today, start_time="11:15 AM", end_time="11:45 AM", status="scheduled", queue_number=3, notes="تحويل من عيادة التأمين الصحي"),
                MedicalAppointment(tenant_id=tenant.id, appointment_number="APT-2026-104", patient_id=existing_patients[3].id, doctor_id=doc1.id, service_type="كشف باطنة وجهاز هضمي", appointment_date=today + timedelta(days=1), start_time="02:00 PM", end_time="02:30 PM", status="scheduled", queue_number=1),
            ]
            session.add_all(apts)
            await session.commit()
            print("  ✅ [HLT-03] Seeded clinic appointments.")

        # 6. HLT-05: Longitudinal EMR (Vitals & Allergies)
        res_vit = await session.execute(select(PatientVitalRecord).where(PatientVitalRecord.tenant_id == tenant.id))
        if not res_vit.scalars().first():
            vitals = [
                PatientVitalRecord(tenant_id=tenant.id, patient_id=p1.id, systolic_bp=128, diastolic_bp=82, pulse_rate=76, temperature=37.1, respiratory_rate=18, oxygen_saturation=98, height_cm=165, weight_kg=72, bmi=26.4),
                PatientVitalRecord(tenant_id=tenant.id, patient_id=p2.id, systolic_bp=145, diastolic_bp=94, pulse_rate=88, temperature=36.9, respiratory_rate=20, oxygen_saturation=97, height_cm=178, weight_kg=86, bmi=27.1),
                PatientVitalRecord(tenant_id=tenant.id, patient_id=p3.id, systolic_bp=118, diastolic_bp=75, pulse_rate=72, temperature=37.0, respiratory_rate=16, oxygen_saturation=99, height_cm=172, weight_kg=68, bmi=23.0),
            ]
            allergies = [
                PatientAllergyRecord(tenant_id=tenant.id, patient_id=p1.id, allergen="مجموعة البنسلين ومشتقاته (Penicillin)", allergy_type="drug", severity="severe", reaction="صدمة تحسسية وطفح جلدي حاد (Anaphylaxis)", is_active=True),
                PatientAllergyRecord(tenant_id=tenant.id, patient_id=p3.id, allergen="مضادات الالتهاب غير الستيرويدية (NSAIDs/Aspirin)", allergy_type="drug", severity="high", reaction="ضيق تنفس ونوبة ربو حادة", is_active=True),
                PatientAllergyRecord(tenant_id=tenant.id, patient_id=existing_patients[4].id, allergen="صبغات الأشعة المقطعية (Iodinated Contrast)", allergy_type="drug", severity="moderate", reaction="وذمة وعائية وطفح حاد", is_active=True),
            ]
            session.add_all(vitals)
            session.add_all(allergies)
            await session.commit()
            print("  ✅ [HLT-05] Seeded longitudinal vitals & drug allergies.")

        # 7. HLT-06: Clinical Consultations (SOAP)
        res_enc = await session.execute(select(ClinicalEncounter).where(ClinicalEncounter.tenant_id == tenant.id))
        if not res_enc.scalars().first():
            encs = [
                ClinicalEncounter(
                    tenant_id=tenant.id, encounter_number="ENC-2026-901", patient_id=p1.id, doctor_id=doc1.id,
                    chief_complaint="ارتفاع قراءات السكر الصائم لأكثر من 190 مع عطش متكرر وإجهاد",
                    examination="فحص قاع العين سليم، عدم وجود تقرحات بالقدمين، النبض الطرفي طبيعي",
                    icd10_code="E11.9", diagnosis="Type 2 diabetes mellitus without complications",
                    treatment_plan="تعديل جرعة الجلوكوفاج 1000 مجم مرتين يومياً وإضافة جانوفيا 100 مجم صباحاً مع حمية غذائية وممارسة رياضة خفيفة",
                    status="finalized", signed_at=datetime.utcnow() - timedelta(minutes=45)
                ),
                ClinicalEncounter(
                    tenant_id=tenant.id, encounter_number="ENC-2026-902", patient_id=p2.id, doctor_id=doc2.id,
                    chief_complaint="نوبات خفقان مع دوار طفيف عند بذل مجهود صعود الدرج",
                    examination="أصوات القلب منتظمة مع لغط انقباضي طفيف، ضغط الدم 145/94",
                    icd10_code="I10", diagnosis="Essential (primary) hypertension",
                    treatment_plan="طلب رسم قلب عاجل وهولتر 24 ساعة، وبدء كونكور 5 مجم يومياً صباحاً",
                    status="in_progress"
                )
            ]
            session.add_all(encs)
            await session.commit()
            print("  ✅ [HLT-06] Seeded clinical SOAP encounters.")

        # 8. HLT-08: Hospital Wards & Beds
        res_ward = await session.execute(select(HospitalWard).where(HospitalWard.tenant_id == tenant.id))
        w1 = res_ward.scalars().first()
        if not w1:
            w1 = HospitalWard(tenant_id=tenant.id, name="جناح العناية المركزة (ICU)", code="WARD-ICU", ward_type="icu", floor="الطابق الثالث", is_active=True)
            w2 = HospitalWard(tenant_id=tenant.id, name="جناح الجراحة العامة الداخلي", code="WARD-SURG", ward_type="surgical", floor="الطابق الرابع", is_active=True)
            w3 = HospitalWard(tenant_id=tenant.id, name="جناح الباطنة والقلب التخصصي", code="WARD-MED", ward_type="general", floor="الطابق الثاني", is_active=True)
            session.add_all([w1, w2, w3])
            await session.commit()
            await session.refresh(w1)
            await session.refresh(w2)
            await session.refresh(w3)

            beds = [
                HospitalBed(tenant_id=tenant.id, ward_id=w1.id, bed_number="ICU-BED-01", bed_type="icu", daily_rate=3500.0, status="occupied", current_patient_id=existing_patients[4].id),
                HospitalBed(tenant_id=tenant.id, ward_id=w1.id, bed_number="ICU-BED-02", bed_type="icu", daily_rate=3500.0, status="available"),
                HospitalBed(tenant_id=tenant.id, ward_id=w2.id, bed_number="SURG-BED-101", bed_type="standard", daily_rate=1200.0, status="occupied", current_patient_id=p2.id),
                HospitalBed(tenant_id=tenant.id, ward_id=w2.id, bed_number="SURG-BED-102", bed_type="standard", daily_rate=1200.0, status="cleaning"),
                HospitalBed(tenant_id=tenant.id, ward_id=w3.id, bed_number="MED-BED-201", bed_type="vip", daily_rate=2200.0, status="available"),
                HospitalBed(tenant_id=tenant.id, ward_id=w3.id, bed_number="MED-BED-202", bed_type="standard", daily_rate=950.0, status="available"),
            ]
            session.add_all(beds)
            await session.commit()
            print("  ✅ [HLT-08] Seeded wards and live beds.")

            # 9. HLT-07: Inpatient Admissions (ADT)
            res_bed = await session.execute(select(HospitalBed).where(HospitalBed.tenant_id == tenant.id))
            all_beds = res_bed.scalars().all()
            b1 = all_beds[0]
            b3 = all_beds[2]

            adms = [
                InpatientAdmission(
                    tenant_id=tenant.id, admission_number="ADM-2026-001", patient_id=existing_patients[4].id,
                    doctor_id=doc2.id, ward_id=w1.id, bed_id=b1.id, admission_date=datetime.utcnow() - timedelta(days=2),
                    discharge_date=datetime.utcnow() + timedelta(days=2), admission_reason="جلطة قلبية حادة غير مكتملة الجدار (NSTEMI) مع عدم انتظام نبض",
                    discharge_summary="مستقر تحت الملاحظة ومراقبة إنزيمات القلب", status="admitted"
                ),
                InpatientAdmission(
                    tenant_id=tenant.id, admission_number="ADM-2026-002", patient_id=p2.id,
                    doctor_id=doc3.id, ward_id=w2.id, bed_id=b3.id, admission_date=datetime.utcnow() - timedelta(days=1),
                    discharge_date=datetime.utcnow() + timedelta(days=1), admission_reason="استئصال مرارة بالمنظار (Laparoscopic Cholecystectomy)",
                    discharge_summary="تمت الجراحة بنجاح، رعاية ما بعد الإفاقة", status="admitted"
                )
            ]
            session.add_all(adms)
            await session.commit()
            print("  ✅ [HLT-07] Seeded inpatient admission records (ADT).")

        # 10. HLT-09: Nursing & e-MAR
        res_mar = await session.execute(select(MedicationAdminRecord).where(MedicationAdminRecord.tenant_id == tenant.id))
        if not res_mar.scalars().first():
            mars = [
                MedicationAdminRecord(tenant_id=tenant.id, patient_id=existing_patients[4].id, medication_name="Clexane 60mg (Enoxaparin)", dosage="60 mg", route="Subcutaneous", scheduled_time="08:00 AM", status="administered", nurse_notes="حقن تحت الجلد بالبطن دون كدمات", administered_at=datetime.utcnow() - timedelta(hours=4)),
                MedicationAdminRecord(tenant_id=tenant.id, patient_id=existing_patients[4].id, medication_name="Plavix 75mg (Clopidogrel)", dosage="75 mg", route="Oral", scheduled_time="02:00 PM", status="administered", nurse_notes="تناول القرص بعد الغداء", administered_at=datetime.utcnow() - timedelta(hours=1)),
                MedicationAdminRecord(tenant_id=tenant.id, patient_id=p2.id, medication_name="Cefotax 1g IV", dosage="1000 mg", route="IV Infusion", scheduled_time="06:00 PM", status="pending", nurse_notes="مقرر بعد اختبار الحساسية"),
            ]
            session.add_all(mars)
            await session.commit()
            print("  ✅ [HLT-09] Seeded nursing medication administration records (MAR).")

        # 11. HLT-10: Laboratory Catalog & Specimens (LIS)
        res_lab = await session.execute(select(LabTestItem).where(LabTestItem.tenant_id == tenant.id))
        lab_items = res_lab.scalars().all()
        if not lab_items:
            lab_items = [
                LabTestItem(tenant_id=tenant.id, code="CBC", name="صورة دم كاملة (Complete Blood Count)", category="Hematology", sample_type="EDTA Whole Blood", unit="10^3/uL", normal_range="4.0 - 11.0", price=180.0),
                LabTestItem(tenant_id=tenant.id, code="HBA1C", name="السكر التراكمي (Glycated Hemoglobin)", category="Biochemistry", sample_type="Whole Blood", unit="%", normal_range="4.0 - 5.6", price=220.0),
                LabTestItem(tenant_id=tenant.id, code="TROP-I", name="إنزيم تروبونين عالي الحساسية (hs-cTnI)", category="Cardiac", sample_type="Serum", unit="ng/mL", normal_range="0.0 - 0.04", price=350.0),
                LabTestItem(tenant_id=tenant.id, code="LIPID", name="دهنيات الدم الشاملة (Lipid Profile)", category="Biochemistry", sample_type="Serum Fasting", unit="mg/dL", normal_range="100.0 - 200.0", price=280.0),
                LabTestItem(tenant_id=tenant.id, code="CREAT", name="وظائف كلى - سيروم كرياتينين (Serum Creatinine)", category="Renal", sample_type="Serum", unit="mg/dL", normal_range="0.7 - 1.3", price=120.0),
            ]
            session.add_all(lab_items)
            await session.commit()
            res_lab = await session.execute(select(LabTestItem).where(LabTestItem.tenant_id == tenant.id))
            lab_items = res_lab.scalars().all()
            print("  ✅ [HLT-10] Seeded laboratory test catalog (LIS).")

            specimens = [
                LabSpecimenOrder(tenant_id=tenant.id, barcode="LAB-2026-901", patient_id=p1.id, test_id=lab_items[1].id, result_value="7.8 %", is_abnormal=True, is_critical=False, status="completed", completed_at=datetime.utcnow() - timedelta(hours=3)),
                LabSpecimenOrder(tenant_id=tenant.id, barcode="LAB-2026-902", patient_id=existing_patients[4].id, test_id=lab_items[2].id, result_value="0.85 ng/mL", is_abnormal=True, is_critical=True, status="completed", completed_at=datetime.utcnow() - timedelta(hours=2)),
                LabSpecimenOrder(tenant_id=tenant.id, barcode="LAB-2026-903", patient_id=p2.id, test_id=lab_items[0].id, result_value="14.2 g/dL", is_abnormal=False, is_critical=False, status="completed", completed_at=datetime.utcnow() - timedelta(minutes=40)),
            ]
            session.add_all(specimens)
            await session.commit()
            print("  ✅ [HLT-10] Seeded specimen orders & critical results.")

        # 12. HLT-11: Radiology & Imaging (RIS/PACS)
        res_rad = await session.execute(select(RadiologyStudyOrder).where(RadiologyStudyOrder.tenant_id == tenant.id))
        if not res_rad.scalars().first():
            rads = [
                RadiologyStudyOrder(tenant_id=tenant.id, order_number="RAD-2026-101", patient_id=p2.id, doctor_id=doc2.id, modality="Echocardiography", body_part="Heart & Valves", clinical_notes="تقييم كفاءة العضلة والارتجاف", findings="EF 60%, Moderate mitral regurgitation with concentric LVH", status="completed"),
                RadiologyStudyOrder(tenant_id=tenant.id, order_number="RAD-2026-102", patient_id=p3.id, doctor_id=doc3.id, modality="Ultrasound", body_part="Abdomen & Pelvis", clinical_notes="ألم موضعي بالجهة اليمنى السفلية", findings="Gallstones noted with no acute cholecystitis, normal appendix", status="completed"),
                RadiologyStudyOrder(tenant_id=tenant.id, order_number="RAD-2026-103", patient_id=existing_patients[4].id, doctor_id=doc2.id, modality="Chest X-Ray", body_part="Thorax PA", clinical_notes="استبعاد ارتشاح رئوي بالعناية", findings="Mild bilateral perihilar congestion, no pleural effusion", status="completed"),
            ]
            session.add_all(rads)
            await session.commit()
            print("  ✅ [HLT-11] Seeded radiology imaging studies (RIS/PACS).")

        # 13. HLT-12: Pharmacy & Formulary
        res_med = await session.execute(select(MedicationProduct).where(MedicationProduct.tenant_id == tenant.id))
        if not res_med.scalars().first():
            meds = [
                MedicationProduct(tenant_id=tenant.id, code="MED-GLUC-1000", trade_name="Glucophage 1000mg", generic_name="Metformin Hydrochloride", dosage_form="أقراص مغلفة", strength="1000 mg", unit_price=65.0, stock_qty=480, is_controlled=False),
                MedicationProduct(tenant_id=tenant.id, code="MED-CONC-05", trade_name="Concor 5mg", generic_name="Bisoprolol Fumarate", dosage_form="أقراص", strength="5 mg", unit_price=48.5, stock_qty=320, is_controlled=False),
                MedicationProduct(tenant_id=tenant.id, code="MED-CLEX-60", trade_name="Clexane 60mg", generic_name="Enoxaparin Sodium", dosage_form="سرنجات جاهزة للحقن", strength="60 mg / 0.6 ml", unit_price=160.0, stock_qty=150, is_controlled=False),
                MedicationProduct(tenant_id=tenant.id, code="MED-MORPH-10", trade_name="Morphine Sulfate 10mg/ml", generic_name="Morphine Sulfate", dosage_form="أمبولات حقن وريدي/عضلي", strength="10 mg/ml", unit_price=85.0, stock_qty=35, is_controlled=True),
                MedicationProduct(tenant_id=tenant.id, code="MED-JANU-100", trade_name="Januvia 100mg", generic_name="Sitagliptin", dosage_form="أقراص", strength="100 mg", unit_price=180.0, stock_qty=210, is_controlled=False),
            ]
            session.add_all(meds)
            await session.commit()
            print("  ✅ [HLT-12] Seeded hospital formulary medications.")

        # 14. HLT-13: Emergency Department (ER Triage)
        res_er = await session.execute(select(EmergencyCase).where(EmergencyCase.tenant_id == tenant.id))
        if not res_er.scalars().first():
            er_cases = [
                EmergencyCase(tenant_id=tenant.id, case_number="ER-2026-001", patient_id=existing_patients[4].id, triage_level=1, chief_complaint="ألم صدري ضاغط شديد مع تعرق بارد وضيق تنفس حاد", arrival_mode="ambulance", assigned_bay="ER-RESUS-01", status="admitted", arrived_at=datetime.utcnow() - timedelta(hours=6)),
                EmergencyCase(tenant_id=tenant.id, case_number="ER-2026-002", patient_id=existing_patients[3].id, triage_level=3, chief_complaint="مغص كلوي حاد بالجانب الأيمن مع قيء متكرر", arrival_mode="walk_in", assigned_bay="ER-BAY-04", status="observing", arrived_at=datetime.utcnow() - timedelta(hours=2)),
                EmergencyCase(tenant_id=tenant.id, case_number="ER-2026-003", patient_id=p3.id, triage_level=4, chief_complaint="جرح قطعي سطحي بالساعد الأيمن إثر زجاج", arrival_mode="walk_in", assigned_bay="ER-MINORS-02", status="triaged", arrived_at=datetime.utcnow() - timedelta(minutes=30)),
            ]
            session.add_all(er_cases)
            await session.commit()
            print("  ✅ [HLT-13] Seeded emergency triage cases (ER).")

        # 15. HLT-14: Operating Room & Surgery (OT)
        res_surg = await session.execute(select(SurgicalCase).where(SurgicalCase.tenant_id == tenant.id))
        if not res_surg.scalars().first():
            surgeries = [
                SurgicalCase(tenant_id=tenant.id, case_number="OT-2026-001", patient_id=p2.id, surgeon_id=doc3.id, theater_name="غرفة العمليات الكبرى 02 (OR-02)", procedure_name="استئصال المرارة بالمنظار الجراحي", scheduled_date=datetime.utcnow() + timedelta(days=1, hours=2), who_checklist_completed=True, status="scheduled"),
                SurgicalCase(tenant_id=tenant.id, case_number="OT-2026-002", patient_id=p3.id, surgeon_id=doc3.id, theater_name="غرفة جراحة اليوم الواحد 01 (Day-Care 01)", procedure_name="إصلاح فتق إربي بالشبكة الجراحية", scheduled_date=datetime.utcnow() + timedelta(days=3), who_checklist_completed=False, status="scheduled"),
            ]
            session.add_all(surgeries)
            await session.commit()
            print("  ✅ [HLT-14] Seeded surgical operating room cases (OT).")

        # 16. HLT-15 & HLT-16: Billing, Invoicing & Insurance Claims
        res_inv = await session.execute(select(PatientInvoice).where(PatientInvoice.tenant_id == tenant.id))
        inv_list = res_inv.scalars().all()
        if not inv_list:
            inv_list = [
                PatientInvoice(tenant_id=tenant.id, invoice_number="INV-HLT-2026-101", patient_id=p1.id, total_amount=750.0, insurance_share=600.0, patient_share=150.0, paid_amount=150.0, payment_status="paid"),
                PatientInvoice(tenant_id=tenant.id, invoice_number="INV-HLT-2026-102", patient_id=p2.id, total_amount=1650.0, insurance_share=1320.0, patient_share=330.0, paid_amount=330.0, payment_status="paid"),
                PatientInvoice(tenant_id=tenant.id, invoice_number="INV-HLT-2026-103", patient_id=existing_patients[4].id, total_amount=9400.0, insurance_share=7520.0, patient_share=1880.0, paid_amount=1000.0, payment_status="partially_paid"),
            ]
            session.add_all(inv_list)
            await session.commit()
            res_inv = await session.execute(select(PatientInvoice).where(PatientInvoice.tenant_id == tenant.id))
            inv_list = res_inv.scalars().all()
            print("  ✅ [HLT-15] Seeded patient medical invoices.")

            claims = [
                InsuranceClaimRecord(tenant_id=tenant.id, claim_number="CLM-2026-001", provider_name="شركة بوبا مصر للتأمين", patient_id=p1.id, claimed_amount=600.0, approved_amount=600.0, status="approved"),
                InsuranceClaimRecord(tenant_id=tenant.id, claim_number="CLM-2026-002", provider_name="شركة مصر للتأمين التكافلي", patient_id=p2.id, claimed_amount=1320.0, approved_amount=0.0, status="submitted"),
                InsuranceClaimRecord(tenant_id=tenant.id, claim_number="CLM-2026-003", provider_name="شركة متلايف أليكو", patient_id=existing_patients[4].id, claimed_amount=7520.0, approved_amount=7000.0, status="approved"),
            ]
            session.add_all(claims)
            await session.commit()
            print("  ✅ [HLT-16] Seeded medical insurance claims.")

        # 17. HLT-17 & HLT-18: Inventory Consumables & Hospital Cost Centers
        res_items = await session.execute(select(MedicalSupplyItem).where(MedicalSupplyItem.tenant_id == tenant.id))
        if not res_items.scalars().first():
            supplies = [
                MedicalSupplyItem(tenant_id=tenant.id, item_code="MED-CAN-20G", name="كانيولا وريدية معقمة مقاس 20G (وردي)", category="Consumables", unit="قطعة", stock_qty=1200, min_alert_qty=250, cost_price=4.5),
                MedicalSupplyItem(tenant_id=tenant.id, item_code="MED-SYR-05ML", name="سرنجات معقمة 5 سم مع سن", category="Consumables", unit="قطعة", stock_qty=2400, min_alert_qty=500, cost_price=2.0),
                MedicalSupplyItem(tenant_id=tenant.id, item_code="MED-GLV-075", name="قفازات جراحية لاتكس مقاس 7.5 معقمة", category="PPE", unit="زوج", stock_qty=850, min_alert_qty=200, cost_price=8.0),
                MedicalSupplyItem(tenant_id=tenant.id, item_code="SURG-SUT-N30", name="خيوط جراحية نايلون 3-0 مع إبرة قاطعة", category="Surgical", unit="علبة", stock_qty=320, min_alert_qty=50, cost_price=35.0),
            ]
            cost_centers = [
                HealthcareCostCenter(tenant_id=tenant.id, code="CC-CLINIC", name="مركز تكلفة العيادات الخارجية", center_type="outpatient", budget=1500000.0, actual_spent=420000.0),
                HealthcareCostCenter(tenant_id=tenant.id, code="CC-ICU", name="مركز تكلفة الرعاية المركزة", center_type="inpatient", budget=3200000.0, actual_spent=1150000.0),
                HealthcareCostCenter(tenant_id=tenant.id, code="CC-SURG", name="مركز تكلفة غرف العمليات", center_type="surgery", budget=2800000.0, actual_spent=890000.0),
                HealthcareCostCenter(tenant_id=tenant.id, code="CC-LAB", name="مركز تكلفة المعامل وبنك الدم", center_type="laboratory", budget=1200000.0, actual_spent=360000.0),
            ]
            session.add_all(supplies)
            session.add_all(cost_centers)
            await session.commit()
            print("  ✅ [HLT-17/18] Seeded medical inventory & cost centers.")

        # 18. HLT-19 & HLT-20: Clinical Credentials & Biomedical Equipment
        res_cred = await session.execute(select(ClinicalCredentialRecord).where(ClinicalCredentialRecord.tenant_id == tenant.id))
        if not res_cred.scalars().first():
            credentials = [
                ClinicalCredentialRecord(tenant_id=tenant.id, staff_id=doc1.id, credential_title="استشاري أمراض باطنة وسكري", issuing_authority="نقابة أطباء مصر", expiry_date=date(2028, 12, 31), status="active"),
                ClinicalCredentialRecord(tenant_id=tenant.id, staff_id=doc2.id, credential_title="استشاري أمراض قلب وتداخلات", issuing_authority="نقابة أطباء مصر", expiry_date=date(2027, 6, 30), status="active"),
                ClinicalCredentialRecord(tenant_id=tenant.id, staff_id=doc3.id, credential_title="أخصائي أول جراحة عامة ومناظير", issuing_authority="وزارة الصحة المصرية", expiry_date=date(2029, 3, 15), status="active"),
            ]
            devices = [
                BiomedicalDevice(tenant_id=tenant.id, asset_tag="DRG-2024-8841", device_name="جهاز تنفس صناعي متقدم (Dräger Evita V800)", serial_number="SN-EV800-4819", department_name="جناح العناية المركزة ICU", last_calibration_date=date(2026, 1, 15), next_calibration_due=date(2026, 7, 15), status="operational"),
                BiomedicalDevice(tenant_id=tenant.id, asset_tag="ZOL-2023-1092", device_name="جهاز صدمات قلبية مزيل للرجفان (Zoll R Series)", serial_number="SN-ZOLL-9921", department_name="قسم الطوارئ ER", last_calibration_date=date(2026, 2, 1), next_calibration_due=date(2026, 8, 1), status="operational"),
                BiomedicalDevice(tenant_id=tenant.id, asset_tag="PHL-2025-9921", device_name="شاشة مراقبة علامات حيوية للمريض (Philips IntelliVue MX750)", serial_number="SN-MX750-1049", department_name="سرير العناية ICU-01", last_calibration_date=date(2026, 3, 10), next_calibration_due=date(2026, 9, 10), status="operational"),
            ]
            session.add_all(credentials)
            session.add_all(devices)
            await session.commit()
            print("  ✅ [HLT-19/20] Seeded clinical credentials & biomedical equipment.")

        # 19. HLT-21 & HLT-22: Patient Portal & Telemedicine
        res_portal = await session.execute(select(PatientPortalRequest).where(PatientPortalRequest.tenant_id == tenant.id))
        if not res_portal.scalars().first():
            requests = [
                PatientPortalRequest(tenant_id=tenant.id, patient_id=p1.id, request_type="medical_report", details="طلب تقرير طبي معتمد موجه لجهة العمل عن المتابعة الأخيرة ونسبة السكر التراكمي", status="pending"),
                PatientPortalRequest(tenant_id=tenant.id, patient_id=p2.id, request_type="appointment_change", details="تعديل موعد استشارة القلب وتأخيره إلى يوم الأحد القادم", status="pending"),
            ]
            telemed = [
                TeleconsultationSession(tenant_id=tenant.id, session_id="TELE-2026-001", patient_id=p1.id, doctor_id=doc1.id, scheduled_at=datetime.utcnow() + timedelta(days=2, hours=4), meeting_link="https://meet.mizan.local/telemed/fatima-hesham-901", status="scheduled"),
                TeleconsultationSession(tenant_id=tenant.id, session_id="TELE-2026-002", patient_id=p2.id, doctor_id=doc2.id, scheduled_at=datetime.utcnow() + timedelta(days=4, hours=2), meeting_link="https://meet.mizan.local/telemed/tarek-mona-902", status="scheduled"),
            ]
            session.add_all(requests)
            session.add_all(telemed)
            await session.commit()
            print("  ✅ [HLT-21/22] Seeded portal requests & telemedicine sessions.")

        # 20. HLT-23 & HLT-24: Clinical Alerts & Analytics Daily KPIs
        res_alerts = await session.execute(select(HealthcareAlert).where(HealthcareAlert.tenant_id == tenant.id))
        if not res_alerts.scalars().first():
            alerts = [
                HealthcareAlert(tenant_id=tenant.id, patient_id=existing_patients[4].id, alert_type="critical_lab", title="إنزيم تروبونين عالي الحرج", message="إنزيم تروبونين مرتفع بشكل حرج (hs-cTnI = 0.85 ng/mL) لمريض العناية محمود صبري", priority="critical", is_read=False),
                HealthcareAlert(tenant_id=tenant.id, patient_id=p1.id, alert_type="allergy_conflict", title="تحذير دوائي سريري", message="تحذير دوائي: المريضة لديها حساسية شديدة من البنسلين مانعة للصرف التلقائي", priority="high", is_read=False),
                HealthcareAlert(tenant_id=tenant.id, patient_id=existing_patients[4].id, alert_type="vitals_abnormal", title="انخفاض تشبع الأكسجين", message="انخفاض تشبع الأكسجين SpO2 إلى 91% في قسم الطوارئ", priority="high", is_read=True),
            ]
            session.add_all(alerts)
            
            today = date.today()
            metrics = [
                HealthcareDailyMetric(tenant_id=tenant.id, metric_date=today - timedelta(days=6), total_visits=118, admissions_count=18, discharges_count=14, bed_occupancy_rate=65.0, average_wait_minutes=18),
                HealthcareDailyMetric(tenant_id=tenant.id, metric_date=today - timedelta(days=5), total_visits=134, admissions_count=22, discharges_count=17, bed_occupancy_rate=72.5, average_wait_minutes=22),
                HealthcareDailyMetric(tenant_id=tenant.id, metric_date=today - timedelta(days=4), total_visits=142, admissions_count=25, discharges_count=20, bed_occupancy_rate=80.0, average_wait_minutes=25),
                HealthcareDailyMetric(tenant_id=tenant.id, metric_date=today - timedelta(days=3), total_visits=128, admissions_count=19, discharges_count=16, bed_occupancy_rate=75.0, average_wait_minutes=20),
                HealthcareDailyMetric(tenant_id=tenant.id, metric_date=today - timedelta(days=2), total_visits=155, admissions_count=28, discharges_count=21, bed_occupancy_rate=85.0, average_wait_minutes=24),
                HealthcareDailyMetric(tenant_id=tenant.id, metric_date=today - timedelta(days=1), total_visits=149, admissions_count=24, discharges_count=19, bed_occupancy_rate=82.5, average_wait_minutes=21),
                HealthcareDailyMetric(tenant_id=tenant.id, metric_date=today, total_visits=162, admissions_count=31, discharges_count=22, bed_occupancy_rate=87.5, average_wait_minutes=19),
            ]
            session.add_all(metrics)
            await session.commit()
            print("  ✅ [HLT-23/24] Seeded clinical alerts & 7-day executive BI metrics.")

        print(f"\n🎉 Successfully seeded complete realistic clinical data across all 24 Healthcare ERP modules for tenant '{tenant.slug}'!")

if __name__ == "__main__":
    asyncio.run(seed_healthcare())
