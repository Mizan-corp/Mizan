"""
migrate.py — Safe incremental DB migrations.
Run after deploy on existing databases to apply new columns/tables.
Each migration is idempotent (safe to run multiple times).
"""
import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "shared" / "backend"))

from app.db.migrations import MIGRATIONS, split_statements

def _resolve_compose():
    for cmd in [
        ["docker", "compose", "-f", str(ROOT / "docker-compose.yml")],
        ["docker", "compose", "-p", "vendora", "-f", str(ROOT / "docker-compose.yml")],
        ["docker", "compose", "-p", "mizan", "-f", str(ROOT / "docker-compose.yml")],
    ]:
        res = subprocess.run(cmd + ["ps", "-q", "db"], capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            return cmd
    return ["docker", "compose", "-p", "vendora", "-f", str(ROOT / "docker-compose.yml")]

COMPOSE = _resolve_compose()

def psql(sql: str):
    """Execute a migration statement-by-statement so one failure never
    silently aborts the rest of the migration (single-transaction psql -c
    did exactly that). Every statement runs with app.bypass=on and the
    primary tenant bound — pre-tenancy migration INSERTs into scoped
    tables resolve their tenant_id column default correctly."""
    ok = True
    for stmt in split_statements(sql):
        result = subprocess.run(
            COMPOSE + ["exec", "-T", "db", "psql", "-U", "postgres", "-d", "inventory_db"],
            input=("SELECT set_config('app.tenant_id', COALESCE((SELECT id::text FROM tenants ORDER BY created_at LIMIT 1), ''), false), set_config('app.bypass', 'on', false);\n"
                   + stmt + ";"), capture_output=True, text=True
        )
        errors = [l for l in result.stderr.splitlines() if "ERROR" in l and "already exists" not in l and "does not exist" not in l]
        if errors or result.returncode != 0:
            ok = False
            print(f"    ⚠️  {errors[0] if errors else result.returncode}: {stmt[:90]}")
    return ok

def ensure_foundation():
    foundation = """
        CREATE TABLE IF NOT EXISTS tenants (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            name text NOT NULL,
            sector text NOT NULL DEFAULT 'plumbing',
            scale text NOT NULL DEFAULT 'medium',
            palette jsonb NOT NULL DEFAULT '{}'::jsonb,
            features jsonb NOT NULL DEFAULT '[]'::jsonb,
            plan text NOT NULL DEFAULT 'trial',
            trial_ends_at timestamptz,
            storefront_slug text UNIQUE,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        DO $fn$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='tenants' AND column_name='status') THEN
                ALTER TABLE tenants ALTER COLUMN status SET DEFAULT 'active';
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='tenants' AND column_name='deployment_mode') THEN
                ALTER TABLE tenants ALTER COLUMN deployment_mode SET DEFAULT 'cloud_saas';
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='tenants' AND column_name='business_type') THEN
                ALTER TABLE tenants ALTER COLUMN business_type SET DEFAULT 'retail';
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='tenants' AND column_name='tech_stack') THEN
                ALTER TABLE tenants ALTER COLUMN tech_stack SET DEFAULT '{}'::jsonb;
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='tenants' AND column_name='active_modules') THEN
                ALTER TABLE tenants ALTER COLUMN active_modules SET DEFAULT '[]'::jsonb;
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='tenants' AND column_name='limits') THEN
                ALTER TABLE tenants ALTER COLUMN limits SET DEFAULT '{}'::jsonb;
            END IF;
        END
        $fn$;
        INSERT INTO tenants (id, name, sector, scale, palette, features, plan)
        SELECT gen_random_uuid(), 'المصرية الألمانية للأدوات الصحية', 'plumbing', 'large', '{}'::jsonb, '[]'::jsonb, 'enterprise'
        WHERE NOT EXISTS (SELECT 1 FROM tenants);
        DO $fn$
        BEGIN
            IF to_regclass('public.accounting_periods') IS NOT NULL THEN ALTER TABLE accounting_periods ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.archived_documents') IS NOT NULL THEN ALTER TABLE archived_documents ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.audit_log') IS NOT NULL THEN ALTER TABLE audit_log ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.categories') IS NOT NULL THEN ALTER TABLE categories ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.collection_items') IS NOT NULL THEN ALTER TABLE collection_items ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.customer_payments') IS NOT NULL THEN ALTER TABLE customer_payments ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.customers') IS NOT NULL THEN ALTER TABLE customers ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.device_tokens') IS NOT NULL THEN ALTER TABLE device_tokens ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.drawer_transactions') IS NOT NULL THEN ALTER TABLE drawer_transactions ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.employees') IS NOT NULL THEN ALTER TABLE employees ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.expense_vendors') IS NOT NULL THEN ALTER TABLE expense_vendors ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.expenses') IS NOT NULL THEN ALTER TABLE expenses ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.financial_categories') IS NOT NULL THEN ALTER TABLE financial_categories ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.hr_advances') IS NOT NULL THEN ALTER TABLE hr_advances ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.hr_attendance') IS NOT NULL THEN ALTER TABLE hr_attendance ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.hr_audit_log') IS NOT NULL THEN ALTER TABLE hr_audit_log ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.hr_employees') IS NOT NULL THEN ALTER TABLE hr_employees ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.hr_payroll') IS NOT NULL THEN ALTER TABLE hr_payroll ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.hr_payroll_entries') IS NOT NULL THEN ALTER TABLE hr_payroll_entries ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.hr_payroll_periods') IS NOT NULL THEN ALTER TABLE hr_payroll_periods ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.hr_settings') IS NOT NULL THEN ALTER TABLE hr_settings ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.hr_shifts') IS NOT NULL THEN ALTER TABLE hr_shifts ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.hr_sync_log') IS NOT NULL THEN ALTER TABLE hr_sync_log ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.payment_wallets') IS NOT NULL THEN ALTER TABLE payment_wallets ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.payroll_entries') IS NOT NULL THEN ALTER TABLE payroll_entries ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.product_barcodes') IS NOT NULL THEN ALTER TABLE product_barcodes ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.product_collections') IS NOT NULL THEN ALTER TABLE product_collections ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.product_images') IS NOT NULL THEN ALTER TABLE product_images ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.products') IS NOT NULL THEN ALTER TABLE products ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.purchase_order_items') IS NOT NULL THEN ALTER TABLE purchase_order_items ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.purchase_orders') IS NOT NULL THEN ALTER TABLE purchase_orders ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.purchase_price_history') IS NOT NULL THEN ALTER TABLE purchase_price_history ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.safe_deposits') IS NOT NULL THEN ALTER TABLE safe_deposits ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.safe_transactions') IS NOT NULL THEN ALTER TABLE safe_transactions ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.safes') IS NOT NULL THEN ALTER TABLE safes ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.sale_items') IS NOT NULL THEN ALTER TABLE sale_items ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.sale_payments') IS NOT NULL THEN ALTER TABLE sale_payments ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.sales') IS NOT NULL THEN ALTER TABLE sales ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.shifts') IS NOT NULL THEN ALTER TABLE shifts ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.stock_balances') IS NOT NULL THEN ALTER TABLE stock_balances ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.stock_movements') IS NOT NULL THEN ALTER TABLE stock_movements ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.store_settings') IS NOT NULL THEN ALTER TABLE store_settings ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.subcategories') IS NOT NULL THEN ALTER TABLE subcategories ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.supplier_prices') IS NOT NULL THEN ALTER TABLE supplier_prices ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.supplier_transactions') IS NOT NULL THEN ALTER TABLE supplier_transactions ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.suppliers') IS NOT NULL THEN ALTER TABLE suppliers ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.users') IS NOT NULL THEN ALTER TABLE users ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.wallet_transactions') IS NOT NULL THEN ALTER TABLE wallet_transactions ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.warehouse_product_status') IS NOT NULL THEN ALTER TABLE warehouse_product_status ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
            IF to_regclass('public.warehouses') IS NOT NULL THEN ALTER TABLE warehouses ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid; END IF;
        END
        $fn$;
    """
    psql(foundation)

def run():
    print("🔄 Running DB migrations...")
    ensure_foundation()
    ok = 0
    for name, sql in MIGRATIONS:
        # Check if already applied
        check = subprocess.run(
            COMPOSE + ["exec", "-T", "db", "psql", "-U", "postgres", "-d", "inventory_db", "-t", "-c",
                       f"SELECT 1 FROM schema_migrations WHERE id='{name}'"],
            capture_output=True, text=True
        )
        if check.returncode == 0 and check.stdout.strip():
            print(f"  ⏭️  {name} (already applied)")
            ok += 1
            continue
        result = psql(sql)
        status = "✅" if result else "⚠️ "
        print(f"  {status} {name}")
        if result:
            ok += 1
            # Record as applied
            subprocess.run(
                COMPOSE + ["exec", "-T", "db", "psql", "-U", "postgres", "-d", "inventory_db", "-c",
                           f"INSERT INTO schema_migrations (id) VALUES ('{name}') ON CONFLICT DO NOTHING"],
                capture_output=True, text=True
            )
    print(f"\n{'✅' if ok == len(MIGRATIONS) else '❌'} Done — {ok}/{len(MIGRATIONS)} migrations applied.")
    if ok < len(MIGRATIONS):
        print("Some migrations failed — check that the compose stack is running.")
        sys.exit(1)

if __name__ == "__main__":
    run()
