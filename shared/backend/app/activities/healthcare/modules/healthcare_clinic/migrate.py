"""Migration v79b (#113): existing clinics keep access to their patients.

Records whose doctor_name is exactly the full name of one active user of the same workspace are
linked to that user (doctor_user_id), and the user joins the patient's care team. Names shared by
two users are left alone. Idempotent: linked records and existing memberships are skipped.
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

CLINICAL_TABLES = ("clinic_appointments", "clinic_encounters", "clinic_prescriptions", "clinic_lab_orders")


async def backfill_care_team(db: AsyncSession) -> None:
    for table in CLINICAL_TABLES:
        await db.execute(text(f"""
            UPDATE {table} r SET doctor_user_id = u.id
            FROM users u
            WHERE r.doctor_user_id IS NULL AND u.tenant_id = r.tenant_id AND u.is_active
              AND u.full_name = r.doctor_name
              AND (SELECT count(*) FROM users o WHERE o.tenant_id = r.tenant_id AND o.is_active AND o.full_name = r.doctor_name) = 1
        """))
    linked = " UNION ".join(
        f"SELECT tenant_id, patient_id, doctor_user_id FROM {t} WHERE doctor_user_id IS NOT NULL" for t in CLINICAL_TABLES
    )
    await db.execute(text(f"""
        INSERT INTO clinic_care_team (id, tenant_id, patient_id, user_id, role, created_at)
        SELECT gen_random_uuid()::text, s.tenant_id, s.patient_id, s.doctor_user_id, 'attending', now()
        FROM ({linked}) s
        WHERE NOT EXISTS (
            SELECT 1 FROM clinic_care_team c
            WHERE c.patient_id = s.patient_id AND c.user_id = s.doctor_user_id AND c.ended_at IS NULL
        )
    """))
