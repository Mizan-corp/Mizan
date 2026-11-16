// Accounting: this module's API calls (paths under /accounting), used by its screens. The screens
// (chart of accounts, journal, reports, period close) come in ADR-014 step 5; for now this file
// holds the shapes of the report endpoints (ADR-014 D8, D10), all read from the ledger only.
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
