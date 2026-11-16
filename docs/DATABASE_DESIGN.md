# Mizan ERP — Database Design & Multi-Tenancy

## 1. Multi-Tenancy Architecture
Mizan enforces a hybrid, multi-layered isolation model to ensure that no tenant can ever read or mutate another tenant's records:

1. **Application-Layer Scoping** (`app/platform/tenancy/context.py`):
   - All tenant-owned models inherit `TenantScoped` (`tenant_id` UUID, references `tenants`, not null, indexed).
   - A `before_flush` hook stamps the bound workspace's `tenant_id` on new rows (and refuses a row carrying another one).
   - Every ORM select, update and delete gets `tenant_id = <bound workspace>` added (`with_loader_criteria`).

2. **Database-Layer Row-Level Security (RLS):**
   - RLS is enabled and forced on every workspace table: `USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')`.
   - `bind_tenant` sets `app.tenant_id` for the transaction, and every later transaction of the session sets it again (`after_begin`).
   - While a workspace is bound, transactions run as the **`mizan_app`** role (`SET LOCAL ROLE`), which can't bypass RLS: the login role may (Neon's owner, a local superuser), so raw SQL is isolated too (#112). Request code never runs DDL or writes platform rows while bound.
   - Work that spans workspaces (the scheduler, cross-workspace lookups such as an installation token or a theme's font) turns `app.bypass` on for that transaction only, and off again before binding a workspace.

## 2. Core Entity Relationship Overview

```
[Tenants] 1 ─── N [HealthcareOrganizations]
                       │ 1
                       ├─── N [Facilities / Hospitals]
                       │         │ 1
                       │         ├─── N [Buildings] ─── N [Floors] ─── N [Rooms/Beds]
                       │         └─── N [Departments] ─── N [Units] ─── N [ServiceLocations]
                       │
                       └─── N [Patients (Master Patient Index)]
                                 │ 1
                                 ├─── N [Appointments]
                                 ├─── N [Clinical Encounters (EMR)]
                                 ├─── N [Lab Orders]
                                 ├─── N [Prescriptions]
                                 └─── N [Inpatient Admissions]
```

In the clinic module, `clinic_appointments`, `clinic_encounters`, `clinic_prescriptions` and
`clinic_lab_orders` have a nullable `doctor_user_id` (→ `users`, `ON DELETE SET NULL`) next to the
free-text `doctor_name`: the clinician the record belongs to (v79; v79b linked existing records
whose `doctor_name` is exactly one active user's name, and put that user on the patient's care
team).

Since v85 (#36) `clinic_appointments` also has `department_id` (→ `clinic_departments`) and
`room_id` (→ `clinic_rooms`), both nullable with `ON DELETE SET NULL`; `department` keeps the
department's name. New bookings store `time_slot` as `HH:MM` (24h); older rows keep their free text
("10:30 AM"), which the booking rules still read. No two non-cancelled appointments overlap for the
same doctor or the same room on a date (checked by the API: each lasts its doctor's roster slot).

`clinic_encounters.blood_glucose` (v87, #42): blood glucose in mg/dL, nullable (not every visit
measures it), next to the other vitals; `GET /clinic/patients/{id}/vitals-history` charts them.

Besides the ERP's own records, every workspace has (all tenant-scoped, with RLS):

| Table | What it holds |
|---|---|
| `community_modules` | Developers' modules installed in the workspace (ADR-007): manifest, entities, approved scopes, the hash of the installation token, the webhook secret; key `(tenant_id, module_id)` |
| `ext_records` | Records of every community module's entities, as JSONB validated against the entity |
| `community_webhook_deliveries` | Webhooks to modules' servers: payload, status, attempts, next attempt, last error |
| `workspace_themes` | Theme packages installed in the workspace (ADR-010), with their font files; the chosen theme is `tenants.palette["name"]` |
| `workspace_files` | Every uploaded file and its size (#114); private files (kinds `clinic_signature`, `clinic_image`) have a `private:…` key in `url` (PRIVATE_UPLOAD_DIR, never served by URL) |
| `clinic_care_team` | A patient's care team (#113): `patient_id` → `clinic_patients`, `user_id` → `users`, `role` (`attending`, `consultant`, `nurse`, `other`), `added_by`, `created_at`, `ended_at` (members are ended, not deleted); one active membership per (patient, user) |
| `clinic_access_grants` | Break-glass grants (#113): patient, user, `reason`, `starts_at`, `expires_at` (60 minutes), `revoked_at`, `reviewed_by`/`reviewed_at`/`review_note` |
| `clinic_access_log` | One row per read of clinical data (#113): `user_id`, `user_name`, `patient_id` (`NULL` for a list), `resource` (`patient`, `encounters`, `prescriptions`, `lab_orders`, `referrals`, `referral`, …), `how` (`all`, `setting`, `team`, `break_glass`, `queue`, `referral`), `rows`; no foreign key to the patient, so it outlives the record |
| `clinic_departments` | Department master (#36, v85): `code` (unique per workspace), `name`, `specialty_code`, `active`; a clinic with none gets the usual departments on its first read |
| `clinic_rooms` | Examination rooms (#36): `name`, `department_id` (→ `clinic_departments`, nullable: shared), `active` |
| `clinic_doctor_schedules` | Doctors' weekly rosters (#36): `doctor_user_id` → `users`, `department_id`, `room_id`, `weekday` (0 = Monday … 6 = Sunday), `start_time`/`end_time` (`HH:MM`), `slot_minutes`, `active`; rows of the same doctor or room don't overlap |
| `clinic_referrals` | Referrals (#45, v86): `referral_ref`, `patient_id`, `from_doctor_user_id`/`from_doctor_name`, `to_department_id` → `clinic_departments`, `to_doctor_user_id` (nullable: any doctor on the department's roster), `priority` (`routine`, `urgent`, `emergency`), `reason`, `triage_notes`, `status` (`pending`, `accepted`, `declined`, `completed`), `encounter_id`, `responded_by`/`responded_at`/`response_note`; accepting puts the receiving doctor on the care team |
| `clinic_consent_forms` | Signed consents (#43, v88): `consent_ref`, `patient_id`, `encounter_id`, `kind` (`procedure`, `surgery`, `data_sharing`, `other`), `title`, `body`, `signer_name`, `signer_relation` (`self`, `guardian`, `parent`, `spouse`, `other`), `signature_path` (the PNG's key in the private file store, never a URL or base64), `signed_at`, `witness_user_id`/`witness_name` (the clinician), `revoked_at`/`revoked_by`/`revoke_reason` (withdrawn, never deleted) |
| `clinic_images` | Medical images (#44, v89): `patient_id`, `encounter_id`, `modality` (`XR`, `US`, `CT`, `MRI`, `other`), `file_path` (the key in the private file store), `content_type` (`image/jpeg`, `image/png`, `image/webp`, `application/dicom`, read from the bytes), `size`, `original_name`, `notes`, `uploaded_by`/`uploaded_by_name` |
| `activity_changes` | Owners' requests to change the workspace's activity and the Mizan team's decisions (#107); read across workspaces by the owner and admin APIs with `app.bypass` |

### Money documents in sales, POS and stock (ADR-014 D4, D5; migration `v80`)

| Column | What it means |
|---|---|
| `sales.return_of` | A return is its own document: a `sales` row with status `returned`, number `RET-…`, its returned lines (at the cost they left at), its own totals (`total` = returned lines, `discount_amount` = its share of the sale's invoice discount, `net_total` = refunded) and refund lines in `sale_payments`, pointing to the sale it returns. The sale stays `confirmed` and its `returns_total` grows. Partial returns made before `v80` were linked from the "مرتجع جزئي من …" text of their notes and got their totals from their lines; full returns made before `v80` (the sale itself marked `returned`) are left as they were. |
| `sale_payments.safe_id` | The safe a payment went into when it didn't go through a drawer (a quotation confirmed into a safe). Bank and cheque lines are recorded with no account yet (ADR-014 D12, step 2). A cancelled sale keeps its `sale_payments` rows; reports count only `confirmed` sales. |
| `drawer_transactions.cancelled_at`, `cancelled_by` | Drawer rows are cancelled, never deleted. Shift summaries, the ledger and the reports skip cancelled rows. Cancelling a sale cancels its drawer rows. |
| `drawer_transactions.customer_payment_id` | The customer receipt a drawer deposit recorded; cancelling the row adds a negative receipt and puts the debt back. |
| `products.avg_cost` | Weighted moving average cost, per workspace (not per branch), started from `cost_price`. Every costed receipt (purchase, opening stock, a return at the cost the line left at, an adjustment with a cost) recomputes it in `inventory.services.stock.apply_movement`; every other movement and every sale line (`sale_items.unit_cost`) is recorded at it, whatever the client sends. `cost_price` stays the last purchase price. |

### Money documents: where the money went (ADR-014 D4, migration `v81_money_flows_finance`)

Every payment names the safe or wallet its money moved through, and safes and wallets change only
through `finance/services/safes.py`, `wallets.record_wallet_tx` and `finance/services/payments.py`
(`money_in` / `money_out`; payments other than expenses never take a safe or wallet below zero).
A bank account, used for bank transfers and cheques, is a safe with `safe_type = 'bank'`.

| Table | Columns | Meaning |
|---|---|---|
| `safes` | `safe_type` | `permanent`, `temporary` or `bank` (CHECK) |
| `safe_transactions` | `ref_type`, `ref_id` | The document behind each movement: `expense`, `expense_cancel`, `customer_payment`, `supplier_payment`, `purchase`, `payroll`, `hr_advance` |
| `wallet_transactions` | `tx_type`, `ref_id` | Same idea (`tx_type` carries the document kind); resetting a wallet is an `adjustment` row |
| `expenses` | `status`, `cancelled_at`, `cancelled_by`, `cancel_reason` | `draft` → `approved` (money leaves the safe/wallet) or `rejected`; an approved expense is `cancelled`, which puts the money back, never deleted. Approving needs a safe or wallet. Payroll expenses have `payment_method = 'payroll'` and are managed from payroll |
| `customers` | `is_active` | A customer with sales, payments or adjustments is deactivated, not deleted |
| `customer_payments` | `method`, `safe_id`, `wallet_id`, `shift_id` | Where a receipt went: the cashier's open drawer (`shift_id`) or a safe/wallet. `customer_id` no longer cascades on delete. Amounts may be negative (reversals) |
| `customer_adjustments` (new) | `kind` (`opening`/`adjustment`), `amount` (signed), `balance_before`, `balance_after`, `note`, `created_by` | Every balance change that isn't a sale or payment (`PUT /customers/{id}/balance`) |
| `supplier_transactions` | `type`, `method`, `safe_id`, `wallet_id`, `purchase_id`, `created_by` | `type` is `debit` (we owe more: an invoice) or `credit` (a payment, from a safe/wallet). The unused duplicate `tx_type` column was dropped; `supplier_id` no longer cascades |
| `purchase_orders` | `safe_id`, `wallet_id` | Where `amount_paid` comes from; it leaves at receipt |
| `hr_advances` | `safe_id`, `wallet_id` | An advance (`record_type = 'سلفة'`) is paid out from here; `خصم` and `مكافأة` move no cash |
| `hr_payroll_periods` | `safe_id`, `wallet_id`, `paid_amount`, `expense_id` | Approving records the salaries expense (no money); paying moves `paid_amount` out once; a paid month can't be reopened, reopening an approved one cancels `expense_id` |

### Clinic invoices (ADR-014 D4; migration `v82`)

`clinic_invoices.sale_id`: a clinic invoice is one `sales` row (the patient's share), made at its first payment. Every payment is a `sale_payments` line on it, and cash goes into the cashier's open drawer. A payment can't be zero or more than what is left. Before, each payment made a new sale with the same invoice number; the migration links each invoice to the first of those.

### Purchase returns (ADR-014 D3, step 3; migration `v91_purchase_returns`)

Tenant tables with RLS. A return sends received goods of a purchase order back to the supplier.

| Table | Columns | Meaning |
|---|---|---|
| `purchase_returns` | `return_number` (`PRT-000001`, per workspace), `po_id`, `supplier_id`, `warehouse_id`, `total` (at the cost the goods came in at), `refund_amount`, `safe_id`, `wallet_id`, `notes`, `created_by` | One return document. `refund_amount` is the part the supplier paid back into the safe or wallet; the rest (`total − refund_amount`) lowers the supplier's balance, recorded as a `credit` row in `supplier_transactions` (reference = the return number) |
| `purchase_return_items` | `return_id`, `product_id`, `qty`, `unit_cost` | The lines. Per product, returns can't exceed what the order received minus what earlier returns took |
| `stock_movements.movement_type` | new value `return_out` | The stock leaving with a return, at the line's cost (not the average); the product's average cost is recalculated without those units. The enum value is added with `ALTER TYPE … ADD VALUE IF NOT EXISTS` |

`products` and the ledger need nothing else: stock adjustments, payroll, advances and clinic invoices are posted from
events and add no columns. The standard chart gains two roles, `inventory_loss` (expense 54) and
`insurance_receivables` (asset 127); existing workspaces get them the first time a rule needs them.

### The ledger (ADR-014 D1, D2, D7; migration `v90_accounting_ledger`, module `accounting`)

Tenant tables with RLS (`tenant_isolation`, USING and WITH CHECK). Money is `numeric(14,2)`.
Written only by `accounting/services/posting.py` (`post` / `reverse`), in the transaction of the
document that caused them. Posting starts when a workspace enables the module (no backfill; the
opening entry is step 4).

| Table | Columns | Meaning |
|---|---|---|
| `acc_accounts` | `code` (unique per workspace), `name`, `name_en`, `type` (`asset`/`liability`/`equity`/`income`/`expense`), `parent_id`, `is_group`, `role` (unique per workspace when set), `active` | The chart of accounts, copied from `accounting/charts/eg_standard.json` on first use. Posting rules find accounts by `role`; group accounts take no postings |
| `acc_entries` | `number` (`JE-000001`, per workspace), `date`, `source_type`, `source_id`, `event` (unique together per workspace), `memo`, `warehouse_id`, `created_by`, `reverses_id` | One journal entry. Never updated (trigger `acc_entries_immutable`) and never deleted by the app; corrected by a reversing entry (`event = 'reverse'`, `reverses_id`). `warehouse_id`/`created_by` carry no foreign key so deleting a branch or user never touches posted rows |
| `acc_lines` | `entry_id`, `account_id`, `debit`, `credit` (exactly one positive, CHECK), `party_type` (`customer`/`supplier`/`employee`), `party_id`, `warehouse_id` | The entry's lines. The deferred constraint triggers `acc_lines_balanced` / `acc_entries_balanced` refuse, at commit, an entry whose debits ≠ credits or total 0; `acc_lines_immutable` refuses updates |
| `acc_money_accounts` | `kind` (`safe`/`wallet`/`drawer`/`default_bank`), `ref_id`, `account_id` (unique per workspace, kind, ref) | The sub-account of each safe (bank safes under the bank group, others under the cash group), payment wallet, branch cashier drawer (`ref_id` = warehouse) and the default bank account, created on first use |
| `financial_categories` | `account_id` | The account a category posts to; none → other income / other expenses |
| `accounting_periods` | `reopened_by`, `reopened_at`, `reopen_reason` | Months close in order (every earlier month since the first entry or first closed month); reopening needs a reason (also in the audit log) and later months reopened first. Posting into a closed month is refused by the posting service |

## 3. Platform Tables (not tenant-scoped)

These belong to Mizan itself, not to a workspace, and have no RLS policy. Only the owner,
admin and website APIs (and the system API's sign-in) read them.

| Table | What it holds |
|---|---|
| `tenants` | Every workspace: slug, sector, plan, limits, trial/paid-until, status, `deployment_mode` (`cloud_saas`, `desktop`, `lan`) |
| `owner_accounts` | Business owners (ADR-004): one owner, many workspaces; their own credentials, email (with `email_verified_at`) and phone |
| `tenant_billing_invoices` | Subscription invoices per workspace |
| `payment_transactions` | Paymob transactions, one per callback, idempotent on Paymob's id |
| `licences` | One per single-device/LAN workspace (ADR-005): mode, `valid_until` (extended on payment), `revoked_at` |
| `installations` | Each on-site install that checked in: host name, OS, version, last IP, last backup, first/last seen |
| `platform_audit_logs` | Every change made in the admin panel |
| `sys_roles` (`tenant_id IS NULL`) | The platform's standard roles and their permissions (workspaces' own roles have a `tenant_id`) |
| `revoked_tokens` | Signed-out sessions (by token id), until they would have expired anyway (#77) |
| `owner_codes` | One-time codes emailed to owners: verify the address, reset the password (#71, #72); an HMAC of the code, expiry, tries, used |
| `owner_email_log` | Emails that must go out once (receipts, trial and renewal reminders), by (kind, ref) |
| `developer_users`, `developer_teams`, `developer_team_members` | The developer portal (ADR-007): developers (separate from owners), teams (a team's handle is its modules' namespace) and their members |
| `developer_keys` | Teams' signing keys and the certificates Mizan issued; `revoked_at` makes cloud installs refuse their packages |
| `developer_cli_tokens` | `mizan` CLI tokens (only their SHA-256) |
| `marketplace_versions` | Every package version developers sent to the marketplace (#105): the `.mzm` bytes, SHA-256, manifest, review status and note, and Mizan's `MZP1` countersignature once approved |
| `marketplace_items` | Listings: the current approved version, `listed`/`delisted` with a reason, install count |

On site, the install's private PostgreSQL holds one workspace and the same schema; the
licence and installation identity live in files under the data folder
(`app.onprem.state`), not in these tables.

## 4. Migration Rules
- Database schema changes are tracked in `shared/backend/app/db/migrations.py` under the ordered `MIGRATIONS` list and applied with `python manage.py db migrate`.
- Every migration must be **strictly idempotent** (`CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`).
- Migration runs execute statements sequentially with auto-healing and rollback safety.
- On-site installs run the same migrations during setup and on every repair/update, so migrations
  must also work on a fresh, single-workspace database.
- Production is migrated by the release workflow (`.github/workflows/deploy.yml`), before the new
  code is deployed: a migration must work with the code that's still running.
- **Models must match their migrations.** Local stacks, CI and on-site setup also create tables
  from the models (`create_all`) before migrations run, so a model declares the same primary key
  and database defaults (`server_default`, e.g. `gen_random_uuid()`) as its migration; otherwise
  those databases differ from production.
- Platform tables (no `tenant_id`) are written only outside a bound workspace (#112).
