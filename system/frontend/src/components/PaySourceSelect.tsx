import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { moneyEGP } from "@/lib/format";
import { Select } from "@/components/ui";

/** Where a payment's money comes from or goes to (ADR-014 D4): a safe — a bank account is a safe of
 * type bank — or a payment wallet. The value is "safe:<id>", "wallet:<id>" or "" (none chosen). */
interface SafeRow { id: string; name: string; safe_type: string; balance: string }
interface WalletRow { id: string; name: string; balance: string }

export function sourceFields(value: string): { safe_id: string | null; wallet_id: string | null } {
  const [kind, id] = value.split(":");
  return { safe_id: kind === "safe" ? id : null, wallet_id: kind === "wallet" ? id : null };
}

export function PaySourceSelect({
  id,
  value,
  onChange,
  emptyLabel = "— اختر الخزنة أو المحفظة —",
}: {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  emptyLabel?: string;
}) {
  const safes = useQuery({ queryKey: ["safes"], queryFn: () => api.get<SafeRow[]>("/safes") });
  const wallets = useQuery({ queryKey: ["wallets"], queryFn: () => api.get<WalletRow[]>("/wallets") });
  const cash = (safes.data ?? []).filter((s) => s.safe_type !== "bank");
  const banks = (safes.data ?? []).filter((s) => s.safe_type === "bank");

  return (
    <Select id={id} value={value} onChange={(e) => onChange(e.target.value)} disabled={safes.isLoading || wallets.isLoading}>
      <option value="">{emptyLabel}</option>
      {!!cash.length && (
        <optgroup label="الخزائن">
          {cash.map((s) => (
            <option key={s.id} value={`safe:${s.id}`}>{s.name} — {moneyEGP(s.balance)}</option>
          ))}
        </optgroup>
      )}
      {!!banks.length && (
        <optgroup label="الحسابات البنكية">
          {banks.map((s) => (
            <option key={s.id} value={`safe:${s.id}`}>{s.name} — {moneyEGP(s.balance)}</option>
          ))}
        </optgroup>
      )}
      {!!wallets.data?.length && (
        <optgroup label="المحافظ">
          {wallets.data.map((w) => (
            <option key={w.id} value={`wallet:${w.id}`}>{w.name} — {moneyEGP(w.balance)}</option>
          ))}
        </optgroup>
      )}
    </Select>
  );
}
