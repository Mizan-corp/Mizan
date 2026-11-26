// Accounting & Finance: the shapes this module's screens read. The routes keep their historical
// paths (/safes, /wallets, /expenses, /periods…), not /modules/finance.

/** GET /safes. The balance comes only with the finance or reports permission. */
export interface Safe {
  id: string;
  name: string;
  safe_type: "permanent" | "temporary" | "bank";
  location?: string | null;
  balance?: string;
  is_active: boolean;
}

/** GET /wallets. The balance comes only with the finance or reports permission. */
export interface WalletRow {
  id: string;
  name: string;
  type: string;
  phone?: string | null;
  balance?: string;
  is_active: boolean;
}

/** One month of GET /periods (newest first). */
export interface PeriodMonth {
  month: string;
  status: "open" | "closed";
  current: boolean;
  can_close: boolean;
  can_reopen: boolean;
  closed_at: string | null;
  closed_by_name: string | null;
  reopened_at: string | null;
  reopened_by_name: string | null;
  reopen_reason: string | null;
}

export const SAFE_TYPE_LABEL: Record<Safe["safe_type"], string> = {
  permanent: "خزينة دائمة",
  temporary: "خزينة وردية",
  bank: "حساب بنكي",
};

/** A fresh id for one attempt of a money movement: sent as client_id, a retry of the same attempt
 *  (a double click, a lost answer) returns the first result instead of moving the money twice. */
export function newClientId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return "10000000-1000-4000-8000-100000000000".replace(/[018]/g, (c) =>
    (Number(c) ^ (Math.random() * 16) >> (Number(c) / 4)).toString(16),
  );
}
