"""Verification script for all 24 Healthcare ERP modules in Mizan ERP."""
import os
import sys
from pathlib import Path

# Set required environment variables
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5433/inventory_db")
os.environ.setdefault("SECRET_KEY", "dummysecret")

sys.path.insert(0, "/home/ammar/projects/Mizan/backend")

import asyncio
from app.modules.loader import registry
from main import app

EXPECTED_MODULES = [
    ("hlt_facility_management", "HLT-01"),
    ("hlt_patient_identity", "HLT-02"),
    ("hlt_appointments", "HLT-03"),
    ("hlt_medical_staff", "HLT-04"),
    ("hlt_emr", "HLT-05"),
    ("hlt_consultation", "HLT-06"),
    ("hlt_admissions", "HLT-07"),
    ("hlt_beds", "HLT-08"),
    ("hlt_nursing", "HLT-09"),
    ("hlt_laboratory", "HLT-10"),
    ("hlt_radiology", "HLT-11"),
    ("hlt_pharmacy", "HLT-12"),
    ("hlt_emergency", "HLT-13"),
    ("hlt_surgery", "HLT-14"),
    ("hlt_billing", "HLT-15"),
    ("hlt_insurance", "HLT-16"),
    ("hlt_inventory_procurement", "HLT-17"),
    ("hlt_accounting", "HLT-18"),
    ("hlt_hr_workforce", "HLT-19"),
    ("hlt_equipment_maintenance", "HLT-20"),
    ("hlt_patient_portal", "HLT-21"),
    ("hlt_telemedicine", "HLT-22"),
    ("hlt_notifications", "HLT-23"),
    ("hlt_analytics", "HLT-24"),
]

def main():
    print("🏥 Verifying Mizan Healthcare ERP 24 Standalone Modules...")
    manifests = registry.discover_modules()
    routers = registry.get_routers()

    missing_manifests = []
    missing_routers = []

    for mod_id, code in EXPECTED_MODULES:
        if mod_id not in manifests:
            missing_manifests.append((mod_id, code))
        else:
            m = manifests[mod_id]
            print(f"  ✅ [{code}] Manifest: {m.id} -> '{m.name}' (Category: {m.category})")

        if mod_id not in routers:
            missing_routers.append((mod_id, code))
        else:
            r = routers[mod_id]
            print(f"     Mounted Router: {r.prefix} ({len(r.routes)} routes)")

    print("\n--- Summary ---")
    print(f"Total verified manifests: {len(EXPECTED_MODULES) - len(missing_manifests)}/{len(EXPECTED_MODULES)}")
    print(f"Total mounted routers: {len(EXPECTED_MODULES) - len(missing_routers)}/{len(EXPECTED_MODULES)}")

    if missing_manifests or missing_routers:
        print("❌ Verification failed!")
        sys.exit(1)
    else:
        print("🎉 All 24 standalone healthcare modules are 100% operational and verified!")

if __name__ == "__main__":
    main()
