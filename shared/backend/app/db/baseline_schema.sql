-- Mizan baseline schema (structure only, no data): the legacy tables, sequences and
-- columns that predate the SQLAlchemy models. Loaded into a brand-new database by
-- docker compose; the models (create_all) and `manage.py db migrate` build on top of it.

--
-- PostgreSQL database dump
--

\restrict 7gvOzt0a84qKVLxmkQyriQs10rEffhCYfdIX6dqsuPjf8HxC0gFdf4aZihe2SQU

-- Dumped from database version 16.15
-- Dumped by pg_dump version 16.15

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: doc_type_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.doc_type_enum AS ENUM (
    'sale_invoice',
    'purchase_order',
    'shift_report',
    'inventory_report',
    'other',
    'quotation',
    'dispatch_order',
    'goods_receipt',
    'stock_request',
    'shift_handover',
    'purchase_invoice',
    'safe_deposit'
);


--
-- Name: drawer_tx_type_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.drawer_tx_type_enum AS ENUM (
    'sale',
    'return_',
    'expense',
    'deposit',
    'withdrawal'
);


--
-- Name: movement_type_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.movement_type_enum AS ENUM (
    'opening_stock',
    'purchase',
    'return_in',
    'adjustment_in',
    'transfer_in',
    'sale',
    'damage',
    'adjustment_out',
    'transfer_out'
);


--
-- Name: po_status_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.po_status_enum AS ENUM (
    'draft',
    'received',
    'partial',
    'cancelled'
);


--
-- Name: sale_mode_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.sale_mode_enum AS ENUM (
    'retail',
    'wholesale'
);


--
-- Name: sale_status_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.sale_status_enum AS ENUM (
    'draft',
    'confirmed',
    'returned',
    'cancelled',
    'quotation'
);


--
-- Name: shift_status_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.shift_status_enum AS ENUM (
    'open',
    'closed'
);


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: archived_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.archived_documents (
    id uuid NOT NULL,
    doc_number character varying(64) NOT NULL,
    doc_type public.doc_type_enum NOT NULL,
    customer_name character varying(128),
    amount numeric(12,2),
    file_path character varying(512),
    storage_key character varying(512),
    metadata jsonb,
    ref_id uuid,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_log (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    entity_type text NOT NULL,
    entity_id uuid,
    action text NOT NULL,
    user_id uuid,
    user_name text,
    changes jsonb,
    note text,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.categories (
    id uuid NOT NULL,
    name character varying(128) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: customer_payments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.customer_payments (
    id uuid NOT NULL,
    customer_id uuid NOT NULL,
    amount numeric(12,2) NOT NULL,
    note text,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: customers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.customers (
    id uuid NOT NULL,
    name character varying(128) NOT NULL,
    phone character varying(32),
    address text,
    is_cash boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    balance numeric(14,2) DEFAULT 0 NOT NULL
);


--
-- Name: dispatch_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.dispatch_seq
    START WITH 1000
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: drawer_transactions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.drawer_transactions (
    id uuid NOT NULL,
    shift_id uuid NOT NULL,
    type public.drawer_tx_type_enum NOT NULL,
    amount numeric(12,2) NOT NULL,
    ref_id uuid,
    note text,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    category_id uuid,
    payment_method text DEFAULT 'cash'::text,
    wallet_id uuid
);


--
-- Name: employees; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.employees (
    id uuid NOT NULL,
    user_id uuid,
    full_name character varying(128) NOT NULL,
    national_id character varying(32),
    phone character varying(32),
    base_salary numeric(12,2) NOT NULL,
    hire_date date NOT NULL,
    is_active boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: financial_categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.financial_categories (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(128) NOT NULL,
    type character varying(16) DEFAULT 'expense'::character varying NOT NULL,
    color character varying(16) DEFAULT '#64748b'::character varying,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: hr_advances; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hr_advances (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    employee_id uuid NOT NULL,
    amount numeric(12,2) NOT NULL,
    date date DEFAULT CURRENT_DATE NOT NULL,
    note text,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    record_type character varying(16) DEFAULT 'سلفة'::character varying
);


--
-- Name: hr_attendance; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hr_attendance (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    employee_id uuid NOT NULL,
    work_date date NOT NULL,
    check_in timestamp with time zone,
    check_out timestamp with time zone,
    status character varying(16) DEFAULT 'present'::character varying,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    edited boolean DEFAULT false,
    edited_by character varying(128),
    edit_reason text,
    excuse_no_late boolean DEFAULT false,
    excuse_no_early boolean DEFAULT false,
    excuse_allow_overtime boolean DEFAULT false,
    shift_override character varying(32)
);


--
-- Name: hr_audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hr_audit_log (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    action_type character varying(32) NOT NULL,
    entity_type character varying(32) NOT NULL,
    entity_id character varying(64),
    performed_by uuid,
    reason text,
    details jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: hr_employees; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hr_employees (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid,
    emp_code character varying(32),
    name character varying(128) NOT NULL,
    "position" character varying(64),
    monthly_salary numeric(12,2) DEFAULT 0 NOT NULL,
    shift_schedule character varying(64),
    hire_date date,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    shift_id character varying(32),
    max_lateness_before_overtime_cancellation integer DEFAULT 30,
    ignore_lateness boolean DEFAULT false
);


--
-- Name: hr_payroll; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hr_payroll (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    employee_id uuid NOT NULL,
    month character varying(7) NOT NULL,
    base_salary numeric(12,2) NOT NULL,
    working_days smallint DEFAULT 0,
    absent_days smallint DEFAULT 0,
    overtime_hours numeric(6,2) DEFAULT 0,
    overtime_pay numeric(12,2) DEFAULT 0,
    bonus numeric(12,2) DEFAULT 0,
    deductions numeric(12,2) DEFAULT 0,
    advances numeric(12,2) DEFAULT 0,
    drawer_variance numeric(12,2) DEFAULT 0,
    net_salary numeric(12,2) DEFAULT 0 NOT NULL,
    status character varying(16) DEFAULT 'draft'::character varying,
    notes text,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    actual_working_days smallint DEFAULT 0,
    vacation_days smallint DEFAULT 0,
    total_hours numeric(8,2) DEFAULT 0,
    lateness_minutes integer DEFAULT 0,
    early_leave_minutes integer DEFAULT 0,
    missing_scan_minutes integer DEFAULT 0,
    lateness_deduction numeric(12,2) DEFAULT 0,
    bonus_days smallint DEFAULT 0,
    bonus_payment numeric(12,2) DEFAULT 0,
    hourly_rate numeric(10,4) DEFAULT 0,
    daily_breakdown jsonb
);


--
-- Name: hr_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hr_settings (
    key character varying(64) NOT NULL,
    value text NOT NULL
);


--
-- Name: hr_shifts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hr_shifts (
    id character varying(32) NOT NULL,
    name character varying(128) NOT NULL,
    start_time character varying(8) NOT NULL,
    end_time character varying(8) NOT NULL,
    description text DEFAULT ''::text
);


--
-- Name: invoice_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.invoice_seq
    START WITH 1000
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: payment_wallets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payment_wallets (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL,
    type text NOT NULL,
    phone text,
    balance numeric(14,2) DEFAULT 0 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT payment_wallets_type_check CHECK ((type = ANY (ARRAY['vodafone_cash'::text, 'instapay'::text, 'cash'::text])))
);


--
-- Name: payroll_entries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payroll_entries (
    id uuid NOT NULL,
    period_id uuid NOT NULL,
    employee_id uuid NOT NULL,
    base_salary numeric(12,2) NOT NULL,
    bonuses numeric(12,2) NOT NULL,
    deductions numeric(12,2) NOT NULL,
    notes text
);


--
-- Name: payroll_periods; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payroll_periods (
    id uuid NOT NULL,
    month smallint NOT NULL,
    year smallint NOT NULL,
    status character varying(16) NOT NULL,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: products; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.products (
    id uuid NOT NULL,
    subcategory_id uuid NOT NULL,
    name character varying(256) NOT NULL,
    barcode character varying(64),
    unit character varying(32) NOT NULL,
    retail_price numeric(12,2) NOT NULL,
    wholesale_price numeric(12,2) NOT NULL,
    cost_price numeric(12,2) NOT NULL,
    company character varying(128),
    size character varying(64),
    type character varying(64),
    material character varying(64),
    image_url character varying(512),
    is_active boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    reorder_point numeric(12,3) DEFAULT 0,
    reorder_qty numeric(12,3) DEFAULT 0,
    stock_status text DEFAULT 'tracked'::text NOT NULL,
    CONSTRAINT products_stock_status_check CHECK ((stock_status = ANY (ARRAY['tracked'::text, 'untracked'::text])))
);


--
-- Name: purchase_order_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.purchase_order_items (
    id uuid NOT NULL,
    po_id uuid NOT NULL,
    product_id uuid NOT NULL,
    qty_ordered numeric(12,3) NOT NULL,
    qty_received numeric(12,3) NOT NULL,
    unit_cost numeric(12,2) NOT NULL,
    notes text
);


--
-- Name: purchase_orders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.purchase_orders (
    id uuid NOT NULL,
    po_number character varying(32) NOT NULL,
    supplier_id uuid,
    warehouse_id uuid NOT NULL,
    created_by uuid NOT NULL,
    status public.po_status_enum NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    received_at timestamp with time zone,
    amount_paid numeric(14,2) DEFAULT 0,
    received_by_name text,
    invoice_image_url text
);


--
-- Name: purchase_price_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.purchase_price_history (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    product_id uuid NOT NULL,
    po_id uuid,
    supplier_id uuid,
    old_cost numeric(12,2),
    new_cost numeric(12,2) NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: purchase_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.purchase_seq
    START WITH 1000
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: quotation_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.quotation_seq
    START WITH 1000
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: safe_deposits; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.safe_deposits (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    safe_id uuid NOT NULL,
    shift_id uuid,
    warehouse_id uuid,
    amount numeric(14,2) NOT NULL,
    received_by uuid,
    received_by_name text,
    deposited_by uuid,
    deposited_by_name text,
    notes text,
    doc_number text,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: safe_transactions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.safe_transactions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    safe_id uuid NOT NULL,
    tx_type text NOT NULL,
    amount numeric(14,2) NOT NULL,
    balance_after numeric(14,2) NOT NULL,
    note text,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT safe_transactions_tx_type_check CHECK ((tx_type = ANY (ARRAY['deposit'::text, 'withdraw'::text])))
);


--
-- Name: safes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.safes (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL,
    location text,
    balance numeric(14,2) DEFAULT 0 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    safe_type text DEFAULT 'permanent'::text NOT NULL,
    CONSTRAINT safes_safe_type_check CHECK ((safe_type = ANY (ARRAY['permanent'::text, 'temporary'::text])))
);


--
-- Name: sale_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sale_items (
    id uuid NOT NULL,
    sale_id uuid NOT NULL,
    product_id uuid NOT NULL,
    qty numeric(12,3) NOT NULL,
    unit_price numeric(12,2) NOT NULL,
    unit_cost numeric(12,2) NOT NULL,
    discount numeric(12,2) NOT NULL
);


--
-- Name: sales; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sales (
    id uuid NOT NULL,
    invoice_number character varying(32) NOT NULL,
    customer_id uuid,
    warehouse_id uuid NOT NULL,
    cashier_id uuid NOT NULL,
    shift_id uuid,
    sale_mode public.sale_mode_enum NOT NULL,
    status public.sale_status_enum NOT NULL,
    discount_amount numeric(12,2) NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    is_credit boolean DEFAULT false NOT NULL,
    created_by uuid,
    payment_method text DEFAULT 'cash'::text,
    wallet_id uuid
);


--
-- Name: shifts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.shifts (
    id uuid NOT NULL,
    cashier_id uuid,
    status public.shift_status_enum NOT NULL,
    initial_amount numeric(12,2) NOT NULL,
    closing_balance numeric(12,2),
    next_day_drawer numeric(12,2),
    closed_by uuid,
    notes text,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    closed_at timestamp with time zone,
    warehouse_id uuid,
    supervisor_id uuid,
    deposit_received_by uuid,
    deposit_amount numeric(12,2)
);


--
-- Name: stock_movements; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.stock_movements (
    id uuid NOT NULL,
    product_id uuid NOT NULL,
    warehouse_id uuid NOT NULL,
    movement_type public.movement_type_enum NOT NULL,
    qty numeric(12,3) NOT NULL,
    unit_cost numeric(12,2) NOT NULL,
    unit_price numeric(12,2) NOT NULL,
    ref_id uuid,
    ref_type character varying(32),
    note text,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: store_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.store_settings (
    key character varying(64) NOT NULL,
    value text NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: subcategories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.subcategories (
    id uuid NOT NULL,
    category_id uuid NOT NULL,
    name character varying(128) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: supplier_transactions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.supplier_transactions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    supplier_id uuid NOT NULL,
    amount numeric(14,2) NOT NULL,
    type text NOT NULL,
    reference_doc text,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT supplier_transactions_type_check CHECK ((type = ANY (ARRAY['debit'::text, 'credit'::text])))
);


--
-- Name: suppliers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.suppliers (
    id uuid NOT NULL,
    name character varying(128) NOT NULL,
    phone character varying(32),
    address text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    type text DEFAULT 'supplier'::text NOT NULL,
    balance numeric(14,2) DEFAULT 0 NOT NULL,
    notes text
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id uuid NOT NULL,
    username character varying(64) NOT NULL,
    full_name character varying(128) NOT NULL,
    role character varying(32) NOT NULL,
    password_hash character varying(256) NOT NULL,
    is_active boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    permissions jsonb DEFAULT '["pos", "inventory", "reports", "archive", "settings"]'::jsonb,
    is_manager boolean DEFAULT false NOT NULL,
    default_warehouse_id uuid
);


--
-- Name: warehouses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.warehouses (
    id uuid NOT NULL,
    code character varying(32) NOT NULL,
    name character varying(128) NOT NULL,
    is_active boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    warehouse_type character varying(20) DEFAULT 'warehouse'::character varying NOT NULL
);


--
-- Name: archived_documents archived_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.archived_documents
    ADD CONSTRAINT archived_documents_pkey PRIMARY KEY (id);


--
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (id);


--
-- Name: categories categories_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_name_key UNIQUE (name);


--
-- Name: categories categories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_pkey PRIMARY KEY (id);


--
-- Name: customer_payments customer_payments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customer_payments
    ADD CONSTRAINT customer_payments_pkey PRIMARY KEY (id);


--
-- Name: customers customers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT customers_pkey PRIMARY KEY (id);


--
-- Name: drawer_transactions drawer_transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.drawer_transactions
    ADD CONSTRAINT drawer_transactions_pkey PRIMARY KEY (id);


--
-- Name: employees employees_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employees
    ADD CONSTRAINT employees_pkey PRIMARY KEY (id);


--
-- Name: financial_categories financial_categories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financial_categories
    ADD CONSTRAINT financial_categories_pkey PRIMARY KEY (id);


--
-- Name: hr_advances hr_advances_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hr_advances
    ADD CONSTRAINT hr_advances_pkey PRIMARY KEY (id);


--
-- Name: hr_attendance hr_attendance_employee_id_work_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hr_attendance
    ADD CONSTRAINT hr_attendance_employee_id_work_date_key UNIQUE (employee_id, work_date);


--
-- Name: hr_attendance hr_attendance_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hr_attendance
    ADD CONSTRAINT hr_attendance_pkey PRIMARY KEY (id);


--
-- Name: hr_audit_log hr_audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hr_audit_log
    ADD CONSTRAINT hr_audit_log_pkey PRIMARY KEY (id);


--
-- Name: hr_employees hr_employees_emp_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hr_employees
    ADD CONSTRAINT hr_employees_emp_code_key UNIQUE (emp_code);


--
-- Name: hr_employees hr_employees_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hr_employees
    ADD CONSTRAINT hr_employees_pkey PRIMARY KEY (id);


--
-- Name: hr_payroll hr_payroll_employee_id_month_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hr_payroll
    ADD CONSTRAINT hr_payroll_employee_id_month_key UNIQUE (employee_id, month);


--
-- Name: hr_payroll hr_payroll_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hr_payroll
    ADD CONSTRAINT hr_payroll_pkey PRIMARY KEY (id);


--
-- Name: hr_settings hr_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hr_settings
    ADD CONSTRAINT hr_settings_pkey PRIMARY KEY (key);


--
-- Name: hr_shifts hr_shifts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hr_shifts
    ADD CONSTRAINT hr_shifts_pkey PRIMARY KEY (id);


--
-- Name: payment_wallets payment_wallets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_wallets
    ADD CONSTRAINT payment_wallets_pkey PRIMARY KEY (id);


--
-- Name: payroll_entries payroll_entries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payroll_entries
    ADD CONSTRAINT payroll_entries_pkey PRIMARY KEY (id);


--
-- Name: payroll_periods payroll_periods_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payroll_periods
    ADD CONSTRAINT payroll_periods_pkey PRIMARY KEY (id);


--
-- Name: products products_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_pkey PRIMARY KEY (id);


--
-- Name: purchase_order_items purchase_order_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_order_items
    ADD CONSTRAINT purchase_order_items_pkey PRIMARY KEY (id);


--
-- Name: purchase_orders purchase_orders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_orders
    ADD CONSTRAINT purchase_orders_pkey PRIMARY KEY (id);


--
-- Name: purchase_orders purchase_orders_po_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_orders
    ADD CONSTRAINT purchase_orders_po_number_key UNIQUE (po_number);


--
-- Name: purchase_price_history purchase_price_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_price_history
    ADD CONSTRAINT purchase_price_history_pkey PRIMARY KEY (id);


--
-- Name: safe_deposits safe_deposits_doc_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.safe_deposits
    ADD CONSTRAINT safe_deposits_doc_number_key UNIQUE (doc_number);


--
-- Name: safe_deposits safe_deposits_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.safe_deposits
    ADD CONSTRAINT safe_deposits_pkey PRIMARY KEY (id);


--
-- Name: safe_transactions safe_transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.safe_transactions
    ADD CONSTRAINT safe_transactions_pkey PRIMARY KEY (id);


--
-- Name: safes safes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.safes
    ADD CONSTRAINT safes_pkey PRIMARY KEY (id);


--
-- Name: sale_items sale_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sale_items
    ADD CONSTRAINT sale_items_pkey PRIMARY KEY (id);


--
-- Name: sales sales_invoice_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales
    ADD CONSTRAINT sales_invoice_number_key UNIQUE (invoice_number);


--
-- Name: sales sales_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales
    ADD CONSTRAINT sales_pkey PRIMARY KEY (id);


--
-- Name: shifts shifts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shifts
    ADD CONSTRAINT shifts_pkey PRIMARY KEY (id);


--
-- Name: stock_movements stock_movements_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_movements
    ADD CONSTRAINT stock_movements_pkey PRIMARY KEY (id);


--
-- Name: store_settings store_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.store_settings
    ADD CONSTRAINT store_settings_pkey PRIMARY KEY (key);


--
-- Name: subcategories subcategories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.subcategories
    ADD CONSTRAINT subcategories_pkey PRIMARY KEY (id);


--
-- Name: supplier_transactions supplier_transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.supplier_transactions
    ADD CONSTRAINT supplier_transactions_pkey PRIMARY KEY (id);


--
-- Name: suppliers suppliers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.suppliers
    ADD CONSTRAINT suppliers_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- Name: warehouses warehouses_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.warehouses
    ADD CONSTRAINT warehouses_code_key UNIQUE (code);


--
-- Name: warehouses warehouses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.warehouses
    ADD CONSTRAINT warehouses_pkey PRIMARY KEY (id);


--
-- Name: idx_audit_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_created ON public.audit_log USING btree (created_at DESC);


--
-- Name: idx_audit_entity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_entity ON public.audit_log USING btree (entity_type, entity_id);


--
-- Name: idx_audit_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_user ON public.audit_log USING btree (user_id);


--
-- Name: idx_pph_product; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pph_product ON public.purchase_price_history USING btree (product_id);


--
-- Name: idx_sup_tx_supplier; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_sup_tx_supplier ON public.supplier_transactions USING btree (supplier_id);


--
-- Name: ix_archived_documents_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_archived_documents_created_at ON public.archived_documents USING btree (created_at);


--
-- Name: ix_archived_documents_doc_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_archived_documents_doc_type ON public.archived_documents USING btree (doc_type);


--
-- Name: ix_archived_documents_ref_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_archived_documents_ref_id ON public.archived_documents USING btree (ref_id);


--
-- Name: ix_customer_payments_customer_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_customer_payments_customer_id ON public.customer_payments USING btree (customer_id);


--
-- Name: ix_drawer_transactions_shift_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_drawer_transactions_shift_id ON public.drawer_transactions USING btree (shift_id);


--
-- Name: ix_products_barcode; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_products_barcode ON public.products USING btree (barcode);


--
-- Name: ix_sale_items_product_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sale_items_product_id ON public.sale_items USING btree (product_id);


--
-- Name: ix_sale_items_sale_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sale_items_sale_id ON public.sale_items USING btree (sale_id);


--
-- Name: ix_sales_cashier_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sales_cashier_id ON public.sales USING btree (cashier_id);


--
-- Name: ix_sales_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sales_created_at ON public.sales USING btree (created_at);


--
-- Name: ix_sales_customer_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sales_customer_id ON public.sales USING btree (customer_id);


--
-- Name: ix_sales_shift_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sales_shift_id ON public.sales USING btree (shift_id);


--
-- Name: ix_stock_movements_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_stock_movements_created_at ON public.stock_movements USING btree (created_at);


--
-- Name: ix_stock_movements_product_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_stock_movements_product_id ON public.stock_movements USING btree (product_id);


--
-- Name: ix_stock_movements_ref_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_stock_movements_ref_id ON public.stock_movements USING btree (ref_id);


--
-- Name: ix_stock_movements_warehouse_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_stock_movements_warehouse_id ON public.stock_movements USING btree (warehouse_id);


--
-- Name: archived_documents archived_documents_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.archived_documents
    ADD CONSTRAINT archived_documents_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: audit_log audit_log_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: customer_payments customer_payments_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customer_payments
    ADD CONSTRAINT customer_payments_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: customer_payments customer_payments_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customer_payments
    ADD CONSTRAINT customer_payments_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(id) ON DELETE CASCADE;


--
-- Name: drawer_transactions drawer_transactions_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.drawer_transactions
    ADD CONSTRAINT drawer_transactions_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.financial_categories(id);


--
-- Name: drawer_transactions drawer_transactions_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.drawer_transactions
    ADD CONSTRAINT drawer_transactions_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: drawer_transactions drawer_transactions_shift_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.drawer_transactions
    ADD CONSTRAINT drawer_transactions_shift_id_fkey FOREIGN KEY (shift_id) REFERENCES public.shifts(id) ON DELETE CASCADE;


--
-- Name: drawer_transactions drawer_transactions_wallet_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.drawer_transactions
    ADD CONSTRAINT drawer_transactions_wallet_id_fkey FOREIGN KEY (wallet_id) REFERENCES public.payment_wallets(id) ON DELETE SET NULL;


--
-- Name: employees employees_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employees
    ADD CONSTRAINT employees_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: hr_advances hr_advances_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hr_advances
    ADD CONSTRAINT hr_advances_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: hr_advances hr_advances_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hr_advances
    ADD CONSTRAINT hr_advances_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.hr_employees(id);


--
-- Name: hr_attendance hr_attendance_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hr_attendance
    ADD CONSTRAINT hr_attendance_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.hr_employees(id) ON DELETE CASCADE;


--
-- Name: hr_audit_log hr_audit_log_performed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hr_audit_log
    ADD CONSTRAINT hr_audit_log_performed_by_fkey FOREIGN KEY (performed_by) REFERENCES public.users(id);


--
-- Name: hr_employees hr_employees_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hr_employees
    ADD CONSTRAINT hr_employees_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: hr_payroll hr_payroll_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hr_payroll
    ADD CONSTRAINT hr_payroll_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: hr_payroll hr_payroll_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hr_payroll
    ADD CONSTRAINT hr_payroll_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.hr_employees(id);


--
-- Name: payroll_entries payroll_entries_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payroll_entries
    ADD CONSTRAINT payroll_entries_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(id);


--
-- Name: payroll_entries payroll_entries_period_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payroll_entries
    ADD CONSTRAINT payroll_entries_period_id_fkey FOREIGN KEY (period_id) REFERENCES public.payroll_periods(id) ON DELETE CASCADE;


--
-- Name: payroll_periods payroll_periods_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payroll_periods
    ADD CONSTRAINT payroll_periods_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: products products_subcategory_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_subcategory_id_fkey FOREIGN KEY (subcategory_id) REFERENCES public.subcategories(id) ON DELETE RESTRICT;


--
-- Name: purchase_order_items purchase_order_items_po_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_order_items
    ADD CONSTRAINT purchase_order_items_po_id_fkey FOREIGN KEY (po_id) REFERENCES public.purchase_orders(id) ON DELETE CASCADE;


--
-- Name: purchase_order_items purchase_order_items_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_order_items
    ADD CONSTRAINT purchase_order_items_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id) ON DELETE RESTRICT;


--
-- Name: purchase_orders purchase_orders_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_orders
    ADD CONSTRAINT purchase_orders_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: purchase_orders purchase_orders_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_orders
    ADD CONSTRAINT purchase_orders_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.suppliers(id) ON DELETE SET NULL;


--
-- Name: purchase_orders purchase_orders_warehouse_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_orders
    ADD CONSTRAINT purchase_orders_warehouse_id_fkey FOREIGN KEY (warehouse_id) REFERENCES public.warehouses(id);


--
-- Name: purchase_price_history purchase_price_history_po_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_price_history
    ADD CONSTRAINT purchase_price_history_po_id_fkey FOREIGN KEY (po_id) REFERENCES public.purchase_orders(id) ON DELETE SET NULL;


--
-- Name: purchase_price_history purchase_price_history_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_price_history
    ADD CONSTRAINT purchase_price_history_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id) ON DELETE CASCADE;


--
-- Name: purchase_price_history purchase_price_history_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_price_history
    ADD CONSTRAINT purchase_price_history_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.suppliers(id) ON DELETE SET NULL;


--
-- Name: safe_deposits safe_deposits_deposited_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.safe_deposits
    ADD CONSTRAINT safe_deposits_deposited_by_fkey FOREIGN KEY (deposited_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: safe_deposits safe_deposits_received_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.safe_deposits
    ADD CONSTRAINT safe_deposits_received_by_fkey FOREIGN KEY (received_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: safe_deposits safe_deposits_safe_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.safe_deposits
    ADD CONSTRAINT safe_deposits_safe_id_fkey FOREIGN KEY (safe_id) REFERENCES public.safes(id);


--
-- Name: safe_deposits safe_deposits_shift_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.safe_deposits
    ADD CONSTRAINT safe_deposits_shift_id_fkey FOREIGN KEY (shift_id) REFERENCES public.shifts(id) ON DELETE SET NULL;


--
-- Name: safe_deposits safe_deposits_warehouse_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.safe_deposits
    ADD CONSTRAINT safe_deposits_warehouse_id_fkey FOREIGN KEY (warehouse_id) REFERENCES public.warehouses(id) ON DELETE SET NULL;


--
-- Name: safe_transactions safe_transactions_safe_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.safe_transactions
    ADD CONSTRAINT safe_transactions_safe_id_fkey FOREIGN KEY (safe_id) REFERENCES public.safes(id);


--
-- Name: sale_items sale_items_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sale_items
    ADD CONSTRAINT sale_items_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id) ON DELETE RESTRICT;


--
-- Name: sale_items sale_items_sale_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sale_items
    ADD CONSTRAINT sale_items_sale_id_fkey FOREIGN KEY (sale_id) REFERENCES public.sales(id) ON DELETE CASCADE;


--
-- Name: sales sales_cashier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales
    ADD CONSTRAINT sales_cashier_id_fkey FOREIGN KEY (cashier_id) REFERENCES public.users(id);


--
-- Name: sales sales_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales
    ADD CONSTRAINT sales_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: sales sales_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales
    ADD CONSTRAINT sales_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(id) ON DELETE SET NULL;


--
-- Name: sales sales_shift_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales
    ADD CONSTRAINT sales_shift_id_fkey FOREIGN KEY (shift_id) REFERENCES public.shifts(id);


--
-- Name: sales sales_wallet_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales
    ADD CONSTRAINT sales_wallet_id_fkey FOREIGN KEY (wallet_id) REFERENCES public.payment_wallets(id) ON DELETE SET NULL;


--
-- Name: sales sales_warehouse_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales
    ADD CONSTRAINT sales_warehouse_id_fkey FOREIGN KEY (warehouse_id) REFERENCES public.warehouses(id);


--
-- Name: shifts shifts_cashier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shifts
    ADD CONSTRAINT shifts_cashier_id_fkey FOREIGN KEY (cashier_id) REFERENCES public.users(id);


--
-- Name: shifts shifts_closed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shifts
    ADD CONSTRAINT shifts_closed_by_fkey FOREIGN KEY (closed_by) REFERENCES public.users(id);


--
-- Name: shifts shifts_deposit_received_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shifts
    ADD CONSTRAINT shifts_deposit_received_by_fkey FOREIGN KEY (deposit_received_by) REFERENCES public.users(id);


--
-- Name: shifts shifts_supervisor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shifts
    ADD CONSTRAINT shifts_supervisor_id_fkey FOREIGN KEY (supervisor_id) REFERENCES public.users(id);


--
-- Name: shifts shifts_warehouse_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shifts
    ADD CONSTRAINT shifts_warehouse_id_fkey FOREIGN KEY (warehouse_id) REFERENCES public.warehouses(id);


--
-- Name: stock_movements stock_movements_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_movements
    ADD CONSTRAINT stock_movements_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: stock_movements stock_movements_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_movements
    ADD CONSTRAINT stock_movements_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id) ON DELETE RESTRICT;


--
-- Name: stock_movements stock_movements_warehouse_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_movements
    ADD CONSTRAINT stock_movements_warehouse_id_fkey FOREIGN KEY (warehouse_id) REFERENCES public.warehouses(id) ON DELETE RESTRICT;


--
-- Name: subcategories subcategories_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.subcategories
    ADD CONSTRAINT subcategories_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id) ON DELETE CASCADE;


--
-- Name: supplier_transactions supplier_transactions_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.supplier_transactions
    ADD CONSTRAINT supplier_transactions_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.suppliers(id) ON DELETE CASCADE;


--
-- Name: users users_default_warehouse_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_default_warehouse_id_fkey FOREIGN KEY (default_warehouse_id) REFERENCES public.warehouses(id) ON DELETE SET NULL;


--
-- PostgreSQL database dump complete
--

\unrestrict 7gvOzt0a84qKVLxmkQyriQs10rEffhCYfdIX6dqsuPjf8HxC0gFdf4aZihe2SQU

