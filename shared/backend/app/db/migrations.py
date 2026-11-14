"""Mizan ERP Database Migrations and Schema Definition Suite.

Contains all tracked migrations (v0 through v41) and the idempotent async
migration execution engine for both cloud serverless (Vercel/Neon) and self-hosted environments.
"""
import logging
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent / "sql"
from typing import List
try:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession
except ImportError:
    text = None
    AsyncSession = None

logger = logging.getLogger("mizan.migrations")

def split_statements(sql: str):
    """Split on top-level semicolons, respecting dollar-quoted blocks
    ($$...$$ and $tag$...$tag$)."""
    import re as _re
    stmts, buf = [], []
    dollar_tag = None
    i = 0
    while i < len(sql):
        m = _re.match(r"\$[A-Za-z_]*\$", sql[i:])
        if m:
            tag = m.group(0)
            if dollar_tag is None:
                dollar_tag = tag
            elif tag == dollar_tag:
                dollar_tag = None
            buf.append(tag)
            i += len(tag)
            continue
        ch = sql[i]
        if ch == ";" and dollar_tag is None:
            stmt = "".join(buf).strip()
            if stmt:
                stmts.append(stmt)
            buf = []
        else:
            buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        stmts.append(tail)
    return stmts



# Runs before every migration pass (`python manage.py db migrate`): the tenants
# table, its column defaults, a default workspace on an empty database, and the
# tenant_id column defaults that read the app.tenant_id GUC. Idempotent.
FOUNDATION_SQL = """
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
        SELECT gen_random_uuid(), 'ميزان', 'retail', 'small', '{}'::jsonb, '[]'::jsonb, 'enterprise'
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


MIGRATIONS = [
    # v0 — migration tracking table
    ("v0_schema_migrations", """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id text PRIMARY KEY,
            applied_at timestamptz DEFAULT now()
        );
    """),

    # v1.1 — accounting_periods: add id column and make it PK (live DB has month as PK)
    ("v1.1_accounting_periods_pk", """
        ALTER TABLE accounting_periods ADD COLUMN IF NOT EXISTS id uuid;
        UPDATE accounting_periods SET id = gen_random_uuid() WHERE id IS NULL;
        ALTER TABLE accounting_periods ALTER COLUMN id SET NOT NULL;
        ALTER TABLE accounting_periods DROP CONSTRAINT IF EXISTS accounting_periods_pkey;
        ALTER TABLE accounting_periods ADD PRIMARY KEY (id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_accounting_periods_month ON accounting_periods(month);
    """),

    # v1 — stock_status on products
    ("v1_stock_status", """
        ALTER TABLE products ADD COLUMN IF NOT EXISTS stock_status text NOT NULL DEFAULT 'tracked';
    """),

    # v2 — safe_transactions table
    ("v2_safe_transactions", """
        CREATE TABLE IF NOT EXISTS safe_transactions (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          safe_id uuid NOT NULL REFERENCES safes(id),
          tx_type text NOT NULL CHECK (tx_type IN ('deposit','withdraw')),
          amount numeric(14,2) NOT NULL,
          balance_after numeric(14,2) NOT NULL,
          note text,
          created_by uuid,
          created_at timestamptz DEFAULT now()
        );
    """),

    # v3 — safe_type on safes
    ("v3_safe_type", """
        ALTER TABLE safes ADD COLUMN IF NOT EXISTS safe_type text NOT NULL DEFAULT 'permanent';
    """),

    # v4 — product_collections
    ("v4_collections", """
        CREATE TABLE IF NOT EXISTS product_collections (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          name text NOT NULL,
          description text,
          retail_price numeric(12,2) DEFAULT 0,
          wholesale_price numeric(12,2) DEFAULT 0,
          is_active boolean DEFAULT true,
          created_at timestamptz DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS collection_items (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          collection_id uuid NOT NULL REFERENCES product_collections(id) ON DELETE CASCADE,
          product_id uuid NOT NULL REFERENCES products(id),
          qty numeric(12,3) NOT NULL DEFAULT 1
        );
        CREATE INDEX IF NOT EXISTS idx_collection_items_collection ON collection_items(collection_id);
    """),

    # v5 — paper_size setting
    ("v5_paper_size", """
        INSERT INTO store_settings (key, value) VALUES ('paper_size', '"A4"') ON CONFLICT DO NOTHING;
    """),

    # v7 — wallet_transactions audit table
    ("v7_wallet_transactions", """
        CREATE TABLE IF NOT EXISTS wallet_transactions (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          wallet_id uuid NOT NULL REFERENCES payment_wallets(id),
          amount numeric(14,2) NOT NULL,
          tx_type text NOT NULL,
          ref_id uuid,
          note text,
          created_by uuid,
          created_at timestamptz DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_wallet_tx_wallet ON wallet_transactions(wallet_id);
    """),

    # v6 — wallet_id on sales
    ("v6_wallet_id_sales", """
        ALTER TABLE sales ADD COLUMN IF NOT EXISTS wallet_id uuid REFERENCES payment_wallets(id) ON DELETE SET NULL;
        ALTER TABLE sales ADD COLUMN IF NOT EXISTS payment_method text DEFAULT 'cash';
    """),

    # v7 — ZK device sync log + device settings
    ("v7_hr_sync_log", """
        CREATE TABLE IF NOT EXISTS hr_sync_log (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            synced_at timestamptz DEFAULT now(),
            status text NOT NULL,
            fetched int DEFAULT 0,
            added int DEFAULT 0,
            updated int DEFAULT 0,
            message text
        );
        INSERT INTO hr_settings (id, key, value) VALUES (gen_random_uuid(), 'device_host', '192.168.1.201') ON CONFLICT DO NOTHING;
        INSERT INTO hr_settings (id, key, value) VALUES (gen_random_uuid(), 'device_port', '4370') ON CONFLICT DO NOTHING;
        INSERT INTO hr_settings (id, key, value) VALUES (gen_random_uuid(), 'device_timeout', '5') ON CONFLICT DO NOTHING;
    """),

    ("v8_warehouse_product_status", """
         CREATE TABLE IF NOT EXISTS warehouse_product_status (
             warehouse_id uuid NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
             product_id   uuid NOT NULL REFERENCES products(id) ON DELETE CASCADE,
             status       text NOT NULL DEFAULT 'untracked',
             PRIMARY KEY (warehouse_id, product_id)
         );
         ALTER TABLE warehouse_product_status ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
         ALTER TABLE warehouse_product_status ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
         INSERT INTO warehouse_product_status (tenant_id, warehouse_id, product_id, status)
         SELECT (SELECT id FROM tenants ORDER BY created_at LIMIT 1), warehouse_id, product_id, 'tracked'
         FROM stock_movements
         ON CONFLICT DO NOTHING;
     """),

    ("v9_product_barcodes", """
         CREATE TABLE IF NOT EXISTS product_barcodes (
             id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
             product_id uuid NOT NULL REFERENCES products(id) ON DELETE CASCADE,
             barcode text NOT NULL,
             is_primary boolean NOT NULL DEFAULT false,
             created_at timestamptz DEFAULT now(),
             UNIQUE(barcode)
         );
         CREATE INDEX IF NOT EXISTS idx_product_barcodes_product ON product_barcodes(product_id);
         CREATE INDEX IF NOT EXISTS idx_product_barcodes_barcode ON product_barcodes(barcode);
         -- Table may pre-exist from create_all without a DB-side id default
         ALTER TABLE product_barcodes ALTER COLUMN id SET DEFAULT gen_random_uuid();
         -- Migrate existing barcodes from products table if they exist
         INSERT INTO product_barcodes (product_id, barcode, is_primary)
         SELECT p.id, p.barcode, true FROM products p
         WHERE p.barcode IS NOT NULL
           AND NOT EXISTS (SELECT 1 FROM product_barcodes pb WHERE pb.barcode = p.barcode);
     """),

    ("v10_supplier_prices", """
         CREATE TABLE IF NOT EXISTS supplier_prices (
             id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
             supplier_id uuid NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
             product_id uuid NOT NULL REFERENCES products(id) ON DELETE CASCADE,
             price numeric(12,2) NOT NULL,
             currency text DEFAULT 'EGP',
             min_qty numeric(12,3) DEFAULT 1,
             last_purchase_date timestamptz,
             notes text,
             is_active boolean DEFAULT true,
             created_at timestamptz DEFAULT now(),
             updated_at timestamptz DEFAULT now(),
             UNIQUE(supplier_id, product_id)
         );
         CREATE INDEX IF NOT EXISTS idx_supplier_prices_supplier ON supplier_prices(supplier_id);
         CREATE INDEX IF NOT EXISTS idx_supplier_prices_product ON supplier_prices(product_id);
         -- Table may pre-exist from create_all without DB-side defaults
         ALTER TABLE supplier_prices ALTER COLUMN currency  SET DEFAULT 'EGP';
         ALTER TABLE supplier_prices ALTER COLUMN min_qty   SET DEFAULT 1;
         ALTER TABLE supplier_prices ALTER COLUMN is_active SET DEFAULT true;
         -- Best-effort seed from existing purchase orders if tables exist.
         DO $$
         BEGIN
           IF to_regclass('purchase_orders') IS NOT NULL AND to_regclass('purchase_order_items') IS NOT NULL THEN
             INSERT INTO supplier_prices (supplier_id, product_id, price, last_purchase_date)
             SELECT po.supplier_id, poi.product_id, poi.unit_cost, po.created_at
             FROM purchase_orders po
             JOIN purchase_order_items poi ON poi.po_id = po.id
             WHERE po.supplier_id IS NOT NULL
             ON CONFLICT (supplier_id, product_id) DO NOTHING;
           END IF;
         END $$;
     """),

    # v11 — HR payroll period workflow
    ("v11_hr_payroll_periods", """
        CREATE TABLE IF NOT EXISTS hr_payroll_periods (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            month text UNIQUE NOT NULL,
            status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','review','approved','paid')),
            submitted_by uuid REFERENCES users(id),
            submitted_at timestamptz,
            approved_by uuid REFERENCES users(id),
            approved_at timestamptz,
            paid_by uuid REFERENCES users(id),
            paid_at timestamptz,
            created_at timestamptz DEFAULT now(),
            updated_at timestamptz DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_hr_payroll_periods_status ON hr_payroll_periods(status);
        CREATE INDEX IF NOT EXISTS idx_hr_payroll_periods_month ON hr_payroll_periods(month);
    """),

    # v12 — suppliers soft-delete
    ("v12_suppliers_soft_delete", """
        ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;
        UPDATE suppliers SET is_active = true WHERE is_active IS NULL;
        CREATE INDEX IF NOT EXISTS idx_suppliers_is_active ON suppliers(is_active);
    """),

    # v13 — sales total/net_total/paid_amount columns (added after model refactor)
    ("v13_sales_amount_columns", """
        ALTER TABLE sales ADD COLUMN IF NOT EXISTS total numeric(12,2) NOT NULL DEFAULT 0;
        ALTER TABLE sales ADD COLUMN IF NOT EXISTS net_total numeric(12,2) NOT NULL DEFAULT 0;
        ALTER TABLE sales ADD COLUMN IF NOT EXISTS paid_amount numeric(12,2) DEFAULT 0;
        ALTER TABLE sales ALTER COLUMN total SET DEFAULT 0;
        ALTER TABLE sales ALTER COLUMN net_total SET DEFAULT 0;
    """),

    # v14 — sale_payments split-payment table
    ("v14_sale_payments", """
        CREATE TABLE IF NOT EXISTS sale_payments (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            sale_id uuid NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
            method text NOT NULL,
            amount numeric(12,2) NOT NULL,
            wallet_id uuid REFERENCES payment_wallets(id) ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS idx_sale_payments_sale ON sale_payments(sale_id);
    """),

    # v15 — shift model: expected_balance, difference, deposit tracking
    ("v15_shift_expected_balance", """
        ALTER TABLE shifts ADD COLUMN IF NOT EXISTS expected_balance numeric(12,2);
        ALTER TABLE shifts ADD COLUMN IF NOT EXISTS difference numeric(12,2);
        ALTER TABLE shifts ADD COLUMN IF NOT EXISTS deposit_received_by uuid REFERENCES users(id);
        ALTER TABLE shifts ADD COLUMN IF NOT EXISTS deposit_amount numeric(12,2);
    """),

    # v16 — hr_payroll_entries: add missing columns from old hr_payroll table
    ("v16_hr_payroll_entries_full", """
        ALTER TABLE hr_payroll_entries ADD COLUMN IF NOT EXISTS working_days integer;
        ALTER TABLE hr_payroll_entries ADD COLUMN IF NOT EXISTS actual_working_days integer;
        ALTER TABLE hr_payroll_entries ADD COLUMN IF NOT EXISTS absent_days integer;
        ALTER TABLE hr_payroll_entries ADD COLUMN IF NOT EXISTS vacation_days integer;
        ALTER TABLE hr_payroll_entries ADD COLUMN IF NOT EXISTS total_hours numeric(12,2);
        ALTER TABLE hr_payroll_entries ADD COLUMN IF NOT EXISTS lateness_minutes integer;
        ALTER TABLE hr_payroll_entries ADD COLUMN IF NOT EXISTS early_leave_minutes integer;
        ALTER TABLE hr_payroll_entries ADD COLUMN IF NOT EXISTS missing_scan_minutes integer;
        ALTER TABLE hr_payroll_entries ADD COLUMN IF NOT EXISTS lateness_deduction numeric(12,2);
        ALTER TABLE hr_payroll_entries ADD COLUMN IF NOT EXISTS overtime_hours numeric(12,2);
        ALTER TABLE hr_payroll_entries ADD COLUMN IF NOT EXISTS overtime_pay numeric(12,2);
        ALTER TABLE hr_payroll_entries ADD COLUMN IF NOT EXISTS bonus_days integer;
        ALTER TABLE hr_payroll_entries ADD COLUMN IF NOT EXISTS bonus_payment numeric(12,2);
        ALTER TABLE hr_payroll_entries ADD COLUMN IF NOT EXISTS bonus numeric(12,2);
        ALTER TABLE hr_payroll_entries ADD COLUMN IF NOT EXISTS deductions numeric(12,2);
        ALTER TABLE hr_payroll_entries ADD COLUMN IF NOT EXISTS advances numeric(12,2);
        ALTER TABLE hr_payroll_entries ADD COLUMN IF NOT EXISTS drawer_variance numeric(12,2);
        ALTER TABLE hr_payroll_entries ADD COLUMN IF NOT EXISTS net_salary numeric(12,2);
        ALTER TABLE hr_payroll_entries ADD COLUMN IF NOT EXISTS hourly_rate numeric(12,2);
        ALTER TABLE hr_payroll_entries ADD COLUMN IF NOT EXISTS daily_breakdown jsonb;
        ALTER TABLE hr_payroll_entries ADD COLUMN IF NOT EXISTS created_by uuid REFERENCES users(id);
        ALTER TABLE hr_payroll_entries ADD COLUMN IF NOT EXISTS status text DEFAULT 'draft';
    """),

    # v17 — unique constraint on (period_id, employee_id) for upsert
    ("v17_hr_payroll_entries_unique", """
        ALTER TABLE hr_payroll_entries DROP CONSTRAINT IF EXISTS hr_payroll_entries_period_id_employee_id_key;
        ALTER TABLE hr_payroll_entries ADD CONSTRAINT hr_payroll_entries_period_id_employee_id_key UNIQUE (period_id, employee_id);
    """),

    # v18 — hr_payroll_periods: add default for id column
    ("v18_hr_payroll_periods_id_default", """
        ALTER TABLE hr_payroll_periods ALTER COLUMN id SET DEFAULT gen_random_uuid();
    """),

    # v19 — 54 missing FK indexes across 27 tables (from model<->DB audit)
    ("v19_missing_fk_indexes",
     (MIGRATIONS_DIR / "add_missing_indexes.sql").read_text() if (MIGRATIONS_DIR / "add_missing_indexes.sql").exists() else ""),

    # v20 — stock_balances maintained table: O(1) balance reads + backfill from movements
    ("v20_stock_balances",
     (MIGRATIONS_DIR / "add_stock_balances.sql").read_text() if (MIGRATIONS_DIR / "add_stock_balances.sql").exists() else ""),

    # v21 — reconcile columns present in models but missing from older databases
    ("v21_model_column_reconciliation", """
        ALTER TABLE customers ADD COLUMN IF NOT EXISTS credit_limit numeric(14,2);
        ALTER TABLE financial_categories ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;
        ALTER TABLE financial_categories ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();
    """),

    # v22 — reconcile enum values + uuid PK defaults used by raw-SQL inserts
    ("v22_defaults_and_enum_reconciliation", """
        ALTER TYPE drawer_tx_type_enum ADD VALUE IF NOT EXISTS 'revenue_delivery';
        ALTER TABLE accounting_periods   ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE archived_documents   ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE expenses             ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE expense_vendors      ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE sale_items           ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE sale_payments        ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE stock_movements      ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE suppliers            ALTER COLUMN id SET DEFAULT gen_random_uuid();
    """),

    # v23 — payment wallet types are free-form String(32) in the model
    # (clients register custom wallet types); drop the legacy 3-value check
    ("v23_drop_wallet_type_check", """
        ALTER TABLE payment_wallets DROP CONSTRAINT IF EXISTS payment_wallets_type_check;
    """),

    # v24 — boolean flag defaults so raw-SQL inserts that omit them succeed
    ("v24_flag_defaults", """
        ALTER TABLE expense_vendors ALTER COLUMN is_active SET DEFAULT true;
        ALTER TABLE expenses        ALTER COLUMN is_recurring SET DEFAULT false;
    """),

    # v25 — nullability reconciliation with models (loosen legacy NOT NULLs)
    ("v25_nullability_reconciliation", """
        ALTER TABLE expenses           ALTER COLUMN recurring_interval DROP NOT NULL;
        ALTER TABLE expenses           ALTER COLUMN recurring_end_date DROP NOT NULL;
        ALTER TABLE hr_settings        ALTER COLUMN value DROP NOT NULL;
        ALTER TABLE products           ALTER COLUMN subcategory_id DROP NOT NULL;
        ALTER TABLE hr_payroll_entries ALTER COLUMN deductions DROP NOT NULL;
    """),

    # v26 — columns present in models but missing from pre-refactor snapshots
    ("v26_model_column_backfill", """
        ALTER TABLE audit_log            ADD COLUMN IF NOT EXISTS action_type text;
        ALTER TABLE audit_log            ADD COLUMN IF NOT EXISTS reason text;
        ALTER TABLE audit_log            ADD COLUMN IF NOT EXISTS details text;
        ALTER TABLE categories           ADD COLUMN IF NOT EXISTS code varchar(32);
        ALTER TABLE categories           ADD COLUMN IF NOT EXISTS image_url varchar(512);
        ALTER TABLE subcategories        ADD COLUMN IF NOT EXISTS code varchar(32);
        ALTER TABLE products             ADD COLUMN IF NOT EXISTS code varchar(32);
        ALTER TABLE products             ADD COLUMN IF NOT EXISTS shelf_number varchar(32);
        ALTER TABLE products             ADD COLUMN IF NOT EXISTS description text;
        ALTER TABLE sales                ADD COLUMN IF NOT EXISTS returns_total numeric(12,2) NOT NULL DEFAULT 0;
        ALTER TABLE sales                ADD COLUMN IF NOT EXISTS last_paid_at timestamptz;
        ALTER TABLE customer_payments    ADD COLUMN IF NOT EXISTS sale_id uuid;
        ALTER TABLE stock_movements      ADD COLUMN IF NOT EXISTS sale_id uuid;
        ALTER TABLE stock_movements      ADD COLUMN IF NOT EXISTS purchase_id uuid;
        ALTER TABLE hr_advances          ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();
        ALTER TABLE hr_attendance        ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();
        ALTER TABLE hr_payroll           ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();
        ALTER TABLE payroll_entries      ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now();
        ALTER TABLE supplier_transactions ADD COLUMN IF NOT EXISTS tx_type varchar(16);
        ALTER TABLE hr_shifts            ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;
        ALTER TABLE hr_shifts            ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now();
        ALTER TABLE hr_shifts            ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();
        ALTER TABLE hr_settings          ADD COLUMN IF NOT EXISTS id uuid NOT NULL DEFAULT gen_random_uuid();
        ALTER TABLE hr_settings          ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now();
        ALTER TABLE hr_settings          ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='hr_settings'::regclass AND contype='p') THEN
                ALTER TABLE hr_settings ADD PRIMARY KEY (id);
            END IF;
        END $$;
    """),

    # v27 — uuid PK defaults everywhere (ORM inserts rely on them on every table)
    ("v27_uuid_pk_defaults", """
        ALTER TABLE categories           ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE collection_items     ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE customer_payments    ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE customers            ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE device_tokens        ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE drawer_transactions  ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE employees            ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE hr_payroll_entries   ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE hr_sync_log          ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE payroll_entries      ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE payroll_periods      ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE product_barcodes     ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE product_collections  ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE product_images       ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE products             ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE purchase_order_items ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE purchase_orders      ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE sales                ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE shifts               ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE subcategories        ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE supplier_prices      ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE users                ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE wallet_transactions  ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE warehouses           ALTER COLUMN id SET DEFAULT gen_random_uuid();
    """),

    # v28 — hr_sync_log counters: raw-SQL failure path inserts without them
    ("v28_sync_log_counter_defaults", """
        ALTER TABLE hr_sync_log ALTER COLUMN fetched SET DEFAULT 0;
        ALTER TABLE hr_sync_log ALTER COLUMN added   SET DEFAULT 0;
        ALTER TABLE hr_sync_log ALTER COLUMN updated SET DEFAULT 0;
    """),
    # v29 — multi-tenancy: tenants + tenant_id on all business tables (backfill = tenant #1)
    ("v29_multi_tenancy", """
        CREATE TABLE IF NOT EXISTS tenants (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name text NOT NULL, sector text NOT NULL DEFAULT 'plumbing', scale text NOT NULL DEFAULT 'medium', palette jsonb NOT NULL DEFAULT '{}'::jsonb, features jsonb NOT NULL DEFAULT '[]'::jsonb, plan text NOT NULL DEFAULT 'trial', trial_ends_at timestamptz, storefront_slug text UNIQUE, created_at timestamptz NOT NULL DEFAULT now());
        CREATE TABLE IF NOT EXISTS subscriptions (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE, plan text NOT NULL, status text NOT NULL DEFAULT 'requested', contact_phone text, created_at timestamptz NOT NULL DEFAULT now());
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
        INSERT INTO tenants (id, name, sector, scale, palette, features, plan) SELECT gen_random_uuid(), 'ميزان', 'retail', 'small', '{}'::jsonb, '[]'::jsonb, 'enterprise' WHERE NOT EXISTS (SELECT 1 FROM tenants);
        ALTER TABLE accounting_periods ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE archived_documents ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE categories ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE collection_items ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE employees ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE users ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE customer_payments ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE customers ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE device_tokens ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE drawer_transactions ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE expense_vendors ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE expenses ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE financial_categories ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE hr_advances ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE hr_attendance ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE hr_audit_log ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE hr_employees ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE hr_payroll ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE hr_payroll_entries ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE hr_payroll_periods ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE hr_settings ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE hr_shifts ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE hr_sync_log ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE payment_wallets ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE payroll_entries ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE product_barcodes ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE product_collections ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE product_images ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE products ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE purchase_order_items ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE purchase_price_history ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE safe_deposits ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE safe_transactions ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE safes ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE sale_items ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE sale_payments ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE sales ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE shifts ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE stock_balances ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE stock_movements ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE store_settings ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE subcategories ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE supplier_prices ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE supplier_transactions ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE wallet_transactions ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE warehouse_product_status ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        ALTER TABLE warehouses ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
        UPDATE users SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE accounting_periods SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE archived_documents SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE audit_log SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE categories SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE customer_payments SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE collection_items SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE employees SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE customers SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE device_tokens SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE drawer_transactions SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE expense_vendors SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE expenses SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE financial_categories SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE hr_advances SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE hr_attendance SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE hr_audit_log SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE hr_employees SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE hr_payroll SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE hr_payroll_entries SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE hr_payroll_periods SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE hr_settings SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE hr_shifts SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE hr_sync_log SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE payment_wallets SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE payroll_entries SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE product_barcodes SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE product_collections SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE product_images SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE products SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE purchase_order_items SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE purchase_orders SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE purchase_price_history SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE safe_deposits SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE safe_transactions SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE safes SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE sale_items SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE sale_payments SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE sales SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE shifts SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE stock_balances SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE stock_movements SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE store_settings SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE subcategories SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE supplier_prices SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE supplier_transactions SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE suppliers SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE wallet_transactions SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE warehouse_product_status SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        UPDATE warehouses SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        CREATE INDEX IF NOT EXISTS ix_accounting_periods_tenant_id ON accounting_periods(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_archived_documents_tenant_id ON archived_documents(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_audit_log_tenant_id ON audit_log(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_categories_tenant_id ON categories(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_customer_payments_tenant_id ON customer_payments(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_collection_items_tenant_id ON collection_items(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_employees_tenant_id ON employees(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_customers_tenant_id ON customers(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_device_tokens_tenant_id ON device_tokens(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_drawer_transactions_tenant_id ON drawer_transactions(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_expense_vendors_tenant_id ON expense_vendors(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_expenses_tenant_id ON expenses(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_financial_categories_tenant_id ON financial_categories(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_hr_advances_tenant_id ON hr_advances(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_hr_attendance_tenant_id ON hr_attendance(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_hr_audit_log_tenant_id ON hr_audit_log(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_hr_employees_tenant_id ON hr_employees(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_hr_payroll_tenant_id ON hr_payroll(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_hr_payroll_entries_tenant_id ON hr_payroll_entries(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_hr_payroll_periods_tenant_id ON hr_payroll_periods(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_hr_settings_tenant_id ON hr_settings(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_hr_shifts_tenant_id ON hr_shifts(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_hr_sync_log_tenant_id ON hr_sync_log(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_payment_wallets_tenant_id ON payment_wallets(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_payroll_entries_tenant_id ON payroll_entries(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_product_barcodes_tenant_id ON product_barcodes(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_product_collections_tenant_id ON product_collections(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_product_images_tenant_id ON product_images(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_products_tenant_id ON products(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_purchase_order_items_tenant_id ON purchase_order_items(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_purchase_orders_tenant_id ON purchase_orders(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_purchase_price_history_tenant_id ON purchase_price_history(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_safe_deposits_tenant_id ON safe_deposits(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_safe_transactions_tenant_id ON safe_transactions(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_safes_tenant_id ON safes(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_sale_items_tenant_id ON sale_items(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_sale_payments_tenant_id ON sale_payments(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_sales_tenant_id ON sales(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_shifts_tenant_id ON shifts(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_stock_balances_tenant_id ON stock_balances(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_stock_movements_tenant_id ON stock_movements(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_store_settings_tenant_id ON store_settings(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_subcategories_tenant_id ON subcategories(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_supplier_prices_tenant_id ON supplier_prices(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_supplier_transactions_tenant_id ON supplier_transactions(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_suppliers_tenant_id ON suppliers(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_wallet_transactions_tenant_id ON wallet_transactions(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_warehouse_product_status_tenant_id ON warehouse_product_status(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_warehouses_tenant_id ON warehouses(tenant_id);
        ALTER TABLE accounting_periods ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE archived_documents ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE audit_log ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE categories ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE customer_payments ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE collection_items ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE employees ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE customers ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE device_tokens ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE drawer_transactions ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE expense_vendors ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE expenses ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE financial_categories ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE hr_advances ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE hr_attendance ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE hr_audit_log ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE hr_employees ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE hr_payroll ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE hr_payroll_entries ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE hr_payroll_periods ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE hr_settings ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE hr_shifts ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE hr_sync_log ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE payment_wallets ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE payroll_entries ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE product_barcodes ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE product_collections ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE product_images ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE products ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE purchase_order_items ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE purchase_orders ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE purchase_price_history ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE safe_deposits ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE safe_transactions ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE safes ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE sale_items ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE sale_payments ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE sales ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE shifts ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE stock_balances ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE stock_movements ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE store_settings ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE subcategories ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE supplier_prices ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE supplier_transactions ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE suppliers ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE wallet_transactions ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE warehouse_product_status ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE warehouses ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE categories DROP CONSTRAINT IF EXISTS categories_name_key;
        DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_categories_name') THEN ALTER TABLE categories ADD CONSTRAINT uq_categories_name UNIQUE (tenant_id, name); END IF; END $$;
        ALTER TABLE warehouses DROP CONSTRAINT IF EXISTS warehouses_code_key;
        DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_warehouses_code') THEN ALTER TABLE warehouses ADD CONSTRAINT uq_warehouses_code UNIQUE (tenant_id, code); END IF; END $$;
        ALTER TABLE payment_wallets DROP CONSTRAINT IF EXISTS payment_wallets_name_key;
        DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_payment_wallets_name') THEN ALTER TABLE payment_wallets ADD CONSTRAINT uq_payment_wallets_name UNIQUE (tenant_id, name); END IF; END $$;
        ALTER TABLE sales DROP CONSTRAINT IF EXISTS sales_invoice_number_key;
        DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_sales_invoice_number') THEN ALTER TABLE sales ADD CONSTRAINT uq_sales_invoice_number UNIQUE (tenant_id, invoice_number); END IF; END $$;
        ALTER TABLE purchase_orders DROP CONSTRAINT IF EXISTS purchase_orders_po_number_key;
        DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_purchase_orders_po_number') THEN ALTER TABLE purchase_orders ADD CONSTRAINT uq_purchase_orders_po_number UNIQUE (tenant_id, po_number); END IF; END $$;
        ALTER TABLE hr_payroll_periods DROP CONSTRAINT IF EXISTS hr_payroll_periods_month_key;
        DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_hr_payroll_periods_month') THEN ALTER TABLE hr_payroll_periods ADD CONSTRAINT uq_hr_payroll_periods_month UNIQUE (tenant_id, month); END IF; END $$;
        ALTER TABLE accounting_periods DROP CONSTRAINT IF EXISTS accounting_periods_month_key;
        DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_accounting_periods_month') THEN ALTER TABLE accounting_periods ADD CONSTRAINT uq_accounting_periods_month UNIQUE (tenant_id, month); END IF; END $$;
        ALTER TABLE hr_settings DROP CONSTRAINT IF EXISTS hr_settings_key_key;
        DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_hr_settings_key') THEN ALTER TABLE hr_settings ADD CONSTRAINT uq_hr_settings_key UNIQUE (tenant_id, key); END IF; END $$;
        ALTER TABLE hr_employees DROP CONSTRAINT IF EXISTS hr_employees_emp_code_key;
        DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_hr_employees_emp_code') THEN ALTER TABLE hr_employees ADD CONSTRAINT uq_hr_employees_emp_code UNIQUE (tenant_id, emp_code); END IF; END $$;
    """),
    # v30 — row-level security: DB-enforced tenancy for ORM AND raw SQL
    ("v30_rls", """
        ALTER TABLE accounting_periods ENABLE ROW LEVEL SECURITY;
        ALTER TABLE accounting_periods FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'accounting_periods' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON accounting_periods
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE archived_documents ENABLE ROW LEVEL SECURITY;
        ALTER TABLE archived_documents FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'archived_documents' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON archived_documents
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
        ALTER TABLE audit_log FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'audit_log' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON audit_log
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE categories ENABLE ROW LEVEL SECURITY;
        ALTER TABLE categories FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'categories' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON categories
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE collection_items ENABLE ROW LEVEL SECURITY;
        ALTER TABLE collection_items FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'collection_items' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON collection_items
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE customer_payments ENABLE ROW LEVEL SECURITY;
        ALTER TABLE customer_payments FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'customer_payments' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON customer_payments
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
        ALTER TABLE customers FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'customers' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON customers
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE device_tokens ENABLE ROW LEVEL SECURITY;
        ALTER TABLE device_tokens FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'device_tokens' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON device_tokens
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE drawer_transactions ENABLE ROW LEVEL SECURITY;
        ALTER TABLE drawer_transactions FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'drawer_transactions' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON drawer_transactions
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE employees ENABLE ROW LEVEL SECURITY;
        ALTER TABLE employees FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'employees' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON employees
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE expense_vendors ENABLE ROW LEVEL SECURITY;
        ALTER TABLE expense_vendors FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'expense_vendors' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON expense_vendors
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE expenses ENABLE ROW LEVEL SECURITY;
        ALTER TABLE expenses FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'expenses' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON expenses
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE financial_categories ENABLE ROW LEVEL SECURITY;
        ALTER TABLE financial_categories FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'financial_categories' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON financial_categories
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE hr_advances ENABLE ROW LEVEL SECURITY;
        ALTER TABLE hr_advances FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'hr_advances' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON hr_advances
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE hr_attendance ENABLE ROW LEVEL SECURITY;
        ALTER TABLE hr_attendance FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'hr_attendance' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON hr_attendance
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE hr_audit_log ENABLE ROW LEVEL SECURITY;
        ALTER TABLE hr_audit_log FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'hr_audit_log' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON hr_audit_log
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE hr_employees ENABLE ROW LEVEL SECURITY;
        ALTER TABLE hr_employees FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'hr_employees' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON hr_employees
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE hr_payroll ENABLE ROW LEVEL SECURITY;
        ALTER TABLE hr_payroll FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'hr_payroll' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON hr_payroll
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE hr_payroll_entries ENABLE ROW LEVEL SECURITY;
        ALTER TABLE hr_payroll_entries FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'hr_payroll_entries' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON hr_payroll_entries
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE hr_payroll_periods ENABLE ROW LEVEL SECURITY;
        ALTER TABLE hr_payroll_periods FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'hr_payroll_periods' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON hr_payroll_periods
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE hr_settings ENABLE ROW LEVEL SECURITY;
        ALTER TABLE hr_settings FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'hr_settings' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON hr_settings
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE hr_shifts ENABLE ROW LEVEL SECURITY;
        ALTER TABLE hr_shifts FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'hr_shifts' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON hr_shifts
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE hr_sync_log ENABLE ROW LEVEL SECURITY;
        ALTER TABLE hr_sync_log FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'hr_sync_log' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON hr_sync_log
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE payment_wallets ENABLE ROW LEVEL SECURITY;
        ALTER TABLE payment_wallets FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'payment_wallets' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON payment_wallets
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE payroll_entries ENABLE ROW LEVEL SECURITY;
        ALTER TABLE payroll_entries FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'payroll_entries' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON payroll_entries
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE product_barcodes ENABLE ROW LEVEL SECURITY;
        ALTER TABLE product_barcodes FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'product_barcodes' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON product_barcodes
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE product_collections ENABLE ROW LEVEL SECURITY;
        ALTER TABLE product_collections FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'product_collections' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON product_collections
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE product_images ENABLE ROW LEVEL SECURITY;
        ALTER TABLE product_images FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'product_images' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON product_images
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE products ENABLE ROW LEVEL SECURITY;
        ALTER TABLE products FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'products' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON products
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE purchase_order_items ENABLE ROW LEVEL SECURITY;
        ALTER TABLE purchase_order_items FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'purchase_order_items' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON purchase_order_items
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE purchase_orders ENABLE ROW LEVEL SECURITY;
        ALTER TABLE purchase_orders FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'purchase_orders' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON purchase_orders
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE purchase_price_history ENABLE ROW LEVEL SECURITY;
        ALTER TABLE purchase_price_history FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'purchase_price_history' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON purchase_price_history
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE safe_deposits ENABLE ROW LEVEL SECURITY;
        ALTER TABLE safe_deposits FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'safe_deposits' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON safe_deposits
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE safe_transactions ENABLE ROW LEVEL SECURITY;
        ALTER TABLE safe_transactions FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'safe_transactions' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON safe_transactions
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE safes ENABLE ROW LEVEL SECURITY;
        ALTER TABLE safes FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'safes' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON safes
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE sale_items ENABLE ROW LEVEL SECURITY;
        ALTER TABLE sale_items FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'sale_items' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON sale_items
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE sale_payments ENABLE ROW LEVEL SECURITY;
        ALTER TABLE sale_payments FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'sale_payments' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON sale_payments
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE sales ENABLE ROW LEVEL SECURITY;
        ALTER TABLE sales FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'sales' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON sales
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE shifts ENABLE ROW LEVEL SECURITY;
        ALTER TABLE shifts FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'shifts' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON shifts
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE stock_balances ENABLE ROW LEVEL SECURITY;
        ALTER TABLE stock_balances FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'stock_balances' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON stock_balances
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE stock_movements ENABLE ROW LEVEL SECURITY;
        ALTER TABLE stock_movements FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'stock_movements' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON stock_movements
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE store_settings ENABLE ROW LEVEL SECURITY;
        ALTER TABLE store_settings FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'store_settings' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON store_settings
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE subcategories ENABLE ROW LEVEL SECURITY;
        ALTER TABLE subcategories FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'subcategories' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON subcategories
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE supplier_prices ENABLE ROW LEVEL SECURITY;
        ALTER TABLE supplier_prices FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'supplier_prices' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON supplier_prices
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE supplier_transactions ENABLE ROW LEVEL SECURITY;
        ALTER TABLE supplier_transactions FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'supplier_transactions' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON supplier_transactions
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE suppliers ENABLE ROW LEVEL SECURITY;
        ALTER TABLE suppliers FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'suppliers' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON suppliers
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE wallet_transactions ENABLE ROW LEVEL SECURITY;
        ALTER TABLE wallet_transactions FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'wallet_transactions' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON wallet_transactions
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE warehouse_product_status ENABLE ROW LEVEL SECURITY;
        ALTER TABLE warehouse_product_status FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'warehouse_product_status' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON warehouse_product_status
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
        ALTER TABLE warehouses ENABLE ROW LEVEL SECURITY;
        ALTER TABLE warehouses FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'warehouses' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON warehouses
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;
    """),
    # v31 — raw-SQL inserts get tenant_id from the RLS GUC automatically
    ("v31_tenant_default", """
        ALTER TABLE accounting_periods ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE archived_documents ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE audit_log ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE categories ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE collection_items ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE customer_payments ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE customers ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE device_tokens ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE drawer_transactions ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE employees ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE expense_vendors ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE expenses ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE financial_categories ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE hr_advances ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE hr_attendance ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE hr_audit_log ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE hr_employees ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE hr_payroll ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE hr_payroll_entries ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE hr_payroll_periods ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE hr_settings ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE hr_shifts ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE hr_sync_log ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE payment_wallets ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE payroll_entries ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE product_barcodes ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE product_collections ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE product_images ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE products ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE purchase_order_items ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE purchase_orders ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE purchase_price_history ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE safe_deposits ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE safe_transactions ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE safes ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE sale_items ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE sale_payments ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE sales ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE shifts ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE stock_balances ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE stock_movements ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE store_settings ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE subcategories ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE supplier_prices ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE supplier_transactions ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE suppliers ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE wallet_transactions ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE warehouse_product_status ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
        ALTER TABLE warehouses ALTER COLUMN tenant_id SET DEFAULT current_setting('app.tenant_id', true)::uuid;
    """),
    # v32 — tenant deletion cascades to all tenant data (incl. user accounts)
    ("v32_tenant_cascade", """
        ALTER TABLE users DROP CONSTRAINT IF EXISTS users_tenant_id_fkey;
        ALTER TABLE users ADD CONSTRAINT users_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE accounting_periods DROP CONSTRAINT IF EXISTS accounting_periods_tenant_id_fkey;
        ALTER TABLE accounting_periods ADD CONSTRAINT accounting_periods_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE archived_documents DROP CONSTRAINT IF EXISTS archived_documents_tenant_id_fkey;
        ALTER TABLE archived_documents ADD CONSTRAINT archived_documents_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE audit_log DROP CONSTRAINT IF EXISTS audit_log_tenant_id_fkey;
        ALTER TABLE audit_log ADD CONSTRAINT audit_log_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE categories DROP CONSTRAINT IF EXISTS categories_tenant_id_fkey;
        ALTER TABLE categories ADD CONSTRAINT categories_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE collection_items DROP CONSTRAINT IF EXISTS collection_items_tenant_id_fkey;
        ALTER TABLE collection_items ADD CONSTRAINT collection_items_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE customer_payments DROP CONSTRAINT IF EXISTS customer_payments_tenant_id_fkey;
        ALTER TABLE customer_payments ADD CONSTRAINT customer_payments_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE customers DROP CONSTRAINT IF EXISTS customers_tenant_id_fkey;
        ALTER TABLE customers ADD CONSTRAINT customers_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE device_tokens DROP CONSTRAINT IF EXISTS device_tokens_tenant_id_fkey;
        ALTER TABLE device_tokens ADD CONSTRAINT device_tokens_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE drawer_transactions DROP CONSTRAINT IF EXISTS drawer_transactions_tenant_id_fkey;
        ALTER TABLE drawer_transactions ADD CONSTRAINT drawer_transactions_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE employees DROP CONSTRAINT IF EXISTS employees_tenant_id_fkey;
        ALTER TABLE employees ADD CONSTRAINT employees_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE expense_vendors DROP CONSTRAINT IF EXISTS expense_vendors_tenant_id_fkey;
        ALTER TABLE expense_vendors ADD CONSTRAINT expense_vendors_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE expenses DROP CONSTRAINT IF EXISTS expenses_tenant_id_fkey;
        ALTER TABLE expenses ADD CONSTRAINT expenses_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE financial_categories DROP CONSTRAINT IF EXISTS financial_categories_tenant_id_fkey;
        ALTER TABLE financial_categories ADD CONSTRAINT financial_categories_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE hr_advances DROP CONSTRAINT IF EXISTS hr_advances_tenant_id_fkey;
        ALTER TABLE hr_advances ADD CONSTRAINT hr_advances_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE hr_attendance DROP CONSTRAINT IF EXISTS hr_attendance_tenant_id_fkey;
        ALTER TABLE hr_attendance ADD CONSTRAINT hr_attendance_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE hr_audit_log DROP CONSTRAINT IF EXISTS hr_audit_log_tenant_id_fkey;
        ALTER TABLE hr_audit_log ADD CONSTRAINT hr_audit_log_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE hr_employees DROP CONSTRAINT IF EXISTS hr_employees_tenant_id_fkey;
        ALTER TABLE hr_employees ADD CONSTRAINT hr_employees_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE hr_payroll DROP CONSTRAINT IF EXISTS hr_payroll_tenant_id_fkey;
        ALTER TABLE hr_payroll ADD CONSTRAINT hr_payroll_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE hr_payroll_entries DROP CONSTRAINT IF EXISTS hr_payroll_entries_tenant_id_fkey;
        ALTER TABLE hr_payroll_entries ADD CONSTRAINT hr_payroll_entries_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE hr_payroll_periods DROP CONSTRAINT IF EXISTS hr_payroll_periods_tenant_id_fkey;
        ALTER TABLE hr_payroll_periods ADD CONSTRAINT hr_payroll_periods_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE hr_settings DROP CONSTRAINT IF EXISTS hr_settings_tenant_id_fkey;
        ALTER TABLE hr_settings ADD CONSTRAINT hr_settings_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE hr_shifts DROP CONSTRAINT IF EXISTS hr_shifts_tenant_id_fkey;
        ALTER TABLE hr_shifts ADD CONSTRAINT hr_shifts_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE hr_sync_log DROP CONSTRAINT IF EXISTS hr_sync_log_tenant_id_fkey;
        ALTER TABLE hr_sync_log ADD CONSTRAINT hr_sync_log_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE payment_wallets DROP CONSTRAINT IF EXISTS payment_wallets_tenant_id_fkey;
        ALTER TABLE payment_wallets ADD CONSTRAINT payment_wallets_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE payroll_entries DROP CONSTRAINT IF EXISTS payroll_entries_tenant_id_fkey;
        ALTER TABLE payroll_entries ADD CONSTRAINT payroll_entries_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE product_barcodes DROP CONSTRAINT IF EXISTS product_barcodes_tenant_id_fkey;
        ALTER TABLE product_barcodes ADD CONSTRAINT product_barcodes_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE product_collections DROP CONSTRAINT IF EXISTS product_collections_tenant_id_fkey;
        ALTER TABLE product_collections ADD CONSTRAINT product_collections_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE product_images DROP CONSTRAINT IF EXISTS product_images_tenant_id_fkey;
        ALTER TABLE product_images ADD CONSTRAINT product_images_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE products DROP CONSTRAINT IF EXISTS products_tenant_id_fkey;
        ALTER TABLE products ADD CONSTRAINT products_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE purchase_order_items DROP CONSTRAINT IF EXISTS purchase_order_items_tenant_id_fkey;
        ALTER TABLE purchase_order_items ADD CONSTRAINT purchase_order_items_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE purchase_orders DROP CONSTRAINT IF EXISTS purchase_orders_tenant_id_fkey;
        ALTER TABLE purchase_orders ADD CONSTRAINT purchase_orders_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE purchase_price_history DROP CONSTRAINT IF EXISTS purchase_price_history_tenant_id_fkey;
        ALTER TABLE purchase_price_history ADD CONSTRAINT purchase_price_history_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE safe_deposits DROP CONSTRAINT IF EXISTS safe_deposits_tenant_id_fkey;
        ALTER TABLE safe_deposits ADD CONSTRAINT safe_deposits_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE safe_transactions DROP CONSTRAINT IF EXISTS safe_transactions_tenant_id_fkey;
        ALTER TABLE safe_transactions ADD CONSTRAINT safe_transactions_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE safes DROP CONSTRAINT IF EXISTS safes_tenant_id_fkey;
        ALTER TABLE safes ADD CONSTRAINT safes_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE sale_items DROP CONSTRAINT IF EXISTS sale_items_tenant_id_fkey;
        ALTER TABLE sale_items ADD CONSTRAINT sale_items_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE sale_payments DROP CONSTRAINT IF EXISTS sale_payments_tenant_id_fkey;
        ALTER TABLE sale_payments ADD CONSTRAINT sale_payments_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE sales DROP CONSTRAINT IF EXISTS sales_tenant_id_fkey;
        ALTER TABLE sales ADD CONSTRAINT sales_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE shifts DROP CONSTRAINT IF EXISTS shifts_tenant_id_fkey;
        ALTER TABLE shifts ADD CONSTRAINT shifts_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE stock_balances DROP CONSTRAINT IF EXISTS stock_balances_tenant_id_fkey;
        ALTER TABLE stock_balances ADD CONSTRAINT stock_balances_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE stock_movements DROP CONSTRAINT IF EXISTS stock_movements_tenant_id_fkey;
        ALTER TABLE stock_movements ADD CONSTRAINT stock_movements_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE store_settings DROP CONSTRAINT IF EXISTS store_settings_tenant_id_fkey;
        ALTER TABLE store_settings ADD CONSTRAINT store_settings_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE subcategories DROP CONSTRAINT IF EXISTS subcategories_tenant_id_fkey;
        ALTER TABLE subcategories ADD CONSTRAINT subcategories_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE supplier_prices DROP CONSTRAINT IF EXISTS supplier_prices_tenant_id_fkey;
        ALTER TABLE supplier_prices ADD CONSTRAINT supplier_prices_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE supplier_transactions DROP CONSTRAINT IF EXISTS supplier_transactions_tenant_id_fkey;
        ALTER TABLE supplier_transactions ADD CONSTRAINT supplier_transactions_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE suppliers DROP CONSTRAINT IF EXISTS suppliers_tenant_id_fkey;
        ALTER TABLE suppliers ADD CONSTRAINT suppliers_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE wallet_transactions DROP CONSTRAINT IF EXISTS wallet_transactions_tenant_id_fkey;
        ALTER TABLE wallet_transactions ADD CONSTRAINT wallet_transactions_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE warehouse_product_status DROP CONSTRAINT IF EXISTS warehouse_product_status_tenant_id_fkey;
        ALTER TABLE warehouse_product_status ADD CONSTRAINT warehouse_product_status_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        ALTER TABLE warehouses DROP CONSTRAINT IF EXISTS warehouses_tenant_id_fkey;
        ALTER TABLE warehouses ADD CONSTRAINT warehouses_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
    """),
    ("v33_tenant_constraints_and_demo", """
        -- 1. Fix global product_barcodes uniqueness to composite (tenant_id, barcode)
        DROP INDEX IF EXISTS ix_product_barcodes_barcode;
        ALTER TABLE product_barcodes DROP CONSTRAINT IF EXISTS product_barcodes_barcode_key;
        CREATE UNIQUE INDEX IF NOT EXISTS uq_product_barcodes_tenant_barcode ON product_barcodes(tenant_id, barcode);

        -- 2. Drop redundant global unique index on accounting_periods(month)
        DROP INDEX IF EXISTS idx_accounting_periods_month;

        -- 3. Fix safe_deposits uniqueness to composite (tenant_id, doc_number)
        ALTER TABLE safe_deposits DROP CONSTRAINT IF EXISTS safe_deposits_doc_number_key;
        CREATE UNIQUE INDEX IF NOT EXISTS uq_safe_deposits_tenant_doc_number ON safe_deposits(tenant_id, doc_number);

        -- 4. Harden users table: backfill, NOT NULL tenant_id, composite unique, and RLS
        UPDATE users SET tenant_id = (SELECT id FROM tenants ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL;
        ALTER TABLE users ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE users ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid;
        ALTER TABLE users DROP CONSTRAINT IF EXISTS users_username_key;
        CREATE UNIQUE INDEX IF NOT EXISTS uq_users_tenant_username ON users(tenant_id, username);
        ALTER TABLE users ENABLE ROW LEVEL SECURITY;
        ALTER TABLE users FORCE ROW LEVEL SECURITY;
        DO $fn$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'users' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON users
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END
        $fn$;

        -- 5. Add is_demo column to business tables for clean onboarding demo wipes
        DO $fn$
        DECLARE
          tbl text;
        BEGIN
          FOR tbl IN SELECT unnest(ARRAY[
            'products', 'categories', 'subcategories', 'warehouses', 'customers', 'suppliers',
            'payment_wallets', 'safes', 'sales', 'sale_items', 'sale_payments', 'stock_movements',
            'stock_balances', 'drawer_transactions', 'purchase_orders', 'purchase_order_items', 'users'
          ]) LOOP
            IF to_regclass('public.' || tbl) IS NOT NULL THEN
              EXECUTE 'ALTER TABLE ' || tbl || ' ADD COLUMN IF NOT EXISTS is_demo BOOLEAN NOT NULL DEFAULT FALSE;';
              EXECUTE 'CREATE INDEX IF NOT EXISTS idx_' || tbl || '_is_demo ON ' || tbl || '(is_demo) WHERE is_demo = TRUE;';
            END IF;
          END LOOP;
        END
        $fn$;
    """),

    # v33 — tenant routing, multi-tenancy columns, and user superadmin
    ("v33_tenant_routing_and_superadmin", """
        ALTER TABLE tenants ADD COLUMN IF NOT EXISTS slug varchar(64);
        ALTER TABLE tenants ADD COLUMN IF NOT EXISTS custom_domain varchar(128);
        ALTER TABLE tenants ADD COLUMN IF NOT EXISTS status varchar(32) NOT NULL DEFAULT 'active';
        ALTER TABLE tenants ADD COLUMN IF NOT EXISTS deployment_mode varchar(32) NOT NULL DEFAULT 'cloud_saas';
        ALTER TABLE tenants ADD COLUMN IF NOT EXISTS business_type varchar(64) NOT NULL DEFAULT 'retail';
        ALTER TABLE tenants ADD COLUMN IF NOT EXISTS tech_stack jsonb NOT NULL DEFAULT '{}'::jsonb;
        ALTER TABLE tenants ADD COLUMN IF NOT EXISTS active_modules jsonb NOT NULL DEFAULT '[]'::jsonb;
        ALTER TABLE tenants ADD COLUMN IF NOT EXISTS limits jsonb NOT NULL DEFAULT '{}'::jsonb;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_tenants_slug ON tenants(slug);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_tenants_custom_domain ON tenants(custom_domain);

        ALTER TABLE users ADD COLUMN IF NOT EXISTS is_superadmin boolean NOT NULL DEFAULT false;
        ALTER TABLE payroll_periods ADD COLUMN IF NOT EXISTS tenant_id uuid;
    """),
    # v34 — per-user personal settings (separate from global store settings)
    ("v34_user_settings", """
        ALTER TABLE users ADD COLUMN IF NOT EXISTS settings jsonb NOT NULL DEFAULT '{}'::jsonb;
    """),
    # v35 — store_settings: per-tenant primary key (was global key PK, broke multi-tenancy)
    ("v35_store_settings_per_tenant_pk", """
        ALTER TABLE store_settings ADD COLUMN IF NOT EXISTS id uuid DEFAULT gen_random_uuid();
        UPDATE store_settings SET id = gen_random_uuid() WHERE id IS NULL;
        ALTER TABLE store_settings ALTER COLUMN id SET NOT NULL;
        ALTER TABLE store_settings DROP CONSTRAINT IF EXISTS store_settings_pkey;
        ALTER TABLE store_settings ADD PRIMARY KEY (id);
        ALTER TABLE store_settings ADD CONSTRAINT uq_store_settings_tenant_key UNIQUE (tenant_id, key);
    """),
    # v36 — clinic referential integrity: patient_id FKs (P0 #5)
    ("v36_clinic_patient_fks", """
        -- Ensure new tables exist (create_all is disabled on Vercel)
        CREATE TABLE IF NOT EXISTS clinic_invoices (
            id varchar(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
            tenant_id uuid NOT NULL,
            invoice_ref varchar(32) NOT NULL,
            patient_id varchar(36) NOT NULL,
            patient_name varchar(128) NOT NULL,
            appointment_id varchar(36),
            encounter_ref varchar(32),
            charges jsonb NOT NULL DEFAULT '[]'::jsonb,
            total double precision NOT NULL DEFAULT 0,
            copay_percent double precision NOT NULL DEFAULT 0,
            insurance_amount double precision NOT NULL DEFAULT 0,
            patient_amount double precision NOT NULL DEFAULT 0,
            paid_amount double precision NOT NULL DEFAULT 0,
            status varchar(32) NOT NULL DEFAULT 'pending',
            payment_method varchar(32) NOT NULL DEFAULT 'cash',
            created_at timestamptz NOT NULL DEFAULT now(),
            paid_at timestamptz
        );
        CREATE TABLE IF NOT EXISTS clinic_insurance_claims (
            id varchar(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
            tenant_id uuid NOT NULL,
            claim_ref varchar(32) NOT NULL,
            patient_id varchar(36) NOT NULL,
            patient_name varchar(128) NOT NULL,
            invoice_id varchar(36),
            insurance_provider varchar(128) NOT NULL,
            policy_no varchar(64) NOT NULL DEFAULT 'N/A',
            copay_percent double precision NOT NULL DEFAULT 0,
            claimed_amount double precision NOT NULL DEFAULT 0,
            approved_amount double precision NOT NULL DEFAULT 0,
            status varchar(32) NOT NULL DEFAULT 'submitted',
            submitted_at timestamptz NOT NULL DEFAULT now(),
            resolved_at timestamptz,
            notes text NOT NULL DEFAULT ''
        );
        -- RLS + tenant_id default
        ALTER TABLE clinic_invoices ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid;
        ALTER TABLE clinic_insurance_claims ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid;

        DELETE FROM clinic_appointments WHERE patient_id NOT IN (SELECT id FROM clinic_patients);
        DELETE FROM clinic_encounters WHERE patient_id NOT IN (SELECT id FROM clinic_patients);
        DELETE FROM clinic_prescriptions WHERE patient_id NOT IN (SELECT id FROM clinic_patients);
        DELETE FROM clinic_lab_orders WHERE patient_id NOT IN (SELECT id FROM clinic_patients);
        DELETE FROM clinic_invoices WHERE patient_id NOT IN (SELECT id FROM clinic_patients);
        DELETE FROM clinic_insurance_claims WHERE patient_id NOT IN (SELECT id FROM clinic_patients);

        DO $fn$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_clinic_appointments_patient') THEN
                ALTER TABLE clinic_appointments ADD CONSTRAINT fk_clinic_appointments_patient FOREIGN KEY (patient_id) REFERENCES clinic_patients(id) ON DELETE CASCADE;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_clinic_encounters_patient') THEN
                ALTER TABLE clinic_encounters ADD CONSTRAINT fk_clinic_encounters_patient FOREIGN KEY (patient_id) REFERENCES clinic_patients(id) ON DELETE CASCADE;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_clinic_prescriptions_patient') THEN
                ALTER TABLE clinic_prescriptions ADD CONSTRAINT fk_clinic_prescriptions_patient FOREIGN KEY (patient_id) REFERENCES clinic_patients(id) ON DELETE CASCADE;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_clinic_lab_orders_patient') THEN
                ALTER TABLE clinic_lab_orders ADD CONSTRAINT fk_clinic_lab_orders_patient FOREIGN KEY (patient_id) REFERENCES clinic_patients(id) ON DELETE CASCADE;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_clinic_invoices_patient') THEN
                ALTER TABLE clinic_invoices ADD CONSTRAINT fk_clinic_invoices_patient FOREIGN KEY (patient_id) REFERENCES clinic_patients(id) ON DELETE CASCADE;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_clinic_claims_patient') THEN
                ALTER TABLE clinic_insurance_claims ADD CONSTRAINT fk_clinic_claims_patient FOREIGN KEY (patient_id) REFERENCES clinic_patients(id) ON DELETE CASCADE;
            END IF;
        END
        $fn$;
    """),
    # v37 — rename module id 'clinic' -> 'healthcare_clinic' (naming convention pilot)
    ("v37_rename_clinic_module", """
        UPDATE tenants SET active_modules = (
            SELECT jsonb_agg(CASE WHEN elem = 'clinic' THEN 'healthcare_clinic' ELSE elem END)
            FROM jsonb_array_elements_text(active_modules) AS elem
        ) WHERE active_modules @> '["clinic"]'::jsonb;

        UPDATE store_settings SET value = (
            SELECT jsonb_agg(CASE WHEN elem = 'clinic' THEN 'healthcare_clinic' ELSE elem END)::text
            FROM jsonb_array_elements_text(value::jsonb) AS elem
        ) WHERE key = 'installed_modules' AND value::jsonb @> '["clinic"]'::jsonb;
    """),
    # v38 — RLS enforcement for healthcare & vertical module tables
    ("v38_module_rls", """
        DO $$
        DECLARE
            tbl text;
            tables text[] := ARRAY[
                'clinic_patients',
                'clinic_appointments',
                'clinic_encounters',
                'clinic_prescriptions',
                'clinic_lab_orders',
                'clinic_beds',
                'clinic_inpatient_beds',
                'clinic_invoices',
                'clinic_insurance_claims'
            ];
        BEGIN
            FOREACH tbl IN ARRAY tables LOOP
                IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = tbl) THEN
                    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY;', tbl);
                    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY;', tbl);
                    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = tbl AND policyname = 'tenant_isolation') THEN
                        EXECUTE format('
                            CREATE POLICY tenant_isolation ON %I
                            USING (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid OR current_setting(''app.bypass'', true) = ''on'')
                            WITH CHECK (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid OR current_setting(''app.bypass'', true) = ''on'');
                        ', tbl);
                    END IF;
                END IF;
            END LOOP;
        END $$;
    """),
    # v39 — RLS enforcement for clinic inpatient beds
    ("v39_inpatient_beds_rls", """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'clinic_inpatient_beds') THEN
                ALTER TABLE clinic_inpatient_beds ENABLE ROW LEVEL SECURITY;
                ALTER TABLE clinic_inpatient_beds FORCE ROW LEVEL SECURITY;
                IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'clinic_inpatient_beds' AND policyname = 'tenant_isolation') THEN
                    CREATE POLICY tenant_isolation ON clinic_inpatient_beds
                        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
                        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
                END IF;
            END IF;
        END $$;
    """),
    # v40 — Standalone Healthcare ERP 24 Modules tables and RLS enforcement
    ("v40_healthcare_standalone_suite", """
        CREATE TABLE IF NOT EXISTS hlt_facilities (
            id SERIAL PRIMARY KEY,
            tenant_id uuid NOT NULL,
            name VARCHAR(150) NOT NULL,
            name_en VARCHAR(150),
            code VARCHAR(50) NOT NULL,
            facility_type VARCHAR(50) DEFAULT 'clinic',
            phone VARCHAR(50),
            email VARCHAR(100),
            license_no VARCHAR(100),
            accreditation VARCHAR(100),
            currency VARCHAR(10) DEFAULT 'SAR',
            operating_hours JSONB,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS hlt_departments (
            id SERIAL PRIMARY KEY,
            tenant_id uuid NOT NULL,
            facility_id INTEGER NOT NULL REFERENCES hlt_facilities(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            name_en VARCHAR(100),
            code VARCHAR(50) NOT NULL,
            dept_type VARCHAR(50) DEFAULT 'outpatient',
            floor VARCHAR(50),
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS hlt_patients (
            id SERIAL PRIMARY KEY,
            tenant_id uuid NOT NULL,
            mrn VARCHAR(50) NOT NULL,
            national_id VARCHAR(50),
            first_name VARCHAR(100) NOT NULL,
            last_name VARCHAR(100) NOT NULL,
            date_of_birth DATE,
            gender VARCHAR(20) DEFAULT 'unknown',
            phone VARCHAR(50) NOT NULL,
            email VARCHAR(100),
            blood_group VARCHAR(10),
            emergency_contact_name VARCHAR(100),
            emergency_contact_phone VARCHAR(50),
            guardian_name VARCHAR(100),
            is_merged BOOLEAN DEFAULT FALSE,
            merged_into_id INTEGER,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS hlt_appointments (
            id SERIAL PRIMARY KEY,
            tenant_id uuid NOT NULL,
            appointment_number VARCHAR(50) NOT NULL,
            patient_id INTEGER NOT NULL,
            doctor_id INTEGER NOT NULL,
            department_id INTEGER,
            service_type VARCHAR(50) DEFAULT 'consultation',
            appointment_date DATE NOT NULL,
            start_time VARCHAR(20) NOT NULL,
            end_time VARCHAR(20),
            status VARCHAR(30) DEFAULT 'scheduled',
            cancellation_reason TEXT,
            queue_number INTEGER,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS hlt_medical_staff (
            id SERIAL PRIMARY KEY,
            tenant_id uuid NOT NULL,
            staff_type VARCHAR(50) DEFAULT 'physician',
            first_name VARCHAR(100) NOT NULL,
            last_name VARCHAR(100) NOT NULL,
            specialty VARCHAR(100) NOT NULL,
            license_number VARCHAR(100),
            license_expiry DATE,
            consultation_fee NUMERIC(10, 2) DEFAULT 0.0,
            commission_rate NUMERIC(5, 2) DEFAULT 0.0,
            phone VARCHAR(50),
            email VARCHAR(100),
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS hlt_patient_vitals (
            id SERIAL PRIMARY KEY,
            tenant_id uuid NOT NULL,
            patient_id INTEGER NOT NULL,
            systolic_bp INTEGER,
            diastolic_bp INTEGER,
            pulse_rate INTEGER,
            temperature NUMERIC(4, 1),
            respiratory_rate INTEGER,
            oxygen_saturation INTEGER,
            height_cm NUMERIC(5, 1),
            weight_kg NUMERIC(5, 1),
            bmi NUMERIC(4, 1),
            recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS hlt_patient_allergies (
            id SERIAL PRIMARY KEY,
            tenant_id uuid NOT NULL,
            patient_id INTEGER NOT NULL,
            allergen VARCHAR(150) NOT NULL,
            allergy_type VARCHAR(50) DEFAULT 'medication',
            severity VARCHAR(50) DEFAULT 'moderate',
            reaction VARCHAR(200),
            is_active BOOLEAN DEFAULT TRUE
        );
        CREATE TABLE IF NOT EXISTS hlt_clinical_encounters (
            id SERIAL PRIMARY KEY,
            tenant_id uuid NOT NULL,
            encounter_number VARCHAR(50) NOT NULL,
            patient_id INTEGER NOT NULL,
            doctor_id INTEGER NOT NULL,
            chief_complaint TEXT NOT NULL,
            examination TEXT,
            diagnosis VARCHAR(255),
            icd10_code VARCHAR(50),
            treatment_plan TEXT,
            status VARCHAR(30) DEFAULT 'draft',
            signed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS hlt_inpatient_admissions (
            id SERIAL PRIMARY KEY,
            tenant_id uuid NOT NULL,
            admission_number VARCHAR(50) NOT NULL,
            patient_id INTEGER NOT NULL,
            doctor_id INTEGER NOT NULL,
            ward_id INTEGER,
            bed_id INTEGER,
            admission_date TIMESTAMPTZ NOT NULL DEFAULT now(),
            discharge_date TIMESTAMPTZ,
            admission_reason TEXT NOT NULL,
            discharge_summary TEXT,
            status VARCHAR(30) DEFAULT 'admitted'
        );
        CREATE TABLE IF NOT EXISTS hlt_hospital_wards (
            id SERIAL PRIMARY KEY,
            tenant_id uuid NOT NULL,
            name VARCHAR(100) NOT NULL,
            code VARCHAR(50) NOT NULL,
            ward_type VARCHAR(50) DEFAULT 'general',
            floor VARCHAR(50),
            is_active BOOLEAN DEFAULT TRUE
        );
        CREATE TABLE IF NOT EXISTS hlt_hospital_beds (
            id SERIAL PRIMARY KEY,
            tenant_id uuid NOT NULL,
            ward_id INTEGER NOT NULL REFERENCES hlt_hospital_wards(id) ON DELETE CASCADE,
            bed_number VARCHAR(50) NOT NULL,
            bed_type VARCHAR(50) DEFAULT 'standard',
            daily_rate NUMERIC(10, 2) DEFAULT 0.0,
            status VARCHAR(30) DEFAULT 'available',
            current_patient_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS hlt_mar_records (
            id SERIAL PRIMARY KEY,
            tenant_id uuid NOT NULL,
            patient_id INTEGER NOT NULL,
            medication_name VARCHAR(150) NOT NULL,
            dosage VARCHAR(50) NOT NULL,
            route VARCHAR(30) DEFAULT 'oral',
            scheduled_time VARCHAR(30) NOT NULL,
            status VARCHAR(30) DEFAULT 'given',
            nurse_notes TEXT,
            administered_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS hlt_lab_catalog (
            id SERIAL PRIMARY KEY,
            tenant_id uuid NOT NULL,
            code VARCHAR(50) NOT NULL,
            name VARCHAR(150) NOT NULL,
            category VARCHAR(50) DEFAULT 'biochemistry',
            sample_type VARCHAR(50) DEFAULT 'blood',
            unit VARCHAR(30),
            normal_range VARCHAR(100),
            price NUMERIC(10, 2) DEFAULT 0.0
        );
        CREATE TABLE IF NOT EXISTS hlt_lab_specimens (
            id SERIAL PRIMARY KEY,
            tenant_id uuid NOT NULL,
            barcode VARCHAR(50) NOT NULL,
            patient_id INTEGER NOT NULL,
            test_id INTEGER NOT NULL,
            result_value VARCHAR(100),
            is_abnormal BOOLEAN DEFAULT FALSE,
            is_critical BOOLEAN DEFAULT FALSE,
            status VARCHAR(30) DEFAULT 'collected',
            completed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS hlt_radiology_orders (
            id SERIAL PRIMARY KEY,
            tenant_id uuid NOT NULL,
            order_number VARCHAR(50) NOT NULL,
            patient_id INTEGER NOT NULL,
            doctor_id INTEGER NOT NULL,
            modality VARCHAR(20) NOT NULL,
            body_part VARCHAR(100) NOT NULL,
            clinical_notes TEXT,
            findings TEXT,
            status VARCHAR(30) DEFAULT 'scheduled',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS hlt_pharmacy_formulary (
            id SERIAL PRIMARY KEY,
            tenant_id uuid NOT NULL,
            code VARCHAR(50) NOT NULL,
            trade_name VARCHAR(150) NOT NULL,
            generic_name VARCHAR(150) NOT NULL,
            dosage_form VARCHAR(50) DEFAULT 'tablet',
            strength VARCHAR(50),
            unit_price NUMERIC(10, 2) DEFAULT 0.0,
            stock_qty INTEGER DEFAULT 0,
            is_controlled BOOLEAN DEFAULT FALSE
        );
        CREATE TABLE IF NOT EXISTS hlt_prescription_dispense (
            id SERIAL PRIMARY KEY,
            tenant_id uuid NOT NULL,
            patient_id INTEGER NOT NULL,
            medication_id INTEGER NOT NULL,
            quantity INTEGER DEFAULT 1,
            dispensed_by VARCHAR(100),
            dispensed_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS hlt_emergency_admissions (
            id SERIAL PRIMARY KEY,
            tenant_id uuid NOT NULL,
            case_number VARCHAR(50) NOT NULL,
            patient_id INTEGER NOT NULL,
            triage_level INTEGER DEFAULT 3,
            chief_complaint TEXT NOT NULL,
            arrival_mode VARCHAR(50) DEFAULT 'walk_in',
            assigned_bay VARCHAR(50),
            status VARCHAR(30) DEFAULT 'triaged',
            arrived_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS hlt_surgical_cases (
            id SERIAL PRIMARY KEY,
            tenant_id uuid NOT NULL,
            case_number VARCHAR(50) NOT NULL,
            patient_id INTEGER NOT NULL,
            surgeon_id INTEGER NOT NULL,
            theater_name VARCHAR(50) NOT NULL,
            procedure_name VARCHAR(200) NOT NULL,
            scheduled_date DATE NOT NULL,
            who_checklist_completed BOOLEAN DEFAULT FALSE,
            status VARCHAR(30) DEFAULT 'scheduled',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS hlt_patient_invoices (
            id SERIAL PRIMARY KEY,
            tenant_id uuid NOT NULL,
            invoice_number VARCHAR(50) NOT NULL,
            patient_id INTEGER NOT NULL,
            total_amount NUMERIC(10, 2) DEFAULT 0.0,
            insurance_share NUMERIC(10, 2) DEFAULT 0.0,
            patient_share NUMERIC(10, 2) DEFAULT 0.0,
            paid_amount NUMERIC(10, 2) DEFAULT 0.0,
            payment_status VARCHAR(30) DEFAULT 'unpaid',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS hlt_insurance_claims (
            id SERIAL PRIMARY KEY,
            tenant_id uuid NOT NULL,
            claim_number VARCHAR(50) NOT NULL,
            provider_name VARCHAR(100) NOT NULL,
            patient_id INTEGER NOT NULL,
            claimed_amount NUMERIC(10, 2) DEFAULT 0.0,
            approved_amount NUMERIC(10, 2) DEFAULT 0.0,
            status VARCHAR(30) DEFAULT 'submitted',
            rejection_reason TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS hlt_medical_items (
            id SERIAL PRIMARY KEY,
            tenant_id uuid NOT NULL,
            item_code VARCHAR(50) NOT NULL,
            name VARCHAR(150) NOT NULL,
            category VARCHAR(50) DEFAULT 'consumable',
            unit VARCHAR(30) DEFAULT 'piece',
            stock_qty INTEGER DEFAULT 0,
            min_alert_qty INTEGER DEFAULT 10,
            cost_price NUMERIC(10, 2) DEFAULT 0.0
        );
        CREATE TABLE IF NOT EXISTS hlt_cost_centers (
            id SERIAL PRIMARY KEY,
            tenant_id uuid NOT NULL,
            code VARCHAR(50) NOT NULL,
            name VARCHAR(100) NOT NULL,
            center_type VARCHAR(50) DEFAULT 'cost_center',
            budget NUMERIC(12, 2) DEFAULT 0.0,
            actual_spent NUMERIC(12, 2) DEFAULT 0.0
        );
        CREATE TABLE IF NOT EXISTS hlt_clinical_credentials (
            id SERIAL PRIMARY KEY,
            tenant_id uuid NOT NULL,
            staff_id INTEGER NOT NULL,
            credential_title VARCHAR(150) NOT NULL,
            issuing_authority VARCHAR(100) NOT NULL,
            expiry_date DATE NOT NULL,
            status VARCHAR(30) DEFAULT 'active'
        );
        CREATE TABLE IF NOT EXISTS hlt_biomedical_devices (
            id SERIAL PRIMARY KEY,
            tenant_id uuid NOT NULL,
            asset_tag VARCHAR(50) NOT NULL,
            device_name VARCHAR(150) NOT NULL,
            serial_number VARCHAR(100),
            department_name VARCHAR(100),
            last_calibration_date DATE,
            next_calibration_due DATE,
            status VARCHAR(30) DEFAULT 'operational'
        );
        CREATE TABLE IF NOT EXISTS hlt_portal_requests (
            id SERIAL PRIMARY KEY,
            tenant_id uuid NOT NULL,
            patient_id INTEGER NOT NULL,
            request_type VARCHAR(50) NOT NULL,
            details TEXT,
            status VARCHAR(30) DEFAULT 'submitted',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS hlt_teleconsultations (
            id SERIAL PRIMARY KEY,
            tenant_id uuid NOT NULL,
            session_id VARCHAR(100) NOT NULL,
            patient_id INTEGER NOT NULL,
            doctor_id INTEGER NOT NULL,
            scheduled_at TIMESTAMPTZ NOT NULL,
            meeting_link VARCHAR(255),
            status VARCHAR(30) DEFAULT 'waiting',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS hlt_alerts (
            id SERIAL PRIMARY KEY,
            tenant_id uuid NOT NULL,
            alert_type VARCHAR(50) NOT NULL,
            patient_id INTEGER,
            title VARCHAR(150) NOT NULL,
            message TEXT NOT NULL,
            priority VARCHAR(20) DEFAULT 'normal',
            is_read BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS hlt_daily_metrics (
            id SERIAL PRIMARY KEY,
            tenant_id uuid NOT NULL,
            metric_date DATE NOT NULL,
            total_visits INTEGER DEFAULT 0,
            admissions_count INTEGER DEFAULT 0,
            discharges_count INTEGER DEFAULT 0,
            bed_occupancy_rate NUMERIC(5, 2) DEFAULT 0.0,
            average_wait_minutes INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        -- Apply Row-Level Security (RLS) to all 24 healthcare tables
        DO $$
        DECLARE
            tbl text;
            tables text[] := ARRAY[
                'hlt_facilities', 'hlt_departments', 'hlt_patients', 'hlt_appointments',
                'hlt_medical_staff', 'hlt_patient_vitals', 'hlt_patient_allergies',
                'hlt_clinical_encounters', 'hlt_inpatient_admissions', 'hlt_hospital_wards',
                'hlt_hospital_beds', 'hlt_mar_records', 'hlt_lab_catalog', 'hlt_lab_specimens',
                'hlt_radiology_orders', 'hlt_pharmacy_formulary', 'hlt_prescription_dispense',
                'hlt_emergency_admissions', 'hlt_surgical_cases', 'hlt_patient_invoices',
                'hlt_insurance_claims', 'hlt_medical_items', 'hlt_cost_centers',
                'hlt_clinical_credentials', 'hlt_biomedical_devices', 'hlt_portal_requests',
                'hlt_teleconsultations', 'hlt_alerts', 'hlt_daily_metrics'
            ];
        BEGIN
            FOREACH tbl IN ARRAY tables LOOP
                IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = tbl) THEN
                    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY;', tbl);
                    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY;', tbl);
                    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = tbl AND policyname = 'tenant_isolation') THEN
                        EXECUTE format('
                            CREATE POLICY tenant_isolation ON %I
                            USING (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid OR current_setting(''app.bypass'', true) = ''on'')
                            WITH CHECK (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid OR current_setting(''app.bypass'', true) = ''on'');
                        ', tbl);
                    END IF;
                END IF;
            END LOOP;
        END $$;
    """),
    # v41 — Hospitality Suite (Banquets, Rooms, Housekeeping, Folios, Night Audit) RLS enforcement
    ("v41_hospitality_suite_rls", """
        CREATE TABLE IF NOT EXISTS hotel_banquet_events (
            id VARCHAR(36) PRIMARY KEY,
            tenant_id uuid NOT NULL DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid,
            booking_ref VARCHAR(32) NOT NULL,
            hall_name VARCHAR(128) NOT NULL,
            client_name VARCHAR(128) NOT NULL,
            client_phone VARCHAR(32) NOT NULL,
            event_type VARCHAR(64) NOT NULL,
            event_date VARCHAR(32) NOT NULL,
            start_time VARCHAR(32) NOT NULL,
            end_time VARCHAR(32) NOT NULL,
            guest_count INTEGER DEFAULT 100,
            catering_package VARCHAR(128) NOT NULL,
            total_amount DOUBLE PRECISION DEFAULT 0.0,
            deposit_amount DOUBLE PRECISION DEFAULT 0.0,
            status VARCHAR(32) DEFAULT 'confirmed',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        DO $$
        DECLARE
            tbl text;
            hotel_tables text[] := ARRAY[
                'hotel_rooms',
                'hotel_reservations',
                'hotel_folio_items',
                'hotel_housekeeping_tasks',
                'hotel_night_audits',
                'hotel_banquet_events'
            ];
        BEGIN
            FOREACH tbl IN ARRAY hotel_tables LOOP
                IF to_regclass('public.' || tbl) IS NOT NULL THEN
                    EXECUTE format('ALTER TABLE %I ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid;', tbl);
                    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%s_tenant ON %I (tenant_id);', tbl, tbl);
                    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY;', tbl);
                    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY;', tbl);
                    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = tbl AND policyname = 'tenant_isolation') THEN
                        EXECUTE format('
                            CREATE POLICY tenant_isolation ON %I
                            USING (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid OR current_setting(''app.bypass'', true) = ''on'')
                            WITH CHECK (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid OR current_setting(''app.bypass'', true) = ''on'');
                        ', tbl);
                    END IF;
                END IF;
            END LOOP;
        END $$;
    """),

    # v42 — Platform-wide RBAC & ABAC Suite (Positions, Account Types, Roles, Permissions, Overrides, Break-Glass & HIPAA Audit)
    ("v42_platform_rbac_abac_suite", """
        -- 1. Extend users with account_type
        ALTER TABLE users ADD COLUMN IF NOT EXISTS account_type VARCHAR(32) NOT NULL DEFAULT 'employee';

        -- 2. Positions Catalog (Job Titles A-I)
        CREATE TABLE IF NOT EXISTS org_positions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID,
            code VARCHAR(64) NOT NULL,
            name VARCHAR(128) NOT NULL,
            name_en VARCHAR(128) NOT NULL,
            category VARCHAR(64) NOT NULL,
            department_name VARCHAR(128),
            description TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE UNIQUE INDEX IF NOT EXISTS uq_position_code_tenant ON org_positions(code, COALESCE(tenant_id, '00000000-0000-0000-0000-000000000000'::uuid));
        CREATE INDEX IF NOT EXISTS idx_org_positions_cat ON org_positions(category);

        -- 3. Granular System Permissions Catalog
        CREATE TABLE IF NOT EXISTS sys_permissions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            code VARCHAR(64) UNIQUE NOT NULL,
            module VARCHAR(64) NOT NULL,
            action VARCHAR(32) NOT NULL,
            name VARCHAR(128) NOT NULL,
            name_en VARCHAR(128) NOT NULL,
            description TEXT,
            is_clinical BOOLEAN DEFAULT FALSE,
            data_sensitivity VARCHAR(32) DEFAULT 'normal',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_sys_permissions_module ON sys_permissions(module);

        -- 4. Roles (RBAC)
        CREATE TABLE IF NOT EXISTS sys_roles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID,
            code VARCHAR(64) NOT NULL,
            name VARCHAR(128) NOT NULL,
            name_en VARCHAR(128) NOT NULL,
            description TEXT,
            is_system BOOLEAN DEFAULT FALSE,
            is_clinical BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE UNIQUE INDEX IF NOT EXISTS uq_sys_role_code_tenant ON sys_roles(code, COALESCE(tenant_id, '00000000-0000-0000-0000-000000000000'::uuid));

        -- 5. Role Permissions Junction
        CREATE TABLE IF NOT EXISTS sys_role_permissions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            role_id UUID NOT NULL REFERENCES sys_roles(id) ON DELETE CASCADE,
            permission_id UUID NOT NULL REFERENCES sys_permissions(id) ON DELETE CASCADE,
            CONSTRAINT uq_role_permission UNIQUE (role_id, permission_id)
        );

        -- 6. User Position Assignment
        CREATE TABLE IF NOT EXISTS user_positions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            position_id UUID NOT NULL REFERENCES org_positions(id) ON DELETE CASCADE,
            department_id INTEGER,
            department_name VARCHAR(128),
            start_date DATE DEFAULT CURRENT_DATE,
            end_date DATE,
            is_primary BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        -- 7. User Role Assignments (with ABAC facility and department scope)
        CREATE TABLE IF NOT EXISTS user_role_assignments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role_id UUID NOT NULL REFERENCES sys_roles(id) ON DELETE CASCADE,
            facility_id INTEGER,
            department_id INTEGER,
            valid_from TIMESTAMPTZ,
            valid_until TIMESTAMPTZ,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        -- 8. User Facility Assignments (Physical ABAC boundary)
        CREATE TABLE IF NOT EXISTS user_facility_assignments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            facility_id INTEGER NOT NULL,
            facility_name VARCHAR(150) NOT NULL,
            department_id INTEGER,
            department_name VARCHAR(150),
            is_primary BOOLEAN DEFAULT TRUE,
            can_switch_facility BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        -- 9. Explicit User Permission Overrides
        CREATE TABLE IF NOT EXISTS user_permission_overrides (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            permission_id UUID NOT NULL REFERENCES sys_permissions(id) ON DELETE CASCADE,
            override_type VARCHAR(16) NOT NULL,
            reason TEXT,
            granted_by UUID REFERENCES users(id),
            expires_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_user_perm_override UNIQUE (user_id, permission_id)
        );

        -- 10. Patient Access Assignments (ABAC Patient Boundary)
        CREATE TABLE IF NOT EXISTS patient_access_assignments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            patient_id INTEGER NOT NULL,
            encounter_id INTEGER,
            admission_id INTEGER,
            assignment_type VARCHAR(32) DEFAULT 'primary_physician',
            access_level VARCHAR(32) DEFAULT 'full',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        -- 11. Temporary Access Grants (Emergency Break-Glass & Delegation)
        CREATE TABLE IF NOT EXISTS temporary_access_grants (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            target_patient_id INTEGER,
            target_facility_id INTEGER,
            grant_reason TEXT NOT NULL,
            granted_role_id UUID REFERENCES sys_roles(id),
            granted_permissions JSONB DEFAULT '[]'::jsonb,
            authorized_by UUID REFERENCES users(id),
            starts_at TIMESTAMPTZ DEFAULT now(),
            expires_at TIMESTAMPTZ NOT NULL,
            is_revoked BOOLEAN DEFAULT FALSE,
            revoked_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        -- 12. User Access Audit Log (HIPAA/GDPR Grade)
        CREATE TABLE IF NOT EXISTS user_access_audits (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            account_type VARCHAR(32) DEFAULT 'employee',
            action VARCHAR(64) NOT NULL,
            resource_type VARCHAR(64) NOT NULL,
            resource_id VARCHAR(64),
            is_clinical BOOLEAN DEFAULT FALSE,
            decision VARCHAR(16) DEFAULT 'granted',
            facility_id INTEGER,
            department_id INTEGER,
            ip_address VARCHAR(64),
            user_agent TEXT,
            details JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        -- 13. Tenant Isolation & Row-Level Security Policies
        DO $$
        DECLARE
            tbl text;
            authz_tables text[] := ARRAY[
                'user_positions',
                'user_role_assignments',
                'user_facility_assignments',
                'user_permission_overrides',
                'patient_access_assignments',
                'temporary_access_grants',
                'user_access_audits'
            ];
        BEGIN
            FOREACH tbl IN ARRAY authz_tables LOOP
                IF to_regclass('public.' || tbl) IS NOT NULL THEN
                    EXECUTE format('ALTER TABLE %I ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid;', tbl);
                    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%s_tenant ON %I (tenant_id);', tbl, tbl);
                    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY;', tbl);
                    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY;', tbl);
                    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = tbl AND policyname = 'tenant_isolation') THEN
                        EXECUTE format('
                            CREATE POLICY tenant_isolation ON %I
                            USING (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid OR current_setting(''app.bypass'', true) = ''on'')
                            WITH CHECK (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid OR current_setting(''app.bypass'', true) = ''on'');
                        ', tbl);
                    END IF;
                END IF;
            END LOOP;
        END $$;
    """),
    # v45 — DB-01: Global Row Level Security enforcement across ALL tenant-scoped tables
    ("v45_global_tenant_rls_enforcement", """
        DO $$
        DECLARE
            rec RECORD;
        BEGIN
            FOR rec IN
                SELECT c.table_name
                FROM information_schema.columns c
                JOIN information_schema.tables t 
                  ON t.table_name = c.table_name 
                 AND t.table_schema = c.table_schema
                WHERE c.table_schema = 'public'
                  AND c.column_name = 'tenant_id'
                  AND t.table_type = 'BASE TABLE'
            LOOP
                EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY;', rec.table_name);
                EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY;', rec.table_name);
                IF NOT EXISTS (
                    SELECT 1 FROM pg_policies 
                    WHERE schemaname = 'public' 
                      AND tablename = rec.table_name 
                      AND policyname = 'tenant_isolation'
                ) THEN
                    EXECUTE format('
                        CREATE POLICY tenant_isolation ON %I
                        USING (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid OR current_setting(''app.bypass'', true) = ''on'')
                        WITH CHECK (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid OR current_setting(''app.bypass'', true) = ''on'');
                    ', rec.table_name);
                END IF;
            END LOOP;
        END $$;
    """),
    # v46 — products reorder_level column
    ("v46_products_reorder_level", """
        ALTER TABLE products ADD COLUMN IF NOT EXISTS reorder_level INTEGER NOT NULL DEFAULT 5;
    """),
    # v47 — owner accounts (one owner, many workspaces) and gateway payment log.
    # Backfills one owner account per existing workspace from its first admin,
    # reusing that admin's username and password.
    ("v47_owner_accounts", """
        CREATE TABLE IF NOT EXISTS owner_accounts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            login varchar(64) NOT NULL UNIQUE,
            full_name varchar(128) NOT NULL,
            email varchar(254),
            phone varchar(32),
            password_hash varchar(256) NOT NULL,
            is_active boolean NOT NULL DEFAULT true,
            settings jsonb NOT NULL DEFAULT '{}'::jsonb,
            last_login_at timestamptz,
            created_at timestamptz DEFAULT now()
        );
        ALTER TABLE tenants ADD COLUMN IF NOT EXISTS owner_account_id uuid REFERENCES owner_accounts(id) ON DELETE SET NULL;
        CREATE INDEX IF NOT EXISTS ix_tenants_owner_account_id ON tenants (owner_account_id);
        ALTER TABLE users ADD COLUMN IF NOT EXISTS owner_account_id uuid REFERENCES owner_accounts(id) ON DELETE SET NULL;
        CREATE TABLE IF NOT EXISTS payment_transactions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            provider varchar(32) NOT NULL,
            event_key varchar(128) NOT NULL UNIQUE,
            provider_txn_id varchar(64) NOT NULL,
            invoice_id uuid REFERENCES tenant_billing_invoices(id) ON DELETE SET NULL,
            state varchar(16) NOT NULL,
            amount_cents integer NOT NULL DEFAULT 0,
            currency varchar(8) NOT NULL DEFAULT 'EGP',
            raw jsonb NOT NULL DEFAULT '{}'::jsonb,
            created_at timestamptz DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS ix_payment_transactions_provider_txn_id ON payment_transactions (provider_txn_id);
        CREATE INDEX IF NOT EXISTS ix_payment_transactions_invoice_id ON payment_transactions (invoice_id);
        DO $$
        DECLARE
            r RECORD;
            new_id uuid;
            candidate text;
            n int;
        BEGIN
            PERFORM set_config('app.bypass', 'on', true);
            FOR r IN
                SELECT DISTINCT ON (u.tenant_id) u.id AS user_id, u.tenant_id, u.username, u.full_name, u.password_hash
                FROM users u JOIN tenants t ON t.id = u.tenant_id
                WHERE t.owner_account_id IS NULL AND u.is_active AND u.role = 'admin'
                  AND NOT COALESCE(u.is_superadmin, false)
                ORDER BY u.tenant_id, u.created_at
            LOOP
                candidate := lower(r.username);
                n := 1;
                WHILE EXISTS (SELECT 1 FROM owner_accounts WHERE login = candidate) LOOP
                    n := n + 1;
                    candidate := lower(r.username) || '-' || n;
                END LOOP;
                new_id := gen_random_uuid();
                INSERT INTO owner_accounts (id, login, full_name, password_hash)
                VALUES (new_id, candidate, r.full_name, r.password_hash);
                UPDATE tenants SET owner_account_id = new_id WHERE id = r.tenant_id;
                UPDATE users SET owner_account_id = new_id WHERE id = r.user_id;
            END LOOP;
        END $$;
    """),
    # v48 — licences and installations for single-device and LAN workspaces (ADR-005).
    ("v48_licences_and_installations", """
        CREATE TABLE IF NOT EXISTS licences (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL UNIQUE REFERENCES tenants(id) ON DELETE CASCADE,
            mode varchar(16) NOT NULL,
            valid_until timestamptz NOT NULL,
            revoked_at timestamptz,
            created_at timestamptz DEFAULT now(),
            updated_at timestamptz DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS installations (
            id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            licence_id uuid NOT NULL REFERENCES licences(id) ON DELETE CASCADE,
            mode varchar(16) NOT NULL,
            hostname varchar(128),
            os varchar(64),
            app_version varchar(32),
            last_ip varchar(45),
            last_backup_at timestamptz,
            first_seen_at timestamptz DEFAULT now(),
            last_seen_at timestamptz DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS ix_installations_tenant_id ON installations (tenant_id);
        ALTER TABLE licences ENABLE ROW LEVEL SECURITY;
        ALTER TABLE licences FORCE ROW LEVEL SECURITY;
        CREATE POLICY tenant_isolation ON licences
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
        ALTER TABLE installations ENABLE ROW LEVEL SECURITY;
        ALTER TABLE installations FORCE ROW LEVEL SECURITY;
        CREATE POLICY tenant_isolation ON installations
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
    """),
    # Workspace isolation (#112): requests bound to a workspace run as mizan_app (SET LOCAL ROLE,
    # app/core/tenancy.py), which cannot bypass RLS, unlike the login role (Neon's owner, or a
    # local superuser). It gets the login role's data rights, now and for tables made later.
    ("v48b_rls_app_role", """
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mizan_app') THEN
                CREATE ROLE mizan_app NOLOGIN NOBYPASSRLS;
            END IF;
        END $$;
        DO $$ BEGIN
            EXECUTE format('GRANT mizan_app TO %I', current_user);
        END $$;
        GRANT USAGE ON SCHEMA public TO mizan_app;
        GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES ON ALL TABLES IN SCHEMA public TO mizan_app;
        GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO mizan_app;
        GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO mizan_app;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES ON TABLES TO mizan_app;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO mizan_app;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO mizan_app;
    """),
    # Codes a workspace types or numbers itself (and the modules' demo seeds) were unique
    # across all workspaces: the second pharmacy to write prescription RX-0001, or the
    # second workspace to seed a module's demo data, got a 500.
    ("v49_tenant_scoped_unique_codes", """
        DO $$ BEGIN
        IF to_regclass('public.school_students') IS NOT NULL THEN
            DROP INDEX IF EXISTS ix_school_students_code;
            CREATE INDEX IF NOT EXISTS ix_school_students_code ON school_students (code);
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_school_students_code') THEN
                ALTER TABLE school_students ADD CONSTRAINT uq_school_students_code UNIQUE (tenant_id, code);
            END IF;
        END IF;
        IF to_regclass('public.pharmacy_prescriptions') IS NOT NULL THEN
            DROP INDEX IF EXISTS ix_pharmacy_prescriptions_rx_number;
            CREATE INDEX IF NOT EXISTS ix_pharmacy_prescriptions_rx_number ON pharmacy_prescriptions (rx_number);
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_pharmacy_prescriptions_rx_number') THEN
                ALTER TABLE pharmacy_prescriptions ADD CONSTRAINT uq_pharmacy_prescriptions_rx_number UNIQUE (tenant_id, rx_number);
            END IF;
        END IF;
        IF to_regclass('public.logistics_vehicles') IS NOT NULL THEN
            DROP INDEX IF EXISTS ix_logistics_vehicles_plate_number;
            CREATE INDEX IF NOT EXISTS ix_logistics_vehicles_plate_number ON logistics_vehicles (plate_number);
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_logistics_vehicles_plate_number') THEN
                ALTER TABLE logistics_vehicles ADD CONSTRAINT uq_logistics_vehicles_plate_number UNIQUE (tenant_id, plate_number);
            END IF;
        END IF;
        IF to_regclass('public.logistics_route_trips') IS NOT NULL THEN
            DROP INDEX IF EXISTS ix_logistics_route_trips_trip_code;
            CREATE INDEX IF NOT EXISTS ix_logistics_route_trips_trip_code ON logistics_route_trips (trip_code);
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_logistics_route_trips_trip_code') THEN
                ALTER TABLE logistics_route_trips ADD CONSTRAINT uq_logistics_route_trips_trip_code UNIQUE (tenant_id, trip_code);
            END IF;
        END IF;
        IF to_regclass('public.ecom_order_fulfillments') IS NOT NULL THEN
            DROP INDEX IF EXISTS ix_ecom_order_fulfillments_order_number;
            CREATE INDEX IF NOT EXISTS ix_ecom_order_fulfillments_order_number ON ecom_order_fulfillments (order_number);
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_ecom_order_fulfillments_order_number') THEN
                ALTER TABLE ecom_order_fulfillments ADD CONSTRAINT uq_ecom_order_fulfillments_order_number UNIQUE (tenant_id, order_number);
            END IF;
        END IF;
        IF to_regclass('public.wms_bin_locations') IS NOT NULL THEN
            DROP INDEX IF EXISTS ix_wms_bin_locations_bin_code;
            CREATE INDEX IF NOT EXISTS ix_wms_bin_locations_bin_code ON wms_bin_locations (bin_code);
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_wms_bin_locations_bin_code') THEN
                ALTER TABLE wms_bin_locations ADD CONSTRAINT uq_wms_bin_locations_bin_code UNIQUE (tenant_id, bin_code);
            END IF;
        END IF;
        IF to_regclass('public.wms_client_accounts') IS NOT NULL THEN
            DROP INDEX IF EXISTS ix_wms_client_accounts_client_code;
            CREATE INDEX IF NOT EXISTS ix_wms_client_accounts_client_code ON wms_client_accounts (client_code);
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_wms_client_accounts_client_code') THEN
                ALTER TABLE wms_client_accounts ADD CONSTRAINT uq_wms_client_accounts_client_code UNIQUE (tenant_id, client_code);
            END IF;
        END IF;
        IF to_regclass('public.wms_cross_dock_orders') IS NOT NULL THEN
            DROP INDEX IF EXISTS ix_wms_cross_dock_orders_cross_dock_code;
            CREATE INDEX IF NOT EXISTS ix_wms_cross_dock_orders_cross_dock_code ON wms_cross_dock_orders (cross_dock_code);
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_wms_cross_dock_orders_cross_dock_code') THEN
                ALTER TABLE wms_cross_dock_orders ADD CONSTRAINT uq_wms_cross_dock_orders_cross_dock_code UNIQUE (tenant_id, cross_dock_code);
            END IF;
        END IF;
        IF to_regclass('public.wms_picking_waves') IS NOT NULL THEN
            DROP INDEX IF EXISTS ix_wms_picking_waves_wave_number;
            CREATE INDEX IF NOT EXISTS ix_wms_picking_waves_wave_number ON wms_picking_waves (wave_number);
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_wms_picking_waves_wave_number') THEN
                ALTER TABLE wms_picking_waves ADD CONSTRAINT uq_wms_picking_waves_wave_number UNIQUE (tenant_id, wave_number);
            END IF;
        END IF;
        IF to_regclass('public.ecom_return_requests') IS NOT NULL THEN
            DROP INDEX IF EXISTS ix_ecom_return_requests_rma_number;
            CREATE INDEX IF NOT EXISTS ix_ecom_return_requests_rma_number ON ecom_return_requests (rma_number);
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_ecom_return_requests_rma_number') THEN
                ALTER TABLE ecom_return_requests ADD CONSTRAINT uq_ecom_return_requests_rma_number UNIQUE (tenant_id, rma_number);
            END IF;
        END IF;
        IF to_regclass('public.wms_billing_invoices') IS NOT NULL THEN
            DROP INDEX IF EXISTS ix_wms_billing_invoices_invoice_number;
            CREATE INDEX IF NOT EXISTS ix_wms_billing_invoices_invoice_number ON wms_billing_invoices (invoice_number);
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_wms_billing_invoices_invoice_number') THEN
                ALTER TABLE wms_billing_invoices ADD CONSTRAINT uq_wms_billing_invoices_invoice_number UNIQUE (tenant_id, invoice_number);
            END IF;
        END IF;
        IF to_regclass('public.logistics_consignments') IS NOT NULL THEN
            DROP INDEX IF EXISTS ix_logistics_consignments_tracking_number;
            CREATE INDEX IF NOT EXISTS ix_logistics_consignments_tracking_number ON logistics_consignments (tracking_number);
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_logistics_consignments_tracking_number') THEN
                ALTER TABLE logistics_consignments ADD CONSTRAINT uq_logistics_consignments_tracking_number UNIQUE (tenant_id, tracking_number);
            END IF;
        END IF;
        IF to_regclass('public.ecom_cod_reconciliations') IS NOT NULL THEN
            DROP INDEX IF EXISTS ix_ecom_cod_reconciliations_remittance_batch;
            CREATE INDEX IF NOT EXISTS ix_ecom_cod_reconciliations_remittance_batch ON ecom_cod_reconciliations (remittance_batch);
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_ecom_cod_reconciliations_remittance_batch') THEN
                ALTER TABLE ecom_cod_reconciliations ADD CONSTRAINT uq_ecom_cod_reconciliations_remittance_batch UNIQUE (tenant_id, remittance_batch);
            END IF;
        END IF;
        END $$;
    """),
    # A workspace's active modules lived in two places: the installed_modules setting (read
    # first by the ERP) and tenants.active_modules (written by the admin panel, read by
    # licences). The column is now the only one (ADR-006 phase 1); the setting wins, since
    # it is what the ERP has been enforcing.
    ("v50_active_modules_single_source", """
        UPDATE tenants t SET active_modules = m.mods
        FROM (
            SELECT tenant_id,
                   CASE WHEN value ~ '^\\s*\\[.*\\]\\s*$' THEN value::jsonb END AS mods
            FROM store_settings WHERE key = 'installed_modules'
        ) m
        WHERE m.tenant_id = t.id AND m.mods IS NOT NULL;
        DELETE FROM store_settings WHERE key = 'installed_modules';
    """),
    # Readable module ids (ADR-006 phase 1): prn → printing, agr → agriculture, …; the
    # manifest-only stubs (retail-pos, restaurant-pos, gym-pos, gym_fitness) map to the modules
    # they stood for. app/catalog/legacy_ids.json keeps the old ids working in code.
    ("v51_readable_module_ids", """
        UPDATE tenants t SET active_modules = (
            SELECT COALESCE(jsonb_agg(x.m ORDER BY x.pos), '[]'::jsonb)
            FROM (
                SELECT COALESCE(l.new_id, e.elem) AS m, MIN(e.ord) AS pos
                FROM jsonb_array_elements_text(t.active_modules) WITH ORDINALITY AS e(elem, ord)
                LEFT JOIN (VALUES
                ('agr', 'agriculture'),
                ('bnk', 'banking'),
                ('cst', 'construction'),
                ('eng', 'energy'),
                ('ent', 'events'),
                ('fod', 'food_manufacturing'),
                ('gov', 'government'),
                ('ins', 'insurance'),
                ('oil', 'oil_gas'),
                ('phm', 'pharma_manufacturing'),
                ('rec', 'real_estate'),
                ('prn', 'printing'),
                ('mfg', 'manufacturing'),
                ('retail-pos', 'pos'),
                ('restaurant-pos', 'restaurant'),
                ('gym-pos', 'gym'),
                ('gym_fitness', 'gym'),
                ('clinic', 'healthcare_clinic')
                ) AS l(old_id, new_id) ON l.old_id = e.elem
                GROUP BY 1
            ) x
        )
        WHERE t.active_modules ?| array['agr', 'bnk', 'cst', 'eng', 'ent', 'fod', 'gov', 'ins', 'oil', 'phm', 'rec', 'prn', 'mfg', 'retail-pos', 'restaurant-pos', 'gym-pos', 'gym_fitness', 'clinic'];
        UPDATE store_settings s SET key = 'mod_settings_' || l.new_id
        FROM (VALUES
                ('agr', 'agriculture'),
                ('bnk', 'banking'),
                ('cst', 'construction'),
                ('eng', 'energy'),
                ('ent', 'events'),
                ('fod', 'food_manufacturing'),
                ('gov', 'government'),
                ('ins', 'insurance'),
                ('oil', 'oil_gas'),
                ('phm', 'pharma_manufacturing'),
                ('rec', 'real_estate'),
                ('prn', 'printing'),
                ('mfg', 'manufacturing'),
                ('retail-pos', 'pos'),
                ('restaurant-pos', 'restaurant'),
                ('gym-pos', 'gym'),
                ('gym_fitness', 'gym'),
                ('clinic', 'healthcare_clinic')
        ) AS l(old_id, new_id)
        WHERE s.key = 'mod_settings_' || l.old_id
          AND NOT EXISTS (SELECT 1 FROM store_settings o WHERE o.tenant_id = s.tenant_id AND o.key = 'mod_settings_' || l.new_id);
    """),
    # Full names (ADR-006): one-word activity ids (discrete_mfg → manufacturing, oil_gas →
    # petroleum, …) and the hospital/hotel modules without hlt_/hot_ prefixes. Stored activities
    # (tenants.sector, business_type), module lists and module settings keys are rewritten;
    # app/catalog/legacy_ids.json keeps the old ids working in code.
    ("v52_full_activity_and_module_names", """
        UPDATE tenants t SET sector = l.new_id
        FROM (VALUES
                ('discrete_mfg', 'manufacturing'),
                ('food_mfg', 'food'),
                ('pharma_mfg', 'pharmaceuticals'),
                ('wms_3pl', 'warehousing'),
                ('law_firm', 'legal'),
                ('field_service', 'maintenance'),
                ('oil_gas', 'petroleum'),
                ('real_estate', 'property')
        ) AS l(old_id, new_id) WHERE t.sector = l.old_id;
        UPDATE tenants t SET business_type = l.new_id
        FROM (VALUES
                ('discrete_mfg', 'manufacturing'),
                ('food_mfg', 'food'),
                ('pharma_mfg', 'pharmaceuticals'),
                ('wms_3pl', 'warehousing'),
                ('law_firm', 'legal'),
                ('field_service', 'maintenance'),
                ('oil_gas', 'petroleum'),
                ('real_estate', 'property')
        ) AS l(old_id, new_id) WHERE t.business_type = l.old_id;
        UPDATE tenants t SET active_modules = (
            SELECT COALESCE(jsonb_agg(x.m ORDER BY x.pos), '[]'::jsonb)
            FROM (
                SELECT COALESCE(l.new_id, e.elem) AS m, MIN(e.ord) AS pos
                FROM jsonb_array_elements_text(t.active_modules) WITH ORDINALITY AS e(elem, ord)
                LEFT JOIN (VALUES
                ('hlt_accounting', 'medical_accounting'),
                ('hlt_admissions', 'admissions'),
                ('hlt_analytics', 'hospital_analytics'),
                ('hlt_appointments', 'appointments'),
                ('hlt_beds', 'beds'),
                ('hlt_billing', 'medical_billing'),
                ('hlt_consultation', 'consultation'),
                ('hlt_emergency', 'emergency'),
                ('hlt_emr', 'emr'),
                ('hlt_equipment_maintenance', 'equipment_maintenance'),
                ('hlt_facility_management', 'facility_management'),
                ('hlt_hr_workforce', 'medical_workforce'),
                ('hlt_insurance', 'health_insurance'),
                ('hlt_inventory_procurement', 'medical_supplies'),
                ('hlt_laboratory', 'laboratory'),
                ('hlt_medical_staff', 'medical_staff'),
                ('hlt_notifications', 'patient_notifications'),
                ('hlt_nursing', 'nursing'),
                ('hlt_patient_identity', 'patient_identity'),
                ('hlt_patient_portal', 'patient_portal'),
                ('hlt_pharmacy', 'hospital_pharmacy'),
                ('hlt_radiology', 'radiology'),
                ('hlt_surgery', 'surgery'),
                ('hlt_telemedicine', 'telemedicine'),
                ('hot_banquet_events', 'banquet_events'),
                ('hot_billing_folio', 'billing_folio'),
                ('hot_pms', 'hotel_pms'),
                ('hot_housekeeping', 'housekeeping'),
                ('hot_night_audit', 'night_audit')
                ) AS l(old_id, new_id) ON l.old_id = e.elem
                GROUP BY 1
            ) x
        )
        WHERE t.active_modules ?| array['hlt_accounting', 'hlt_admissions', 'hlt_analytics', 'hlt_appointments', 'hlt_beds', 'hlt_billing', 'hlt_consultation', 'hlt_emergency', 'hlt_emr', 'hlt_equipment_maintenance', 'hlt_facility_management', 'hlt_hr_workforce', 'hlt_insurance', 'hlt_inventory_procurement', 'hlt_laboratory', 'hlt_medical_staff', 'hlt_notifications', 'hlt_nursing', 'hlt_patient_identity', 'hlt_patient_portal', 'hlt_pharmacy', 'hlt_radiology', 'hlt_surgery', 'hlt_telemedicine', 'hot_banquet_events', 'hot_billing_folio', 'hot_pms', 'hot_housekeeping', 'hot_night_audit'];
        UPDATE store_settings s SET key = 'mod_settings_' || l.new_id
        FROM (VALUES
                ('hlt_accounting', 'medical_accounting'),
                ('hlt_admissions', 'admissions'),
                ('hlt_analytics', 'hospital_analytics'),
                ('hlt_appointments', 'appointments'),
                ('hlt_beds', 'beds'),
                ('hlt_billing', 'medical_billing'),
                ('hlt_consultation', 'consultation'),
                ('hlt_emergency', 'emergency'),
                ('hlt_emr', 'emr'),
                ('hlt_equipment_maintenance', 'equipment_maintenance'),
                ('hlt_facility_management', 'facility_management'),
                ('hlt_hr_workforce', 'medical_workforce'),
                ('hlt_insurance', 'health_insurance'),
                ('hlt_inventory_procurement', 'medical_supplies'),
                ('hlt_laboratory', 'laboratory'),
                ('hlt_medical_staff', 'medical_staff'),
                ('hlt_notifications', 'patient_notifications'),
                ('hlt_nursing', 'nursing'),
                ('hlt_patient_identity', 'patient_identity'),
                ('hlt_patient_portal', 'patient_portal'),
                ('hlt_pharmacy', 'hospital_pharmacy'),
                ('hlt_radiology', 'radiology'),
                ('hlt_surgery', 'surgery'),
                ('hlt_telemedicine', 'telemedicine'),
                ('hot_banquet_events', 'banquet_events'),
                ('hot_billing_folio', 'billing_folio'),
                ('hot_pms', 'hotel_pms'),
                ('hot_housekeeping', 'housekeeping'),
                ('hot_night_audit', 'night_audit')
        ) AS l(old_id, new_id)
        WHERE s.key = 'mod_settings_' || l.old_id
          AND NOT EXISTS (SELECT 1 FROM store_settings o WHERE o.tenant_id = s.tenant_id AND o.key = 'mod_settings_' || l.new_id);
    """),
    # One permission system (ADR-006 phase 3): roles hold their permissions (grants); a user acts
    # as one assigned role (active_role_id). Workspaces can read the platform's standard roles
    # (tenant_id NULL) but not change them.
    ("v53_roles_hold_permissions", """
        ALTER TABLE sys_roles ADD COLUMN IF NOT EXISTS grants jsonb NOT NULL DEFAULT '[]'::jsonb;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS active_role_id uuid REFERENCES sys_roles(id) ON DELETE SET NULL;
        CREATE UNIQUE INDEX IF NOT EXISTS uq_sys_roles_platform_code ON sys_roles (code) WHERE tenant_id IS NULL;
        DROP POLICY IF EXISTS tenant_isolation ON sys_roles;
        DROP POLICY IF EXISTS tenant_read ON sys_roles;
        DROP POLICY IF EXISTS tenant_write ON sys_roles;
        CREATE POLICY tenant_read ON sys_roles FOR SELECT
            USING (tenant_id IS NULL OR tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
        CREATE POLICY tenant_write ON sys_roles FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
    """),
    # Every user gets roles with exactly the access they had (Python: needs the permission catalogue).
    ("v54_users_get_roles", "python:app.platform.permissions.migrate:migrate_users"),
    # Production drift found by rehearsing on a production copy: columns the clinic audit
    # remediation added only through create_all (so every clinic screen using them failed in
    # production), and two codes still unique across all workspaces (a second pharmacy's demo
    # drugs, or closing a month another workspace had closed, failed with a 500).
    ("v55_production_drift", """
        ALTER TABLE clinic_appointments ADD COLUMN IF NOT EXISTS cancellation_reason VARCHAR(256);
        ALTER TABLE clinic_appointments ADD COLUMN IF NOT EXISTS created_by VARCHAR(128);
        ALTER TABLE clinic_appointments ADD COLUMN IF NOT EXISTS reschedule_count INTEGER DEFAULT 0 NOT NULL;
        ALTER TABLE clinic_appointments ADD COLUMN IF NOT EXISTS rescheduled_from VARCHAR(64);
        ALTER TABLE clinic_appointments ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL;
        ALTER TABLE clinic_appointments ADD COLUMN IF NOT EXISTS updated_by VARCHAR(128);
        ALTER TABLE clinic_encounters ADD COLUMN IF NOT EXISTS created_by VARCHAR(128);
        ALTER TABLE clinic_encounters ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL;
        ALTER TABLE clinic_encounters ADD COLUMN IF NOT EXISTS updated_by VARCHAR(128);
        ALTER TABLE clinic_inpatient_beds ADD COLUMN IF NOT EXISTS created_by VARCHAR(128);
        ALTER TABLE clinic_inpatient_beds ADD COLUMN IF NOT EXISTS current_patient_id VARCHAR(36);
        ALTER TABLE clinic_inpatient_beds ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL;
        ALTER TABLE clinic_inpatient_beds ADD COLUMN IF NOT EXISTS updated_by VARCHAR(128);
        ALTER TABLE clinic_insurance_claims ADD COLUMN IF NOT EXISTS created_by VARCHAR(128);
        ALTER TABLE clinic_invoices ADD COLUMN IF NOT EXISTS created_by VARCHAR(128);
        ALTER TABLE clinic_invoices ADD COLUMN IF NOT EXISTS paid_by VARCHAR(128);
        ALTER TABLE clinic_lab_orders ADD COLUMN IF NOT EXISTS collected_at TIMESTAMP WITH TIME ZONE;
        ALTER TABLE clinic_lab_orders ADD COLUMN IF NOT EXISTS created_by VARCHAR(128);
        ALTER TABLE clinic_lab_orders ADD COLUMN IF NOT EXISTS is_critical BOOLEAN DEFAULT false NOT NULL;
        ALTER TABLE clinic_lab_orders ADD COLUMN IF NOT EXISTS numeric_value FLOAT;
        ALTER TABLE clinic_lab_orders ADD COLUMN IF NOT EXISTS signed_off_at TIMESTAMP WITH TIME ZONE;
        ALTER TABLE clinic_lab_orders ADD COLUMN IF NOT EXISTS signed_off_by VARCHAR(128);
        ALTER TABLE clinic_lab_orders ADD COLUMN IF NOT EXISTS test_fee FLOAT DEFAULT 150.0 NOT NULL;
        ALTER TABLE clinic_lab_orders ADD COLUMN IF NOT EXISTS unit VARCHAR(32) DEFAULT '' NOT NULL;
        ALTER TABLE clinic_lab_orders ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL;
        ALTER TABLE clinic_lab_orders ADD COLUMN IF NOT EXISTS updated_by VARCHAR(128);
        ALTER TABLE clinic_patients ADD COLUMN IF NOT EXISTS created_by VARCHAR(128);
        ALTER TABLE clinic_patients ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL;
        ALTER TABLE clinic_patients ADD COLUMN IF NOT EXISTS updated_by VARCHAR(128);
        ALTER TABLE clinic_prescriptions ADD COLUMN IF NOT EXISTS created_by VARCHAR(128);
        ALTER TABLE clinic_prescriptions ADD COLUMN IF NOT EXISTS dispensed_at TIMESTAMP WITH TIME ZONE;
        ALTER TABLE clinic_prescriptions ADD COLUMN IF NOT EXISTS dispensed_by VARCHAR(128);
        ALTER TABLE clinic_prescriptions ADD COLUMN IF NOT EXISTS quantity INTEGER DEFAULT 1 NOT NULL;
        ALTER TABLE clinic_prescriptions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL;
        ALTER TABLE clinic_prescriptions ADD COLUMN IF NOT EXISTS updated_by VARCHAR(128);
        DO $$ BEGIN
        IF to_regclass('public.pharmacy_drugs') IS NOT NULL THEN
            DROP INDEX IF EXISTS ix_pharmacy_drugs_code;
            CREATE INDEX IF NOT EXISTS ix_pharmacy_drugs_code ON pharmacy_drugs (code);
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_pharmacy_drugs_tenant_code') THEN
                ALTER TABLE pharmacy_drugs ADD CONSTRAINT uq_pharmacy_drugs_tenant_code UNIQUE (tenant_id, code);
            END IF;
        END IF;
        IF to_regclass('public.accounting_periods') IS NOT NULL THEN
            DROP INDEX IF EXISTS ix_accounting_periods_month;
            CREATE INDEX IF NOT EXISTS ix_accounting_periods_month ON accounting_periods (month);
        END IF;
        END $$;
    """),
    # Real sign-out (#77): signed-out token ids are refused until they expire; a password change
    # or reset ends every session issued before it.
    ("v56_session_revocation", """
        CREATE TABLE IF NOT EXISTS revoked_tokens (
            jti varchar(64) PRIMARY KEY,
            expires_at timestamptz NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_revoked_tokens_expires_at ON revoked_tokens (expires_at);
        ALTER TABLE users ADD COLUMN IF NOT EXISTS tokens_valid_after timestamptz;
        ALTER TABLE owner_accounts ADD COLUMN IF NOT EXISTS tokens_valid_after timestamptz;
    """),
    # Paid periods end (#66): the end of the last paid period, from paid invoices.
    ("v57_tenants_paid_until", """
        ALTER TABLE tenants ADD COLUMN IF NOT EXISTS paid_until timestamptz;
        UPDATE tenants t SET paid_until = p.period_end
        FROM (SELECT tenant_id, max(period_end) AS period_end FROM tenant_billing_invoices
              WHERE status = 'paid' AND period_end IS NOT NULL GROUP BY tenant_id) p
        WHERE p.tenant_id = t.id AND t.plan <> 'trial' AND t.paid_until IS NULL;
    """),
    # Positions per activity (ADR-006 D4): standard positions have no workspace and belong to an
    # activity ('general' = every business); workspaces read them but only change their own.
    ("v58_standard_positions_readable", """
        ALTER TABLE org_positions ADD COLUMN IF NOT EXISTS activity varchar(48);
        -- The old catalogue (hospital titles shown to every workspace) is replaced by each
        -- activity's positions (app/activities/*/positions.json), synced by the app.
        DELETE FROM org_positions WHERE tenant_id IS NULL AND activity IS NULL;
        CREATE UNIQUE INDEX IF NOT EXISTS uq_org_positions_standard ON org_positions (activity, code) WHERE tenant_id IS NULL;
        DROP POLICY IF EXISTS tenant_isolation ON org_positions;
        DROP POLICY IF EXISTS tenant_read ON org_positions;
        DROP POLICY IF EXISTS tenant_write ON org_positions;
        CREATE POLICY tenant_read ON org_positions FOR SELECT
            USING (tenant_id IS NULL OR tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
        CREATE POLICY tenant_write ON org_positions FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
    """),
    # Standard positions are unique per (activity, code): the same title (plant_manager) exists in
    # several activities. The old index made codes unique across all standard positions.
    ("v59_positions_unique_per_activity", """
        ALTER TABLE org_positions DROP CONSTRAINT IF EXISTS uq_position_code_tenant;
        DROP INDEX IF EXISTS uq_position_code_tenant;
        CREATE UNIQUE INDEX IF NOT EXISTS uq_org_positions_workspace ON org_positions (tenant_id, code) WHERE tenant_id IS NOT NULL;
    """),
    # Fields variants and workspaces add to shared records (ADR-006 phase 4): their values in an
    # `extra` JSON column; a workspace's own fields and its changes in workspace_fields.
    ("v60_record_fields", """
        ALTER TABLE products ADD COLUMN IF NOT EXISTS extra jsonb NOT NULL DEFAULT '{}'::jsonb;
        ALTER TABLE sales ADD COLUMN IF NOT EXISTS extra jsonb NOT NULL DEFAULT '{}'::jsonb;
        ALTER TABLE sale_items ADD COLUMN IF NOT EXISTS extra jsonb NOT NULL DEFAULT '{}'::jsonb;
        ALTER TABLE customers ADD COLUMN IF NOT EXISTS extra jsonb NOT NULL DEFAULT '{}'::jsonb;
        ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS extra jsonb NOT NULL DEFAULT '{}'::jsonb;
        ALTER TABLE purchase_order_items ADD COLUMN IF NOT EXISTS extra jsonb NOT NULL DEFAULT '{}'::jsonb;
        CREATE TABLE IF NOT EXISTS workspace_fields (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE
                DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid,
            record varchar(32) NOT NULL,
            key varchar(48) NOT NULL,
            definition jsonb NOT NULL DEFAULT '{}'::jsonb,
            position integer NOT NULL DEFAULT 0,
            hidden boolean NOT NULL DEFAULT false,
            created_at timestamptz DEFAULT now(),
            CONSTRAINT uq_workspace_fields_key UNIQUE (tenant_id, record, key)
        );
        CREATE INDEX IF NOT EXISTS ix_workspace_fields_tenant_id ON workspace_fields (tenant_id);
        ALTER TABLE workspace_fields ENABLE ROW LEVEL SECURITY;
        ALTER TABLE workspace_fields FORCE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS tenant_isolation ON workspace_fields;
        CREATE POLICY tenant_isolation ON workspace_fields
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
        CREATE INDEX IF NOT EXISTS ix_products_extra ON products USING gin (extra);
    """),
    # Batches and expiry (ADR-006 phase 4c): stock lots per product, branch and batch number, and
    # what each stock movement took from or put into each lot.
    ("v61_batches", """
        CREATE TABLE IF NOT EXISTS batches_lots (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE
                DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid,
            product_id uuid NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            warehouse_id uuid NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
            batch_number varchar(64) NOT NULL,
            expiry_date date,
            qty numeric(14, 3) NOT NULL DEFAULT 0,
            unit_cost numeric(14, 2),
            status varchar(16) NOT NULL DEFAULT 'active',
            received_at timestamptz DEFAULT now(),
            created_at timestamptz DEFAULT now(),
            CONSTRAINT uq_batches_lots_batch UNIQUE (tenant_id, product_id, warehouse_id, batch_number)
        );
        CREATE INDEX IF NOT EXISTS ix_batches_lots_fefo ON batches_lots (product_id, warehouse_id, expiry_date);
        CREATE INDEX IF NOT EXISTS ix_batches_lots_tenant_id ON batches_lots (tenant_id);
        CREATE TABLE IF NOT EXISTS batches_lot_movements (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE
                DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid,
            lot_id uuid NOT NULL REFERENCES batches_lots(id) ON DELETE CASCADE,
            movement_id uuid NOT NULL REFERENCES stock_movements(id) ON DELETE CASCADE,
            qty numeric(14, 3) NOT NULL,
            created_at timestamptz DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS ix_batches_lot_movements_lot_id ON batches_lot_movements (lot_id);
        CREATE INDEX IF NOT EXISTS ix_batches_lot_movements_movement_id ON batches_lot_movements (movement_id);
        CREATE INDEX IF NOT EXISTS ix_batches_lot_movements_tenant_id ON batches_lot_movements (tenant_id);
        ALTER TABLE batches_lots ENABLE ROW LEVEL SECURITY;
        ALTER TABLE batches_lots FORCE ROW LEVEL SECURITY;
        ALTER TABLE batches_lot_movements ENABLE ROW LEVEL SECURITY;
        ALTER TABLE batches_lot_movements FORCE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS tenant_isolation ON batches_lots;
        CREATE POLICY tenant_isolation ON batches_lots
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
        DROP POLICY IF EXISTS tenant_isolation ON batches_lot_movements;
        CREATE POLICY tenant_isolation ON batches_lot_movements
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
    """),
    # The POS pharmacy variant dispenses through sales (ADR-006 phase 4d): prescriptions and the
    # controlled-drug log point at the sale and the drug's product.
    ("v62_dispensing_through_sales", """
        ALTER TABLE pharmacy_prescriptions ADD COLUMN IF NOT EXISTS sale_id uuid REFERENCES sales(id) ON DELETE SET NULL;
        ALTER TABLE pharmacy_prescriptions ADD COLUMN IF NOT EXISTS patient_national_id varchar(32);
        CREATE INDEX IF NOT EXISTS ix_pharmacy_prescriptions_sale_id ON pharmacy_prescriptions (sale_id);
        ALTER TABLE pharmacy_controlled_logs ALTER COLUMN drug_id DROP NOT NULL;
        ALTER TABLE pharmacy_controlled_logs ADD COLUMN IF NOT EXISTS product_id uuid REFERENCES products(id) ON DELETE SET NULL;
        ALTER TABLE pharmacy_controlled_logs ADD COLUMN IF NOT EXISTS sale_id uuid REFERENCES sales(id) ON DELETE SET NULL;
        CREATE INDEX IF NOT EXISTS ix_pharmacy_controlled_logs_product_id ON pharmacy_controlled_logs (product_id);
        CREATE INDEX IF NOT EXISTS ix_pharmacy_controlled_logs_sale_id ON pharmacy_controlled_logs (sale_id);
    """),
    # The pharmacy's own drugs and batches join the ERP: products, stock and batches (ADR-006
    # phase 4e); see the module's migrate.py.
    ("v63_pharmacy_joins_the_erp", "python:app.activities.pharmacy.modules.pharmacy.migrate:migrate"),
    # Removing a module (ADR-006 D2): its data kept hidden 30 days, or deleted after an export.
    ("v64_module_retention", """
        CREATE TABLE IF NOT EXISTS module_retention (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE
                DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid,
            module_id varchar(64) NOT NULL,
            mode varchar(16) NOT NULL,
            removed_at timestamptz DEFAULT now(),
            purge_after timestamptz,
            export bytea,
            removed_by uuid
        );
        CREATE INDEX IF NOT EXISTS ix_module_retention_module_id ON module_retention (module_id);
        CREATE INDEX IF NOT EXISTS ix_module_retention_tenant_id ON module_retention (tenant_id);
        ALTER TABLE module_retention ENABLE ROW LEVEL SECURITY;
        ALTER TABLE module_retention FORCE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS tenant_isolation ON module_retention;
        CREATE POLICY tenant_isolation ON module_retention
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
    """),
    # Storage quota (ADR-006 D3): each workspace's last measurement, analysed by module.
    ("v65_storage_usage", """
        CREATE TABLE IF NOT EXISTS storage_usage (
            tenant_id uuid PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
            measured_at timestamptz DEFAULT now(),
            total_bytes bigint NOT NULL DEFAULT 0,
            by_module jsonb NOT NULL DEFAULT '{}'::jsonb
        );
        ALTER TABLE storage_usage ENABLE ROW LEVEL SECURITY;
        ALTER TABLE storage_usage FORCE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS tenant_isolation ON storage_usage;
        CREATE POLICY tenant_isolation ON storage_usage
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
    """),
    # The screen builder's layouts (ADR-006 phase 5), per workspace: a role's home, menu and
    # dashboard (kind 'role', target = role id; standard roles are platform rows, shared by every
    # workspace) and a record's form (kind 'form', target = record).
    ("v66_workspace_layouts", """
        CREATE TABLE IF NOT EXISTS workspace_layouts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE
                DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid,
            kind varchar(16) NOT NULL,
            target varchar(64) NOT NULL,
            layout jsonb NOT NULL DEFAULT '{}'::jsonb,
            updated_by uuid,
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_workspace_layouts_target UNIQUE (tenant_id, kind, target)
        );
        CREATE INDEX IF NOT EXISTS ix_workspace_layouts_tenant_id ON workspace_layouts (tenant_id);
        ALTER TABLE workspace_layouts ENABLE ROW LEVEL SECURITY;
        ALTER TABLE workspace_layouts FORCE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS tenant_isolation ON workspace_layouts;
        CREATE POLICY tenant_isolation ON workspace_layouts
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
    """),
    # Uploaded files (#114): where each is stored (Vercel Blob in the cloud, the disk on site), what
    # it belongs to and its size, so replaced files are deleted and the quota counts real bytes.
    ("v67_workspace_files", """
        CREATE TABLE IF NOT EXISTS workspace_files (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE
                DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid,
            kind varchar(32) NOT NULL,
            owner_id varchar(64),
            url varchar(1024) NOT NULL,
            size bigint NOT NULL DEFAULT 0,
            content_type varchar(128),
            created_at timestamptz DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS ix_workspace_files_tenant_id ON workspace_files (tenant_id);
        CREATE INDEX IF NOT EXISTS ix_workspace_files_owner ON workspace_files (tenant_id, kind, owner_id);
        ALTER TABLE workspace_files ENABLE ROW LEVEL SECURITY;
        ALTER TABLE workspace_files FORCE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS tenant_isolation ON workspace_files;
        CREATE POLICY tenant_isolation ON workspace_files
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
    """),
    # #92: a licence runs on one computer (a single-device install, or a LAN's server): the
    # first that checks in. Others using a copy are flagged and get no renewed key; the owner
    # can move the licence. Existing licences bind to their first-seen install.
    ("v68_licence_device", """
        ALTER TABLE licences ADD COLUMN IF NOT EXISTS bound_installation_id uuid;
        UPDATE licences l SET bound_installation_id = (
            SELECT i.id FROM installations i WHERE i.licence_id = l.id ORDER BY i.first_seen_at, i.id LIMIT 1
        ) WHERE l.bound_installation_id IS NULL;
    """),
    # ADR-007: community modules installed in a workspace, and their records.
    ("v69_community_modules", """
        CREATE TABLE IF NOT EXISTS community_modules (
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE
                DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid,
            module_id varchar(80) NOT NULL,
            version varchar(32) NOT NULL,
            developer varchar(32) NOT NULL,
            manifest jsonb NOT NULL,
            entities jsonb NOT NULL DEFAULT '{}'::jsonb,
            scopes jsonb NOT NULL DEFAULT '[]'::jsonb,
            package_sha256 varchar(64),
            status varchar(16) NOT NULL DEFAULT 'active',
            installed_by uuid,
            installed_at timestamptz DEFAULT now(),
            updated_at timestamptz DEFAULT now(),
            PRIMARY KEY (tenant_id, module_id)
        );
        CREATE TABLE IF NOT EXISTS ext_records (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE
                DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid,
            module_id varchar(80) NOT NULL,
            entity varchar(48) NOT NULL,
            data jsonb NOT NULL DEFAULT '{}'::jsonb,
            created_by uuid,
            created_at timestamptz DEFAULT now(),
            updated_at timestamptz DEFAULT now(),
            deleted_at timestamptz
        );
        CREATE INDEX IF NOT EXISTS ix_ext_records_list ON ext_records (tenant_id, module_id, entity, created_at DESC);
        ALTER TABLE community_modules ENABLE ROW LEVEL SECURITY;
        ALTER TABLE community_modules FORCE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS tenant_isolation ON community_modules;
        CREATE POLICY tenant_isolation ON community_modules
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
        ALTER TABLE ext_records ENABLE ROW LEVEL SECURITY;
        ALTER TABLE ext_records FORCE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS tenant_isolation ON ext_records;
        CREATE POLICY tenant_isolation ON ext_records
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
    """),
    # ADR-007 D4: the token a community module's server calls /ext/v1 with (stored hashed), and the
    # secret its webhooks are signed with.
    ("v70_community_tokens", """
        ALTER TABLE community_modules ADD COLUMN IF NOT EXISTS api_token_hash varchar(64);
        ALTER TABLE community_modules ADD COLUMN IF NOT EXISTS webhook_secret varchar(64);
        ALTER TABLE community_modules ADD COLUMN IF NOT EXISTS token_created_at timestamptz;
        -- Looked up across workspaces by the hash of a random 32-byte token (no collisions).
        CREATE INDEX IF NOT EXISTS ix_community_modules_token ON community_modules (api_token_hash)
            WHERE api_token_hash IS NOT NULL;
    """),
    # ADR-007 D4: webhooks to community modules' servers, kept until delivered or given up.
    ("v71_community_webhooks", """
        CREATE TABLE IF NOT EXISTS community_webhook_deliveries (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE
                DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid,
            module_id varchar(80) NOT NULL,
            event varchar(48) NOT NULL,
            payload jsonb NOT NULL,
            status varchar(16) NOT NULL DEFAULT 'pending',
            attempts integer NOT NULL DEFAULT 0,
            next_attempt_at timestamptz DEFAULT now(),
            last_status_code integer,
            last_error text,
            created_at timestamptz DEFAULT now(),
            delivered_at timestamptz
        );
        CREATE INDEX IF NOT EXISTS ix_community_webhooks_due ON community_webhook_deliveries (next_attempt_at)
            WHERE status = 'pending';
        CREATE INDEX IF NOT EXISTS ix_community_webhooks_module ON community_webhook_deliveries (tenant_id, module_id, created_at DESC);
        ALTER TABLE community_webhook_deliveries ENABLE ROW LEVEL SECURITY;
        ALTER TABLE community_webhook_deliveries FORCE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS tenant_isolation ON community_webhook_deliveries;
        CREATE POLICY tenant_isolation ON community_webhook_deliveries
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
    """),
    # ADR-007 D5: the developer portal. Developers (people, separate from owners), teams (a team's
    # handle is the <developer> part of its module ids), their signing keys and CLI tokens.
    ("v72_developer_portal", """
        CREATE TABLE IF NOT EXISTS developer_users (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            email varchar(254) NOT NULL UNIQUE,
            full_name varchar(128) NOT NULL,
            password_hash varchar(256) NOT NULL,
            is_active boolean NOT NULL DEFAULT true,
            tokens_valid_after timestamptz,
            last_login_at timestamptz,
            created_at timestamptz DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS developer_teams (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            handle varchar(32) NOT NULL UNIQUE,
            name varchar(128) NOT NULL,
            created_by uuid REFERENCES developer_users(id) ON DELETE SET NULL,
            created_at timestamptz DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS developer_team_members (
            team_id uuid NOT NULL REFERENCES developer_teams(id) ON DELETE CASCADE,
            user_id uuid NOT NULL REFERENCES developer_users(id) ON DELETE CASCADE,
            role varchar(16) NOT NULL DEFAULT 'member',
            created_at timestamptz DEFAULT now(),
            PRIMARY KEY (team_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS developer_keys (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            team_id uuid NOT NULL REFERENCES developer_teams(id) ON DELETE CASCADE,
            key_id varchar(32) NOT NULL UNIQUE,
            name varchar(64) NOT NULL,
            public_key varchar(64) NOT NULL,
            certificate text NOT NULL,
            created_by uuid REFERENCES developer_users(id) ON DELETE SET NULL,
            created_at timestamptz DEFAULT now(),
            revoked_at timestamptz
        );
        CREATE TABLE IF NOT EXISTS developer_cli_tokens (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id uuid NOT NULL REFERENCES developer_users(id) ON DELETE CASCADE,
            name varchar(64) NOT NULL,
            token_hash varchar(64) NOT NULL UNIQUE,
            created_at timestamptz DEFAULT now(),
            last_used_at timestamptz,
            revoked_at timestamptz
        );
    """),
    # ADR-010 D3: theme packages installed in a workspace (Mizan's and activities' themes are files).
    ("v73_workspace_themes", """
        CREATE TABLE IF NOT EXISTS workspace_themes (
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE
                DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid,
            theme_id varchar(80) NOT NULL,
            version varchar(32) NOT NULL,
            developer varchar(32) NOT NULL,
            theme jsonb NOT NULL,
            assets jsonb NOT NULL DEFAULT '{}'::jsonb,
            package_sha256 varchar(64),
            installed_by uuid,
            installed_at timestamptz DEFAULT now(),
            PRIMARY KEY (tenant_id, theme_id)
        );
        ALTER TABLE workspace_themes ENABLE ROW LEVEL SECURITY;
        ALTER TABLE workspace_themes FORCE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS tenant_isolation ON workspace_themes;
        CREATE POLICY tenant_isolation ON workspace_themes
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
    """),
    # #107 (ADR-006 phase 9): an owner asks to change a workspace's activity; the Mizan team
    # approves or rejects it in the admin panel. Read across workspaces (owner and admin APIs, with
    # app.bypass), so written outside a bound workspace; RLS like every table with tenant_id.
    ("v74_activity_changes", """
        CREATE TABLE IF NOT EXISTS activity_changes (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            from_activity varchar(32) NOT NULL,
            to_activity varchar(64) NOT NULL,
            data_mode varchar(8) NOT NULL DEFAULT 'keep',
            status varchar(16) NOT NULL DEFAULT 'requested',
            note text,
            requested_by uuid REFERENCES owner_accounts(id) ON DELETE SET NULL,
            decided_by uuid,
            decision_note text,
            result jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            decided_at timestamptz
        );
        CREATE INDEX IF NOT EXISTS ix_activity_changes_tenant ON activity_changes (tenant_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS ix_activity_changes_status ON activity_changes (status);
        CREATE UNIQUE INDEX IF NOT EXISTS ux_activity_changes_one_open ON activity_changes (tenant_id) WHERE status = 'requested';
        ALTER TABLE activity_changes ENABLE ROW LEVEL SECURITY;
        ALTER TABLE activity_changes FORCE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS tenant_isolation ON activity_changes;
        CREATE POLICY tenant_isolation ON activity_changes
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
    """),
    # The marketplace (ADR-007 milestone 2, #105): developers submit signed packages, the Mizan
    # team reviews and countersigns them, workspaces install listed ones. Platform tables.
    ("v75_marketplace", """
        CREATE TABLE IF NOT EXISTS marketplace_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            item_id varchar(80) NOT NULL,
            version varchar(32) NOT NULL,
            kind varchar(16) NOT NULL,
            team_id uuid NOT NULL REFERENCES developer_teams(id) ON DELETE CASCADE,
            package bytea NOT NULL,
            sha256 varchar(64) NOT NULL,
            size integer NOT NULL,
            manifest jsonb NOT NULL,
            status varchar(16) NOT NULL DEFAULT 'in_review',
            submitted_by uuid REFERENCES developer_users(id) ON DELETE SET NULL,
            submitted_at timestamptz NOT NULL DEFAULT now(),
            reviewed_by uuid,
            reviewed_at timestamptz,
            review_note text,
            countersignature text,
            UNIQUE (item_id, version)
        );
        CREATE INDEX IF NOT EXISTS ix_marketplace_versions_status ON marketplace_versions (status, submitted_at);
        CREATE TABLE IF NOT EXISTS marketplace_items (
            id varchar(80) PRIMARY KEY,
            kind varchar(16) NOT NULL,
            team_id uuid NOT NULL REFERENCES developer_teams(id) ON DELETE CASCADE,
            name text NOT NULL,
            name_en text,
            description text,
            current_version varchar(32) NOT NULL,
            status varchar(16) NOT NULL DEFAULT 'listed',
            status_note text,
            installs integer NOT NULL DEFAULT 0,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        );
    """),
    # Developers' activities run in workspaces (ADR-012): activity ids are '<team>.<activity>'.
    ("v76_package_activity_ids", """
        ALTER TABLE tenants ALTER COLUMN sector TYPE varchar(80);
        ALTER TABLE tenants ALTER COLUMN business_type TYPE varchar(80);
        ALTER TABLE activity_changes ALTER COLUMN from_activity TYPE varchar(80);
        ALTER TABLE activity_changes ALTER COLUMN to_activity TYPE varchar(80);
        ALTER TABLE org_positions ALTER COLUMN activity TYPE varchar(80);
        ALTER TABLE org_positions ALTER COLUMN category TYPE varchar(80);
    """),
    # Owners' email (#71, #72): a verified address, one-time codes (verify the address, reset the
    # password) and a log of the emails Mizan sent, so reminders and receipts go out once.
    ("v77_owner_email", """
        ALTER TABLE owner_accounts ADD COLUMN IF NOT EXISTS email_verified_at timestamptz;
        CREATE TABLE IF NOT EXISTS owner_codes (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_id uuid NOT NULL REFERENCES owner_accounts(id) ON DELETE CASCADE,
            purpose varchar(24) NOT NULL,
            email varchar(254) NOT NULL,
            code_hash varchar(64) NOT NULL,
            attempts integer NOT NULL DEFAULT 0,
            expires_at timestamptz NOT NULL,
            used_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS ix_owner_codes_owner ON owner_codes (owner_id, purpose, created_at);
        CREATE TABLE IF NOT EXISTS owner_email_log (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_id uuid REFERENCES owner_accounts(id) ON DELETE CASCADE,
            kind varchar(32) NOT NULL,
            ref varchar(160) NOT NULL,
            email varchar(254) NOT NULL,
            ok boolean NOT NULL DEFAULT true,
            sent_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (kind, ref)
        );
    """),
    # A table made from the model before v77 ran (tests, fresh databases) lacked the unique key
    # owner_mail.send_once needs.
    ("v78_owner_email_log_unique", """
        CREATE UNIQUE INDEX IF NOT EXISTS owner_email_log_kind_ref_key ON owner_email_log (kind, ref);
    """),
    # Patient-level clinical access (#113): the clinicians on a patient's care team read the record,
    # others only through a logged, reviewed break-glass grant; every clinical read is logged.
    ("v79_clinic_patient_access", """
        ALTER TABLE clinic_appointments ADD COLUMN IF NOT EXISTS doctor_user_id uuid REFERENCES users(id) ON DELETE SET NULL;
        ALTER TABLE clinic_encounters ADD COLUMN IF NOT EXISTS doctor_user_id uuid REFERENCES users(id) ON DELETE SET NULL;
        ALTER TABLE clinic_prescriptions ADD COLUMN IF NOT EXISTS doctor_user_id uuid REFERENCES users(id) ON DELETE SET NULL;
        ALTER TABLE clinic_lab_orders ADD COLUMN IF NOT EXISTS doctor_user_id uuid REFERENCES users(id) ON DELETE SET NULL;
        CREATE INDEX IF NOT EXISTS ix_clinic_appointments_doctor_user_id ON clinic_appointments (doctor_user_id);
        CREATE INDEX IF NOT EXISTS ix_clinic_encounters_doctor_user_id ON clinic_encounters (doctor_user_id);
        CREATE INDEX IF NOT EXISTS ix_clinic_prescriptions_doctor_user_id ON clinic_prescriptions (doctor_user_id);
        CREATE INDEX IF NOT EXISTS ix_clinic_lab_orders_doctor_user_id ON clinic_lab_orders (doctor_user_id);
        CREATE TABLE IF NOT EXISTS clinic_care_team (
            id varchar(36) PRIMARY KEY,
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            patient_id varchar(36) NOT NULL REFERENCES clinic_patients(id) ON DELETE CASCADE,
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role varchar(16) NOT NULL DEFAULT 'attending',
            added_by uuid,
            created_at timestamptz NOT NULL DEFAULT now(),
            ended_at timestamptz
        );
        CREATE INDEX IF NOT EXISTS ix_clinic_care_team_tenant_id ON clinic_care_team (tenant_id);
        CREATE INDEX IF NOT EXISTS ix_clinic_care_team_patient_id ON clinic_care_team (patient_id);
        CREATE INDEX IF NOT EXISTS ix_clinic_care_team_user_id ON clinic_care_team (user_id);
        CREATE UNIQUE INDEX IF NOT EXISTS ux_clinic_care_team_active ON clinic_care_team (tenant_id, patient_id, user_id) WHERE ended_at IS NULL;
        CREATE TABLE IF NOT EXISTS clinic_access_grants (
            id varchar(36) PRIMARY KEY,
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            patient_id varchar(36) NOT NULL REFERENCES clinic_patients(id) ON DELETE CASCADE,
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            reason text NOT NULL,
            starts_at timestamptz NOT NULL DEFAULT now(),
            expires_at timestamptz NOT NULL,
            revoked_at timestamptz,
            reviewed_by uuid,
            reviewed_at timestamptz,
            review_note text
        );
        CREATE INDEX IF NOT EXISTS ix_clinic_access_grants_tenant_id ON clinic_access_grants (tenant_id);
        CREATE INDEX IF NOT EXISTS ix_clinic_access_grants_patient_id ON clinic_access_grants (patient_id);
        CREATE INDEX IF NOT EXISTS ix_clinic_access_grants_user_id ON clinic_access_grants (user_id);
        CREATE TABLE IF NOT EXISTS clinic_access_log (
            id varchar(36) PRIMARY KEY,
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            user_id uuid,
            user_name varchar(128) NOT NULL DEFAULT '',
            patient_id varchar(36),
            resource varchar(16) NOT NULL,
            how varchar(16) NOT NULL,
            rows integer NOT NULL DEFAULT 0,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS ix_clinic_access_log_tenant_id ON clinic_access_log (tenant_id);
        CREATE INDEX IF NOT EXISTS ix_clinic_access_log_user_id ON clinic_access_log (user_id);
        CREATE INDEX IF NOT EXISTS ix_clinic_access_log_patient_id ON clinic_access_log (patient_id);
        CREATE INDEX IF NOT EXISTS ix_clinic_access_log_created_at ON clinic_access_log (created_at);
        ALTER TABLE clinic_care_team ENABLE ROW LEVEL SECURITY;
        ALTER TABLE clinic_care_team FORCE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS tenant_isolation ON clinic_care_team;
        CREATE POLICY tenant_isolation ON clinic_care_team
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
        ALTER TABLE clinic_access_grants ENABLE ROW LEVEL SECURITY;
        ALTER TABLE clinic_access_grants FORCE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS tenant_isolation ON clinic_access_grants;
        CREATE POLICY tenant_isolation ON clinic_access_grants
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
        ALTER TABLE clinic_access_log ENABLE ROW LEVEL SECURITY;
        ALTER TABLE clinic_access_log FORCE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS tenant_isolation ON clinic_access_log;
        CREATE POLICY tenant_isolation ON clinic_access_log
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
    """),
    # Existing clinics keep access to their patients: records whose doctor_name is exactly an active
    # user's name in the workspace are linked to that user, who joins the patient's care team.
    ("v79b_clinic_care_team_backfill", "python:app.activities.healthcare.modules.healthcare_clinic.migrate:backfill_care_team"),
    # ADR-014 D4/D5 (sales, POS, inventory): returns are their own documents linked to the sale,
    # drawer rows are cancelled instead of deleted, and products keep a weighted average cost.
    # Existing partial returns (RET-…, linked only by "مرتجع جزئي من INV-…" in their notes) are
    # linked to their sale and get their real totals from their lines. Old full returns (the
    # original sale marked 'returned') are left as they are: history is not rewritten.
    ("v80_sales_returns_drawer_cancel_avg_cost", """
        ALTER TABLE sales ADD COLUMN IF NOT EXISTS return_of uuid REFERENCES sales(id);
        CREATE INDEX IF NOT EXISTS ix_sales_return_of ON sales (return_of) WHERE return_of IS NOT NULL;
        ALTER TABLE drawer_transactions ADD COLUMN IF NOT EXISTS cancelled_at timestamptz;
        ALTER TABLE drawer_transactions ADD COLUMN IF NOT EXISTS cancelled_by uuid REFERENCES users(id) ON DELETE SET NULL;
        ALTER TABLE drawer_transactions ADD COLUMN IF NOT EXISTS customer_payment_id uuid REFERENCES customer_payments(id) ON DELETE SET NULL;
        ALTER TABLE sale_payments ADD COLUMN IF NOT EXISTS safe_id uuid REFERENCES safes(id) ON DELETE SET NULL;
        ALTER TABLE products ADD COLUMN IF NOT EXISTS avg_cost numeric(14,4) NOT NULL DEFAULT 0;
        UPDATE products SET avg_cost = COALESCE(cost_price, 0) WHERE avg_cost = 0 AND COALESCE(cost_price, 0) <> 0;
        UPDATE sales r SET return_of = o.id
        FROM sales o
        WHERE r.return_of IS NULL AND r.status = 'returned' AND r.invoice_number LIKE 'RET-%'
          AND r.notes LIKE 'مرتجع جزئي من %' AND o.tenant_id = r.tenant_id AND o.id <> r.id
          AND o.invoice_number = btrim(substring(r.notes FROM 15));
        UPDATE sales r SET total = t.gross, net_total = t.gross - t.line_discounts, paid_amount = t.gross - t.line_discounts
        FROM (SELECT sale_id, SUM(qty * unit_price) AS gross, SUM(COALESCE(discount, 0)) AS line_discounts
              FROM sale_items GROUP BY sale_id) t
        WHERE t.sale_id = r.id AND r.return_of IS NOT NULL AND COALESCE(r.total, 0) = 0;
    """),
    # ADR-014 D4: every payment says where the money went, and money documents are cancelled or
    # deactivated instead of deleted.
    ("v81_money_flows_finance", """
        ALTER TABLE safes DROP CONSTRAINT IF EXISTS safes_safe_type_check;
        ALTER TABLE safes ADD CONSTRAINT safes_safe_type_check CHECK (safe_type IN ('permanent', 'temporary', 'bank'));
        ALTER TABLE safe_transactions ADD COLUMN IF NOT EXISTS ref_type text;
        ALTER TABLE safe_transactions ADD COLUMN IF NOT EXISTS ref_id uuid;
        CREATE INDEX IF NOT EXISTS idx_safe_transactions_ref ON safe_transactions (ref_type, ref_id);

        ALTER TABLE expenses ADD COLUMN IF NOT EXISTS cancelled_at timestamptz;
        ALTER TABLE expenses ADD COLUMN IF NOT EXISTS cancelled_by uuid REFERENCES users(id);
        ALTER TABLE expenses ADD COLUMN IF NOT EXISTS cancel_reason text;

        ALTER TABLE customers ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;
        ALTER TABLE customer_payments ADD COLUMN IF NOT EXISTS method text;
        ALTER TABLE customer_payments ADD COLUMN IF NOT EXISTS safe_id uuid REFERENCES safes(id);
        ALTER TABLE customer_payments ADD COLUMN IF NOT EXISTS wallet_id uuid REFERENCES payment_wallets(id);
        ALTER TABLE customer_payments ADD COLUMN IF NOT EXISTS shift_id uuid REFERENCES shifts(id);
        ALTER TABLE customer_payments DROP CONSTRAINT IF EXISTS customer_payments_customer_id_fkey;
        ALTER TABLE customer_payments ADD CONSTRAINT customer_payments_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES customers(id);
        CREATE TABLE IF NOT EXISTS customer_adjustments (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid
                REFERENCES tenants(id) ON DELETE CASCADE,
            customer_id uuid NOT NULL REFERENCES customers(id),
            kind text NOT NULL DEFAULT 'adjustment' CHECK (kind IN ('opening', 'adjustment')),
            amount numeric(14,2) NOT NULL,
            balance_before numeric(14,2) NOT NULL,
            balance_after numeric(14,2) NOT NULL,
            note text,
            created_by uuid REFERENCES users(id),
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS ix_customer_adjustments_tenant_id ON customer_adjustments (tenant_id);
        CREATE INDEX IF NOT EXISTS ix_customer_adjustments_customer_id ON customer_adjustments (customer_id);
        ALTER TABLE customer_adjustments ENABLE ROW LEVEL SECURITY;
        ALTER TABLE customer_adjustments FORCE ROW LEVEL SECURITY;
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'customer_adjustments' AND policyname = 'tenant_isolation') THEN
            CREATE POLICY tenant_isolation ON customer_adjustments
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
          END IF;
        END $$;

        ALTER TABLE supplier_transactions DROP COLUMN IF EXISTS tx_type;
        ALTER TABLE supplier_transactions ADD COLUMN IF NOT EXISTS method text;
        ALTER TABLE supplier_transactions ADD COLUMN IF NOT EXISTS safe_id uuid REFERENCES safes(id);
        ALTER TABLE supplier_transactions ADD COLUMN IF NOT EXISTS wallet_id uuid REFERENCES payment_wallets(id);
        ALTER TABLE supplier_transactions ADD COLUMN IF NOT EXISTS purchase_id uuid REFERENCES purchase_orders(id);
        ALTER TABLE supplier_transactions ADD COLUMN IF NOT EXISTS created_by uuid REFERENCES users(id);
        ALTER TABLE supplier_transactions DROP CONSTRAINT IF EXISTS supplier_transactions_supplier_id_fkey;
        ALTER TABLE supplier_transactions ADD CONSTRAINT supplier_transactions_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES suppliers(id);
        ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS safe_id uuid REFERENCES safes(id);
        ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS wallet_id uuid REFERENCES payment_wallets(id);

        ALTER TABLE hr_advances ADD COLUMN IF NOT EXISTS safe_id uuid REFERENCES safes(id);
        ALTER TABLE hr_advances ADD COLUMN IF NOT EXISTS wallet_id uuid REFERENCES payment_wallets(id);
        ALTER TABLE hr_payroll_periods ADD COLUMN IF NOT EXISTS safe_id uuid REFERENCES safes(id);
        ALTER TABLE hr_payroll_periods ADD COLUMN IF NOT EXISTS wallet_id uuid REFERENCES payment_wallets(id);
        ALTER TABLE hr_payroll_periods ADD COLUMN IF NOT EXISTS expense_id uuid REFERENCES expenses(id);
        ALTER TABLE hr_payroll_periods ADD COLUMN IF NOT EXISTS paid_amount numeric(14,2);
    """),
    # ADR-014 D4 (clinic): a clinic invoice is one sale, made at its first payment; payments are
    # payment lines on it. Before, every payment made a new sale with the same invoice number.
    ("v82_clinic_invoice_sale", """
        ALTER TABLE clinic_invoices ADD COLUMN IF NOT EXISTS sale_id uuid REFERENCES sales(id) ON DELETE SET NULL;
        UPDATE clinic_invoices ci SET sale_id = s.id
        FROM (SELECT DISTINCT ON (tenant_id, invoice_number) id, tenant_id, invoice_number
              FROM sales ORDER BY tenant_id, invoice_number, created_at) s
        WHERE ci.sale_id IS NULL AND s.tenant_id = ci.tenant_id AND s.invoice_number = ci.invoice_ref;
    """),
    # #131: the clinical roles hold their own clinic permissions, not the umbrella "clinic". The
    # standard roles (tenant_id NULL) are re-synced from roles.py by ensure_standard_roles; this
    # strips "clinic" from the personal copies v54 made of them ("doctor-1a2b3c4d"), keeping
    # clinic:view. Workspaces' own roles ("ws-…") are left as their admins set them. Invoice lines
    # stop naming the medication or test (billing staff see invoices, not clinical data).
    ("v84_clinic_role_separation", """
        UPDATE sys_roles r SET grants = (
            SELECT COALESCE(jsonb_agg(DISTINCT g ORDER BY g), '[]'::jsonb)
            FROM jsonb_array_elements_text(r.grants || '["clinic:view"]'::jsonb) AS e(g)
            WHERE g <> 'clinic'
        ), updated_at = now()
        WHERE r.tenant_id IS NOT NULL
          AND r.code ~ '^(doctor|nurse|receptionist|lab_tech|pharmacist)-[0-9a-f]{8}$'
          AND r.grants ? 'clinic';
        UPDATE clinic_invoices ci SET charges = (
            SELECT jsonb_agg(CASE
                WHEN c->>'description' LIKE 'صرف دواء:%' THEN jsonb_set(c, '{description}', to_jsonb('صرف أدوية'::text))
                WHEN c->>'description' LIKE 'رسوم فحص مخبري:%'
                    THEN jsonb_set(c, '{description}', to_jsonb(('رسوم فحص مخبري — طلب ' || COALESCE(ci.encounter_ref, ''))::text))
                ELSE c END ORDER BY n)
            FROM jsonb_array_elements(ci.charges) WITH ORDINALITY AS x(c, n)
        )
        WHERE jsonb_typeof(ci.charges) = 'array'
          AND (ci.charges::text LIKE '%صرف دواء:%' OR ci.charges::text LIKE '%رسوم فحص مخبري:%');
    """),
    # #36: department master, examination rooms and doctors' weekly rosters; appointments name their
    # department and room. The department name stays in clinic_appointments.department for older
    # records and lists.
    ("v85_clinic_departments_rosters", """
        CREATE TABLE IF NOT EXISTS clinic_departments (
            id varchar(36) PRIMARY KEY,
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            code varchar(16) NOT NULL,
            name varchar(64) NOT NULL,
            specialty_code varchar(32) NOT NULL DEFAULT '',
            active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS ix_clinic_departments_tenant_id ON clinic_departments (tenant_id);
        CREATE UNIQUE INDEX IF NOT EXISTS ux_clinic_departments_code ON clinic_departments (tenant_id, code);
        CREATE TABLE IF NOT EXISTS clinic_rooms (
            id varchar(36) PRIMARY KEY,
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name varchar(64) NOT NULL,
            department_id varchar(36) REFERENCES clinic_departments(id) ON DELETE SET NULL,
            active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS ix_clinic_rooms_tenant_id ON clinic_rooms (tenant_id);
        CREATE INDEX IF NOT EXISTS ix_clinic_rooms_department_id ON clinic_rooms (department_id);
        CREATE TABLE IF NOT EXISTS clinic_doctor_schedules (
            id varchar(36) PRIMARY KEY,
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            doctor_user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            department_id varchar(36) NOT NULL REFERENCES clinic_departments(id) ON DELETE CASCADE,
            room_id varchar(36) REFERENCES clinic_rooms(id) ON DELETE SET NULL,
            weekday integer NOT NULL CHECK (weekday BETWEEN 0 AND 6),
            start_time varchar(5) NOT NULL,
            end_time varchar(5) NOT NULL,
            slot_minutes integer NOT NULL DEFAULT 15,
            active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS ix_clinic_doctor_schedules_tenant_id ON clinic_doctor_schedules (tenant_id);
        CREATE INDEX IF NOT EXISTS ix_clinic_doctor_schedules_doctor_user_id ON clinic_doctor_schedules (doctor_user_id);
        CREATE INDEX IF NOT EXISTS ix_clinic_doctor_schedules_department_id ON clinic_doctor_schedules (department_id);
        CREATE INDEX IF NOT EXISTS ix_clinic_doctor_schedules_room_id ON clinic_doctor_schedules (room_id);
        ALTER TABLE clinic_appointments ADD COLUMN IF NOT EXISTS department_id varchar(36) REFERENCES clinic_departments(id) ON DELETE SET NULL;
        ALTER TABLE clinic_appointments ADD COLUMN IF NOT EXISTS room_id varchar(36) REFERENCES clinic_rooms(id) ON DELETE SET NULL;
        CREATE INDEX IF NOT EXISTS ix_clinic_appointments_department_id ON clinic_appointments (department_id);
        CREATE INDEX IF NOT EXISTS ix_clinic_appointments_room_id ON clinic_appointments (room_id);
        ALTER TABLE clinic_departments ENABLE ROW LEVEL SECURITY;
        ALTER TABLE clinic_departments FORCE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS tenant_isolation ON clinic_departments;
        CREATE POLICY tenant_isolation ON clinic_departments
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
        ALTER TABLE clinic_rooms ENABLE ROW LEVEL SECURITY;
        ALTER TABLE clinic_rooms FORCE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS tenant_isolation ON clinic_rooms;
        CREATE POLICY tenant_isolation ON clinic_rooms
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
        ALTER TABLE clinic_doctor_schedules ENABLE ROW LEVEL SECURITY;
        ALTER TABLE clinic_doctor_schedules FORCE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS tenant_isolation ON clinic_doctor_schedules;
        CREATE POLICY tenant_isolation ON clinic_doctor_schedules
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
    """),
    # #45: referrals between departments and doctors; accepting one puts the receiving doctor on
    # the patient's care team.
    ("v86_clinic_referrals", """
        CREATE TABLE IF NOT EXISTS clinic_referrals (
            id varchar(36) PRIMARY KEY,
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            referral_ref varchar(32) NOT NULL,
            patient_id varchar(36) NOT NULL REFERENCES clinic_patients(id) ON DELETE CASCADE,
            from_doctor_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
            from_doctor_name varchar(128) NOT NULL DEFAULT '',
            to_department_id varchar(36) NOT NULL REFERENCES clinic_departments(id) ON DELETE RESTRICT,
            to_doctor_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
            priority varchar(16) NOT NULL DEFAULT 'routine' CHECK (priority IN ('routine', 'urgent', 'emergency')),
            reason text NOT NULL,
            triage_notes text NOT NULL DEFAULT '',
            status varchar(16) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'declined', 'completed')),
            encounter_id varchar(36) REFERENCES clinic_encounters(id) ON DELETE SET NULL,
            responded_by uuid,
            responded_at timestamptz,
            response_note text NOT NULL DEFAULT '',
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS ix_clinic_referrals_tenant_id ON clinic_referrals (tenant_id);
        CREATE INDEX IF NOT EXISTS ix_clinic_referrals_referral_ref ON clinic_referrals (referral_ref);
        CREATE INDEX IF NOT EXISTS ix_clinic_referrals_patient_id ON clinic_referrals (patient_id);
        CREATE INDEX IF NOT EXISTS ix_clinic_referrals_from_doctor_user_id ON clinic_referrals (from_doctor_user_id);
        CREATE INDEX IF NOT EXISTS ix_clinic_referrals_to_department_id ON clinic_referrals (to_department_id);
        CREATE INDEX IF NOT EXISTS ix_clinic_referrals_to_doctor_user_id ON clinic_referrals (to_doctor_user_id);
        CREATE INDEX IF NOT EXISTS ix_clinic_referrals_status ON clinic_referrals (status);
        CREATE INDEX IF NOT EXISTS ix_clinic_referrals_created_at ON clinic_referrals (created_at);
        ALTER TABLE clinic_referrals ENABLE ROW LEVEL SECURITY;
        ALTER TABLE clinic_referrals FORCE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS tenant_isolation ON clinic_referrals;
        CREATE POLICY tenant_isolation ON clinic_referrals
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on');
    """),
]

# mizan_app's rights (#112), granted again after every migrate. Default privileges only cover tables
# made by the role that set them, so after the move from Neon (ADR-011) tables the new login role
# made had no grants and workspace requests got "permission denied" on them.
APP_ROLE_GRANTS = """
    GRANT USAGE ON SCHEMA public TO mizan_app;
    GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES ON ALL TABLES IN SCHEMA public TO mizan_app;
    GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO mizan_app;
    GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO mizan_app;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES ON TABLES TO mizan_app;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO mizan_app;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO mizan_app;
"""


async def grant_app_role(session: AsyncSession) -> None:
    if not await session.scalar(text("SELECT 1 FROM pg_roles WHERE rolname = 'mizan_app'")):
        return
    for stmt in split_statements(APP_ROLE_GRANTS):
        if stmt.strip():
            try:
                async with session.begin_nested():
                    await session.execute(text(stmt.strip()))
            except Exception as e:
                logger.warning(f"Granting mizan_app: {e}")
    await session.commit()


async def apply_migrations(session: AsyncSession) -> List[str]:
    """Apply all pending migrations asynchronously using SQLAlchemy.
    Statement-by-statement execution wrapped in savepoints for total resilience.
    """
    # 1. Ensure schema_migrations table
    await session.execute(text("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id text PRIMARY KEY,
            applied_at timestamptz DEFAULT now()
        );
    """))
    await session.commit()

    # 2. Bind foundation and bypass RLS
    try:
        await session.execute(text("SELECT set_config('app.bypass', 'on', false)"))
    except Exception as e:
        await session.rollback()
        logger.warning(f"Notice setting bypass: {e}")

    # 3. Fetch applied migrations
    res = await session.execute(text("SELECT id FROM schema_migrations"))
    applied = set(res.scalars().all())

    applied_now = []
    for mid, sql in MIGRATIONS:
        if mid in applied:
            continue

        logger.info(f"Applying migration {mid}...")
        if sql.startswith("python:"):
            # A data migration in Python, run with RLS bypassed; it must be idempotent.
            import importlib

            module_name, _, fn_name = sql.removeprefix("python:").partition(":")
            await getattr(importlib.import_module(module_name), fn_name)(session)
            await session.execute(text("INSERT INTO schema_migrations (id) VALUES (:id) ON CONFLICT DO NOTHING"), {"id": mid})
            await session.commit()
            applied_now.append(mid)
            logger.info(f"Successfully applied migration {mid}")
            continue
        stmts = split_statements(sql)
        for stmt in stmts:
            stmt_clean = stmt.strip()
            if not stmt_clean:
                continue
            try:
                async with session.begin_nested():
                    await session.execute(text(stmt_clean))
            except Exception as e:
                err_str = str(e).lower()
                if any(x in err_str for x in ("already exists", "duplicate", "does not exist", "notice")):
                    continue
                logger.warning(f"Migration {mid} notice on statement: {e}")

        # Mark applied
        await session.execute(
            text("INSERT INTO schema_migrations (id) VALUES (:id) ON CONFLICT DO NOTHING"),
            {"id": mid}
        )
        await session.commit()
        applied_now.append(mid)
        logger.info(f"Successfully applied migration {mid}")

    await grant_app_role(session)
    return applied_now
