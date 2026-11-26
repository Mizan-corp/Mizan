"""Healthcare clinic: demo patients, appointments, records, beds, invoices and claims for a new
clinic workspace (also offered by POST /clinic/seed). Does nothing if the clinic has patients."""
from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.activities.healthcare.modules.healthcare_clinic.models import ClinicAppointment, ClinicInpatientBed, ClinicInsuranceClaim, ClinicInvoice, ClinicPatient


async def seed_clinic_records(db: AsyncSession, tenant_id: str) -> bool:
    q_patients = await db.execute(select(ClinicPatient).where(ClinicPatient.tenant_id == tenant_id))
    if q_patients.scalars().first():
        return False

    p1 = ClinicPatient(
        tenant_id=tenant_id,
        patient_mrn="MRN-2026-0811",
        full_name="فاطمة الزهراء علي",
        national_id="29408110104821",
        phone="0501234567",
        gender="أنثى",
        date_of_birth="1994-08-11",
        blood_group="O+",
        allergies="بنسلين (Penicillin)",
        chronic_conditions="ربو تحسسي خفيف",
        insurance_provider="بوبا العربية للتأمين",
        insurance_policy_no="BUPA-992144",
        copay_percent=20.0,
        created_by="مدير النظام",
    )
    p2 = ClinicPatient(
        tenant_id=tenant_id,
        patient_mrn="MRN-2026-0812",
        full_name="عمر خالد القحطاني",
        national_id="28803150201944",
        phone="0559876543",
        gender="ذكر",
        date_of_birth="1988-03-15",
        blood_group="A+",
        allergies="لا توجد حساسيات مسجلة",
        chronic_conditions="ارتفاع ضغط دم أولي",
        insurance_provider="التعاونية للتأمين",
        insurance_policy_no="TAW-441092",
        copay_percent=10.0,
        created_by="مدير النظام",
    )
    p3 = ClinicPatient(
        tenant_id=tenant_id,
        patient_mrn="MRN-2026-0813",
        full_name="سارة عبد الله الشمري",
        national_id="29911040305512",
        phone="0543322110",
        gender="أنثى",
        date_of_birth="1999-11-04",
        blood_group="B+",
        allergies="لا توجد حساسيات مسجلة",
        chronic_conditions="قصور الغدة الدرقية",
        insurance_provider="ميدغلف للتأمين",
        insurance_policy_no="MED-881903",
        copay_percent=15.0,
        created_by="مدير النظام",
    )
    p4 = ClinicPatient(
        tenant_id=tenant_id,
        patient_mrn="MRN-2026-0814",
        full_name="طارق عبد الحميد محمود",
        national_id="27506200109931",
        phone="0567788990",
        gender="ذكر",
        date_of_birth="1975-06-20",
        blood_group="AB+",
        allergies="أسبرين (Aspirin / NSAIDs)",
        chronic_conditions="داء السكري النوع الثاني، قصور شرياني تاجي",
        insurance_provider="نقدي / غير مؤمن",
        insurance_policy_no="N/A",
        copay_percent=0.0,
        created_by="مدير النظام",
    )
    db.add_all([p1, p2, p3, p4])
    await db.flush()

    today_str = date.today().isoformat()

    a1 = ClinicAppointment(
        tenant_id=tenant_id,
        appointment_ref="APT-2026-101",
        patient_id=p1.id,
        patient_name=p1.full_name,
        doctor_name="د. هشام الشناوي",
        department="الباطنة العامة",
        appointment_date=today_str,
        time_slot="09:30 AM",
        queue_number=1,
        status="completed",
        consultation_fee=250.0,
        chief_complaint="متابعة دورية للفحوصات وضيق تنفس خفيف",
        created_by="مدير النظام",
    )
    a2 = ClinicAppointment(
        tenant_id=tenant_id,
        appointment_ref="APT-2026-102",
        patient_id=p2.id,
        patient_name=p2.full_name,
        doctor_name="د. أحمد نبيل",
        department="أمراض القلب والأوعية",
        appointment_date=today_str,
        time_slot="10:00 AM",
        queue_number=2,
        status="in_consultation",
        consultation_fee=350.0,
        chief_complaint="صداع صباحي مستمر مع خفقان",
        created_by="مدير النظام",
    )
    a3 = ClinicAppointment(
        tenant_id=tenant_id,
        appointment_ref="APT-2026-103",
        patient_id=p3.id,
        patient_name=p3.full_name,
        doctor_name="د. منى عبد الرحمن",
        department="الغدد الصماء والسكري",
        appointment_date=today_str,
        time_slot="10:30 AM",
        queue_number=3,
        status="waiting",
        consultation_fee=300.0,
        chief_complaint="إجهاد عام وطلب تعديل جرعة الثيروكسين",
        created_by="مدير النظام",
    )
    db.add_all([a1, a2, a3])
    await db.flush()

    # Bed records
    b1 = ClinicInpatientBed(
        tenant_id=tenant_id,
        bed_code="BED-ICU-01",
        ward_name="العناية المركزة (ICU)",
        room_number="غرفة 101",
        bed_type="عناية حثيثة متقدمة",
        daily_rate=2800.0,
        status="occupied",
        current_patient_id=p4.id,
        current_patient_name=p4.full_name,
        admission_date="2026-11-04",
        created_by="مدير النظام",
    )
    b2 = ClinicInpatientBed(
        tenant_id=tenant_id,
        bed_code="BED-ICU-02",
        ward_name="العناية المركزة (ICU)",
        room_number="غرفة 102",
        bed_type="عناية حثيثة متقدمة",
        daily_rate=2800.0,
        status="available",
        current_patient_id=None,
        current_patient_name="",
        admission_date="",
        created_by="مدير النظام",
    )
    b3 = ClinicInpatientBed(
        tenant_id=tenant_id,
        bed_code="BED-SURG-201",
        ward_name="جناح الجراحة العامة",
        room_number="غرفة 201",
        bed_type="سرير استشفاء جراحي",
        daily_rate=1400.0,
        status="available",
        current_patient_id=None,
        current_patient_name="",
        admission_date="",
        created_by="مدير النظام",
    )
    db.add_all([b1, b2, b3])

    # Sample Invoice & Claim
    inv1 = ClinicInvoice(
        tenant_id=tenant_id,
        invoice_ref="INV-2026-001",
        patient_id=p1.id,
        patient_name=p1.full_name,
        appointment_id=a1.id,
        charges=[{"description": "رسوم كشف واستشارة — د. هشام الشناوي (الباطنة العامة)", "amount": 250.0}],
        total=250.0,
        copay_percent=20.0,
        insurance_amount=50.0,
        patient_amount=200.0,
        paid_amount=200.0,
        status="paid",
        payment_method="card",
        created_by="مدير النظام",
        paid_by="مدير النظام",
    )
    db.add(inv1)
    await db.flush()

    clm1 = ClinicInsuranceClaim(
        tenant_id=tenant_id,
        claim_ref="CLM-2026-001",
        patient_id=p1.id,
        patient_name=p1.full_name,
        invoice_id=inv1.id,
        insurance_provider=p1.insurance_provider,
        policy_no=p1.insurance_policy_no,
        copay_percent=20.0,
        claimed_amount=50.0,
        approved_amount=50.0,
        status="approved",
        created_by="مدير النظام",
        notes="تمت الموافقة والمطابقة الإلكترونية",
    )
    db.add(clm1)

    await db.commit()
    return True
