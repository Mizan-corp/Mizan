// Accounting: the shapes of this module's API (paths under /accounting), used by its screens
// (ADR-014 step 5): the chart, the journal and its drafts (D9), the reports (D8, all read from the
// ledger only), the opening entry (D10) and the periods (D7).
// Amounts are numbers rounded to the piastre; dates are ISO strings (YYYY-MM-DD).

export type AccountType = "asset" | "liability" | "equity" | "income" | "expense";

export interface AccountRef {
  id: string;
  code: string;
  name: string;
  name_en: string | null;
  type: AccountType;
}

/** Filters every report takes: `warehouse_id` is the branch; lines with no branch are left out of a branch report. */
export interface ReportRange {
  from?: string;
  to?: string;
  warehouse_id?: string;
}

export interface TrialBalanceRow extends AccountRef {
  parent_id: string | null;
  is_group: boolean;
  level: number;
  role: string | null;
  active: boolean;
  opening: number;
  opening_debit: number;
  opening_credit: number;
  debit: number;
  credit: number;
  closing: number;
  closing_debit: number;
  closing_credit: number;
}

export interface TrialBalanceTotals {
  opening_debit: number;
  opening_credit: number;
  debit: number;
  credit: number;
  closing_debit: number;
  closing_credit: number;
}

/** GET /accounting/trial-balance?from&to&warehouse_id&include_zero&include_closing */
export interface TrialBalance {
  from: string | null;
  to: string | null;
  accounts: TrialBalanceRow[];
  totals: TrialBalanceTotals;
  balanced: boolean;
}

export interface StatementLine extends AccountRef {
  amount: number;
}

export interface StatementSection {
  lines: StatementLine[];
  total: number;
}

/** GET /accounting/income-statement?from&to&warehouse_id&include_closing (the closing entry is left out by default) */
export interface IncomeStatement {
  revenue: StatementSection;
  sales_returns: StatementSection;
  net_sales: number;
  cogs: StatementSection;
  gross_profit: number;
  operating_expenses: StatementSection;
  operating_profit: number;
  other_income: StatementSection;
  other_expenses: StatementSection;
  net_profit: number;
}

export interface BalanceSheetRow extends AccountRef {
  parent_id: string | null;
  is_group: boolean;
  level: number;
  amount: number;
}

/** GET /accounting/balance-sheet?as_of&warehouse_id&include_closing. `balanced` false means assets differ from liabilities + equity by `difference`. */
export interface BalanceSheet {
  as_of: string;
  fiscal_year_start: string;
  assets: { accounts: BalanceSheetRow[]; total: number };
  liabilities: { accounts: BalanceSheetRow[]; total: number };
  equity: {
    accounts: BalanceSheetRow[];
    accounts_total: number;
    prior_years_profit: number;
    current_year_profit: number;
    profit_to_date: number;
    total: number;
  };
  total_liabilities_and_equity: number;
  difference: number;
  balanced: boolean;
}

/** One line of a general ledger or a party statement, with the running balance. */
export interface StatementEntryLine {
  entry_id: string;
  number: string;
  date: string;
  source_type: string;
  source_id: string;
  event: string;
  memo: string | null;
  account_id: string;
  account_code: string;
  account_name: string;
  account_name_en: string | null;
  debit: number;
  credit: number;
  party_type: "customer" | "supplier" | "employee" | null;
  party_id: string | null;
  party_name: string | null;
  warehouse_id: string | null;
  balance: number;
}

export interface LinesPage {
  opening_balance: number;
  lines: StatementEntryLine[];
  page: number;
  page_size: number;
  count: number;
  total_debit: number;
  total_credit: number;
  closing_balance: number;
}

/** GET /accounting/general-ledger/{account_id}?from&to&warehouse_id&include_closing&page&page_size */
export interface GeneralLedger extends LinesPage {
  account: AccountRef & { is_group: boolean };
  normal_side: "debit" | "credit";
}

/** GET /accounting/party-statement/{customer|supplier|employee}/{id}: `difference` is operational minus ledger balance. */
export interface PartyStatement extends LinesPage {
  party: { type: "customer" | "supplier" | "employee"; id: string; name: string };
  meaning: "what_they_owe_us" | "what_we_owe_them";
  ledger_balance: number;
  operational_balance: number | null;
  difference: number | null;
  matches: boolean | null;
}

export interface ReconciliationItem {
  key: string;
  label: string;
  label_en: string;
  ledger: number;
  operational: number;
  difference: number;
  ok: boolean;
}

/** GET /accounting/reconciliation: flags only, nothing is changed. */
export interface Reconciliation {
  as_of: string;
  ok: boolean;
  items: ReconciliationItem[];
  differences: ReconciliationItem[];
  parties: { party_type: "customer" | "supplier"; id: string; name: string | null; ledger: number; operational: number; difference: number }[];
}

export interface VatCodeRow { tax_code: "standard" | "zero" | "exempt"; label: string; rate: number; taxable: number; tax: number; documents: number }

/** GET /accounting/vat-report (ADR-014 D6): the ledger's VAT accounts, and the documents' VAT by tax code. */
export interface VatReport {
  from: string | null;
  to: string | null;
  vat_registered: boolean;
  tax_number: string;
  output: { sales: number; returns: number; other: number; total: number };
  input: { purchases: number; returns: number; expenses: number; other: number; total: number };
  /** Positive: owed to the Tax Authority; negative: a credit carried forward. */
  net_payable: number;
  by_month: { month: string; output: number; input: number; net: number }[];
  by_code: { sales: VatCodeRow[]; sale_returns: VatCodeRow[]; purchases: VatCodeRow[]; purchase_returns: VatCodeRow[];
             expenses: { taxable: number; tax: number; documents: number } };
}

export interface OpeningLine {
  section: "customers" | "suppliers" | "safes" | "wallets" | "drawers" | "inventory" | "equity";
  label: string;
  label_en: string;
  account: { id: string; code: string; name: string; name_en: string | null } | null;
  party_type: "customer" | "supplier" | null;
  party_id: string | null;
  warehouse_id: string | null;
  operational: number;
  ledger: number;
  debit: number;
  credit: number;
}

/** GET /accounting/opening/preview?date (nothing posted); POST /accounting/opening {date} returns the same plus `entry`. */
export interface OpeningPreview {
  date: string;
  lines: OpeningLine[];
  total_debit: number;
  total_credit: number;
  balanced: boolean;
  sections: Record<string, { count: number; debit: number; credit: number }>;
  skipped_no_cost: { product_id: string; name: string; code: string | null; qty: number }[];
  notes: string[];
  can_post: boolean;
  blockers: string[];
  opening_entry: { id: string; number: string; date: string } | null;
  settings: AccountingSettings;
}

export interface AccountingSettings {
  fiscal_year_start: number;
  start_date: string | null;
}

export interface EntryRef {
  id: string;
  number: string;
  date: string;
}

/** GET /accounting/settings: the settings plus the state the screens need. */
export interface AccountingState extends AccountingSettings {
  /** null: no opening entry in force, the opening wizard is offered. */
  opening_entry: EntryRef | null;
  first_entry_date: string | null;
  year_end_closings: (EntryRef & { memo: string | null })[];
}

/** GET /accounting/accounts: the chart as a tree. */
export interface AccountNode extends AccountRef {
  parent_id: string | null;
  is_group: boolean;
  role: string | null;
  active: boolean;
  /** The sub-account of a safe, wallet, branch drawer or the default bank (created automatically). */
  money_kind: "safe" | "wallet" | "drawer" | "default_bank" | null;
  children: AccountNode[];
}

export type PartyType = "customer" | "supplier" | "employee";

/** GET /accounting/entries?from&to&source_type&account_id&page&page_size */
export interface EntryRow {
  id: string;
  number: string;
  date: string;
  source_type: string;
  source_id: string;
  event: string;
  memo: string | null;
  warehouse_id: string | null;
  reverses_id: string | null;
  created_by: string | null;
  created_at: string;
  amount: number;
  reversed: boolean;
}

export interface Paged<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface EntryLine {
  id: string;
  account_id: string;
  account_code: string;
  account_name: string;
  debit: number;
  credit: number;
  party_type: PartyType | null;
  party_id: string | null;
  party_name: string | null;
  warehouse_id: string | null;
}

/** GET /accounting/entries/{id} */
export interface EntryDetail extends Omit<EntryRow, "amount" | "reversed"> {
  reversed_by: string | null;
  reversed_by_entry: EntryRef | null;
  reverses_entry: EntryRef | null;
  created_by_name: string | null;
  /** The document's number or description (invoice number, PO number, the draft's memo…). */
  source_ref: string | null;
  lines: EntryLine[];
}

export interface DraftLine {
  account_id: string;
  account_code: string | null;
  account_name: string | null;
  account_role: string | null;
  debit: number;
  credit: number;
  party_type: PartyType | null;
  party_id: string | null;
  party_name: string | null;
  warehouse_id: string | null;
}

/** GET /accounting/drafts/{id}: `problems` lists what stops it from being posted (empty: it can be). */
export interface Draft {
  id: string;
  date: string;
  memo: string | null;
  warehouse_id: string | null;
  status: "draft" | "posted";
  entry: EntryRef | null;
  lines: DraftLine[];
  total_debit: number;
  total_credit: number;
  difference: number;
  balanced: boolean;
  problems: string[];
  updated_at: string;
}

/** GET /accounting/drafts?status */
export interface DraftRow {
  id: string;
  date: string;
  memo: string | null;
  status: "draft" | "posted";
  entry_id: string | null;
  entry_number: string | null;
  created_by_name: string | null;
  updated_at: string;
  debit: number;
  credit: number;
  line_count: number;
  balanced: boolean;
}

/** The body of POST /accounting/drafts and PUT /accounting/drafts/{id}. */
export interface DraftPayload {
  date: string;
  memo: string | null;
  warehouse_id: string | null;
  lines: {
    account_id: string;
    debit: string;
    credit: string;
    party_type: PartyType | null;
    party_id: string | null;
    warehouse_id: string | null;
  }[];
}

export interface PostResult {
  draft_id: string;
  entry: EntryRef;
  already: boolean;
}

export interface ReverseResult {
  reversed: string;
  entry: EntryRef;
  already: boolean;
}

export interface PeriodMonth {
  month: string;
  status: "open" | "closed";
  closed_at: string | null;
  closed_by_name: string | null;
  reopened_at: string | null;
  reopened_by_name: string | null;
  reopen_reason: string | null;
  current: boolean;
  can_close: boolean;
  can_reopen: boolean;
}

export interface FiscalYear {
  year: number;
  from: string;
  to: string;
  over: boolean;
  open_months: string[];
  closing_entry: EntryRef | null;
}

/** GET /accounting/periods: newest month first. */
export interface PeriodsOverview {
  current_month: string;
  fiscal_year_start: number;
  months: PeriodMonth[];
  years: FiscalYear[];
}

export interface FinancialCategory {
  id: string;
  name: string;
  type: "income" | "expense" | string;
  account_id: string | null;
}

export interface Branch {
  id: string;
  name: string;
}
