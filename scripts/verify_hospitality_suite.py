"""Verification script for Hospitality standalone modules."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5433/inventory_db")
os.environ.setdefault("SECRET_KEY", "dummysecret")

from app.modules.loader import registry
import main

manifests = registry.discover_modules()
routers = registry.get_routers()

expected_submodules = [
    "hot_pms",
    "hot_housekeeping",
    "hot_billing_folio",
    "hot_night_audit",
    "hot_banquet_events",
]

print("🏨 Verifying Hospitality Standalone Modules:")
all_ok = True
for mod_id in expected_submodules:
    man = manifests.get(mod_id)
    r = routers.get(mod_id)
    if man and r:
        print(f"  ✅ {mod_id}: {man.name} ({man.name_en}) | Router mounted")
    else:
        print(f"  ❌ {mod_id}: Manifest={bool(man)}, Router={bool(r)}")
        all_ok = False

# Check routes in main.app
app_routes = [route.path for route in main.app.routes]
expected_routes = [
    "/hospitality/pms",
    "/hospitality/housekeeping",
    "/hospitality/billing",
    "/hospitality/night-audit",
    "/hospitality/banquet",
]
print("\n🛣️  Verifying Route Prefixes in FastAPI App:")
for pfx in expected_routes:
    found = any(r.startswith(pfx) for r in app_routes)
    if found:
        print(f"  ✅ Mounted route prefix: {pfx}")
    else:
        print(f"  ❌ Missing route prefix: {pfx}")
        all_ok = False

if all_ok:
    print("\n🎉 All Hospitality Standalone Modules & Routes are verified and mounted successfully!")
else:
    print("\n⚠️ Verification failed for some modules.")
    sys.exit(1)
