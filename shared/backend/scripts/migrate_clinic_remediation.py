"""Migration script for clinic remediation schema updates."""
import asyncio
from app.db.base import AsyncSessionLocal
from sqlalchemy import text


async def run_migration():
    async with AsyncSessionLocal() as s:
        print("Running clinic remediation schema migration...")

        statements = [
            # 1. clinic_patients
            """
            ALTER TABLE clinic_patients
            ADD COLUMN IF NOT EXISTS created_by character varying(128),
            ADD COLUMN IF NOT EXISTS updated_by character varying(128),
            ADD COLUMN IF NOT EXISTS updated_at timestamp with time zone DEFAULT now();
            """,

            # 2. clinic_appointments
            """
            ALTER TABLE clinic_appointments
            ADD COLUMN IF NOT EXISTS cancellation_reason character varying(256),
            ADD COLUMN IF NOT EXISTS rescheduled_from character varying(64),
            ADD COLUMN IF NOT EXISTS reschedule_count integer DEFAULT 0,
            ADD COLUMN IF NOT EXISTS created_by character varying(128),
            ADD COLUMN IF NOT EXISTS updated_by character varying(128),
            ADD COLUMN IF NOT EXISTS updated_at timestamp with time zone DEFAULT now();
            """,

            # 3. clinic_encounters
            """
            ALTER TABLE clinic_encounters
            ADD COLUMN IF NOT EXISTS created_by character varying(128),
            ADD COLUMN IF NOT EXISTS updated_by character varying(128),
            ADD COLUMN IF NOT EXISTS updated_at timestamp with time zone DEFAULT now();
            """,

            # 4. clinic_prescriptions
            """
            ALTER TABLE clinic_prescriptions
            ADD COLUMN IF NOT EXISTS quantity integer DEFAULT 1,
            ADD COLUMN IF NOT EXISTS dispensed_at timestamp with time zone,
            ADD COLUMN IF NOT EXISTS dispensed_by character varying(128),
            ADD COLUMN IF NOT EXISTS created_by character varying(128),
            ADD COLUMN IF NOT EXISTS updated_by character varying(128),
            ADD COLUMN IF NOT EXISTS updated_at timestamp with time zone DEFAULT now();
            """,

            # 5. clinic_lab_orders
            """
            ALTER TABLE clinic_lab_orders
            ADD COLUMN IF NOT EXISTS numeric_value double precision,
            ADD COLUMN IF NOT EXISTS unit character varying(32) DEFAULT '',
            ADD COLUMN IF NOT EXISTS is_critical boolean DEFAULT false,
            ADD COLUMN IF NOT EXISTS collected_at timestamp with time zone,
            ADD COLUMN IF NOT EXISTS signed_off_by character varying(128),
            ADD COLUMN IF NOT EXISTS signed_off_at timestamp with time zone,
            ADD COLUMN IF NOT EXISTS test_fee double precision DEFAULT 150.0,
            ADD COLUMN IF NOT EXISTS created_by character varying(128),
            ADD COLUMN IF NOT EXISTS updated_by character varying(128),
            ADD COLUMN IF NOT EXISTS updated_at timestamp with time zone DEFAULT now();
            """,

            # 6. clinic_inpatient_beds
            """
            ALTER TABLE clinic_inpatient_beds
            ADD COLUMN IF NOT EXISTS current_patient_id character varying(36),
            ADD COLUMN IF NOT EXISTS created_by character varying(128),
            ADD COLUMN IF NOT EXISTS updated_by character varying(128),
            ADD COLUMN IF NOT EXISTS updated_at timestamp with time zone DEFAULT now();
            """,

            # 7. clinic_invoices
            """
            ALTER TABLE clinic_invoices
            ADD COLUMN IF NOT EXISTS created_by character varying(128),
            ADD COLUMN IF NOT EXISTS paid_by character varying(128);
            """,

            # 8. clinic_insurance_claims
            """
            ALTER TABLE clinic_insurance_claims
            ADD COLUMN IF NOT EXISTS created_by character varying(128);
            """
        ]

        for stmt in statements:
            await s.execute(text(stmt))

        # Foreign key constraint for current_patient_id if not present
        try:
            await s.execute(text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = 'fk_clinic_beds_patient_id'
                    ) THEN
                        ALTER TABLE clinic_inpatient_beds
                        ADD CONSTRAINT fk_clinic_beds_patient_id
                        FOREIGN KEY (current_patient_id) REFERENCES clinic_patients(id) ON DELETE SET NULL;
                    END IF;
                END $$;
            """))
        except Exception as e:
            print("FK notice:", e)

        # Pharmacy drug uniqueness
        try:
            await s.execute(text("DROP INDEX IF EXISTS ix_pharmacy_drugs_code CASCADE;"))
            await s.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_pharmacy_drugs_tenant_code 
                ON pharmacy_drugs (tenant_id, code);
            """))
            await s.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_pharmacy_drugs_code 
                ON pharmacy_drugs (code);
            """))
        except Exception as e:
            print("Pharmacy index notice:", e)

        await s.commit()
        print("Schema migration completed successfully!")


if __name__ == "__main__":
    asyncio.run(run_migration())
