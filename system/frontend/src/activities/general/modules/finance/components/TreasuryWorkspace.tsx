// Safes, bank accounts and payment wallets: create, edit, stop and bring back; deposit, withdraw
// (a manager with finance) and wallet → safe transfers. Every movement carries a client id, so a
// retried request never moves the money twice.
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeftRight, Banknote, History, Pencil, Plus, Power, Wallet } from "lucide-react";
import { Skeleton } from "@/components/kit/skeleton";
import { api } from "@/lib/api";
import { D, dateTime, moneyEGP } from "@/lib/format";
import { sound } from "@/lib/sound";
import { useAuth } from "@/stores/auth";
import { Badge, Button, ConfirmDialog, Empty, ErrorBox, Input, Modal, Select, Spinner, useToast } from "@/components/ui";
import { newClientId, SAFE_TYPE_LABEL, type Safe, type WalletRow } from "../api";

type Move = { kind: "deposit" | "withdraw"; safe: Safe } | { kind: "transfer"; wallet: WalletRow };
type SafeForm = { id?: string; name: string; location: string; safe_type: Safe["safe_type"] };
type WalletForm = { id?: string; name: string; type: string; phone: string };
type Stop = { what: "safe"; row: Safe } | { what: "wallet"; row: WalletRow };

const WALLET_TYPES: Record<string, string> = {
  vodafone_cash: "فودافون كاش",
  orange_cash: "أورنج كاش",
  etisalat_cash: "اتصالات كاش",
  instapay: "إنستاباي",
  mobile: "محفظة إلكترونية",
  bank: "حساب بنكي",
  cash: "نقدي",
};

export function TreasuryWorkspace() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const can = useAuth((s) => s.can);
  const isManager = useAuth((s) => !!s.user?.is_manager);
  const manage = can("finance");
  const [showStopped, setShowStopped] = useState(false);
  const safes = useQuery({
    queryKey: ["safes", { all: showStopped }],
    queryFn: () => api.get<Safe[]>("/safes", { include_inactive: showStopped ? "true" : undefined }),
  });
  const wallets = useQuery({
    queryKey: ["wallets", { all: showStopped }],
    queryFn: () => api.get<WalletRow[]>("/wallets", { include_inactive: showStopped ? "true" : undefined }),
  });

  const [move, setMove] = useState<Move | null>(null);
  const [clientId, setClientId] = useState("");
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [toSafe, setToSafe] = useState("");
  const [safeForm, setSafeForm] = useState<SafeForm | null>(null);
  const [walletForm, setWalletForm] = useState<WalletForm | null>(null);
  const [stop, setStop] = useState<Stop | null>(null);
  const [history, setHistory] = useState<{ what: "safe" | "wallet"; id: string; name: string } | null>(null);

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["safes"] });
    qc.invalidateQueries({ queryKey: ["wallets"] });
  };
  const openMove = (m: Move) => {
    setMove(m);
    setClientId(newClientId());
    setAmount("");
    setNote("");
    setToSafe("");
  };

  const act = useMutation({
    mutationFn: () => {
      sound.click();
      const a = D(amount).toFixed(2);
      const m = move!;
      if (m.kind === "transfer")
        return api.post("/safes/transfer", { from_wallet_id: m.wallet.id, to_safe_id: toSafe, amount: a, note: note || null, client_id: clientId });
      if (m.kind === "deposit") return api.post(`/safes/${m.safe.id}/deposit`, { amount: a, notes: note || null, client_id: clientId });
      return api.post(`/safes/${m.safe.id}/withdraw`, { amount: a, note: note || null, client_id: clientId });
    },
    onSuccess: () => {
      sound.success();
      toast("success", "تم تسجيل الحركة");
      setMove(null);
      refresh();
    },
    onError: () => sound.error(),
  });

  const saveSafe = useMutation({
    mutationFn: (f: SafeForm) => {
      const body = { name: f.name.trim(), location: f.location.trim() || null, safe_type: f.safe_type };
      return f.id ? api.put(`/safes/${f.id}`, body) : api.post("/safes", body);
    },
    onSuccess: (_r, f) => {
      sound.success();
      toast("success", f.id ? "حُفظت الخزنة" : "أُضيفت الخزنة");
      setSafeForm(null);
      refresh();
    },
    onError: () => sound.error(),
  });

  const saveWallet = useMutation({
    mutationFn: (f: WalletForm) => {
      const body = { name: f.name.trim(), type: f.type, phone: f.phone.trim() || null };
      return f.id ? api.put(`/wallets/${f.id}`, body) : api.post("/wallets", body);
    },
    onSuccess: (_r, f) => {
      sound.success();
      toast("success", f.id ? "حُفظت المحفظة" : "أُضيفت المحفظة");
      setWalletForm(null);
      refresh();
    },
    onError: () => sound.error(),
  });

  const setActive = useMutation({
    mutationFn: ({ what, id, active }: { what: "safe" | "wallet"; id: string; active: boolean }) => {
      const base = what === "safe" ? "/safes" : "/wallets";
      return active ? api.post(`${base}/${id}/activate`) : api.del(`${base}/${id}`);
    },
    onSuccess: (_r, v) => {
      sound.success();
      toast("success", v.active ? "أُعيد التفعيل" : "تم الإيقاف");
      setStop(null);
      refresh();
    },
    onError: (e) => {
      sound.error();
      setStop(null);
      toast("error", (e as Error).message);
    },
  });

  const activeSafes = (safes.data ?? []).filter((s) => s.is_active);
  const loading = safes.isLoading || wallets.isLoading;
  const failed = safes.isError ? safes : wallets.isError ? wallets : null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <label className="flex items-center gap-2 text-xs font-medium text-muted">
          <input type="checkbox" checked={showStopped} onChange={(e) => setShowStopped(e.target.checked)} />
          إظهار الخزائن والمحافظ الموقوفة
        </label>
        {manage && (
          <div className="flex gap-2">
            <Button size="sm" className="gap-1.5 text-xs font-bold"
                    onClick={() => setSafeForm({ name: "", location: "", safe_type: "permanent" })}>
              <Plus className="size-4" /> خزنة أو حساب بنكي
            </Button>
            <Button size="sm" variant="outline" className="gap-1.5 text-xs font-bold"
                    onClick={() => setWalletForm({ name: "", type: "vodafone_cash", phone: "" })}>
              <Plus className="size-4" /> محفظة
            </Button>
          </div>
        )}
      </div>

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-44 w-full rounded-2xl" />)}
        </div>
      ) : failed ? (
        <ErrorBox message={(failed.error as Error).message} onRetry={() => { safes.refetch(); wallets.refetch(); }} />
      ) : (
        <>
          <section>
            <h2 className="text-base font-bold text-ink">الخزائن والحسابات البنكية</h2>
            <p className="mb-4 text-xs text-muted">منها تُصرف المصروفات ودفعات الموردين والرواتب، وإليها تدخل التحصيلات.</p>
            {!safes.data?.length ? (
              <Empty text="لا توجد خزائن بعد" hint="أضف خزنة لتتمكن من اعتماد المصروفات وتحصيل دفعات العملاء خارج الوردية."
                     icon={<Banknote className="size-10" />} />
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {safes.data.map((s) => (
                  <div key={s.id} className={`rounded-2xl border border-line bg-card p-5 space-y-4 shadow-xs ${s.is_active ? "" : "opacity-60"}`}>
                    <div className="flex items-center justify-between gap-2">
                      <span className="flex items-center gap-2 font-bold text-ink">
                        <Banknote className="size-5 text-amber-500" /> {s.name}
                      </span>
                      <div className="flex items-center gap-1">
                        {!s.is_active && <Badge tone="danger">موقوفة</Badge>}
                        <Badge tone="muted">{SAFE_TYPE_LABEL[s.safe_type] ?? s.safe_type}</Badge>
                      </div>
                    </div>
                    {s.location && <p className="text-xs text-muted">{s.location}</p>}
                    <div>
                      <span className="text-xs text-muted block mb-1">الرصيد الحالي</span>
                      <p className="num text-2xl font-black text-primary">{s.balance != null ? moneyEGP(s.balance) : "—"}</p>
                    </div>
                    {manage && (
                      <div className="flex flex-wrap gap-2 pt-2 border-t border-line/60">
                        {s.is_active && (
                          <>
                            <Button variant="outline" size="sm" className="flex-1 font-bold text-xs" onClick={() => openMove({ kind: "deposit", safe: s })}>
                              إيداع
                            </Button>
                            {isManager && (
                              <Button variant="outline" size="sm" className="flex-1 font-bold text-xs" onClick={() => openMove({ kind: "withdraw", safe: s })}>
                                سحب
                              </Button>
                            )}
                          </>
                        )}
                        <Button variant="ghost" size="icon" aria-label={`سجل ${s.name}`} className="size-8 px-0!"
                                onClick={() => setHistory({ what: "safe", id: s.id, name: s.name })}>
                          <History className="size-4" />
                        </Button>
                        <Button variant="ghost" size="icon" aria-label={`تعديل ${s.name}`} className="size-8 px-0!"
                                onClick={() => setSafeForm({ id: s.id, name: s.name, location: s.location ?? "", safe_type: s.safe_type })}>
                          <Pencil className="size-4" />
                        </Button>
                        <Button variant="ghost" size="icon" aria-label={s.is_active ? `إيقاف ${s.name}` : `تفعيل ${s.name}`} className="size-8 px-0!"
                                disabled={setActive.isPending}
                                onClick={() => (s.is_active ? setStop({ what: "safe", row: s }) : setActive.mutate({ what: "safe", id: s.id, active: true }))}>
                          <Power className="size-4" />
                        </Button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>

          <section>
            <h2 className="text-base font-bold text-ink">محافظ الدفع الإلكتروني</h2>
            <p className="mb-4 text-xs text-muted">فودافون كاش وإنستاباي وغيرها: تدخلها مبيعات المحفظة ويُحوَّل رصيدها إلى خزنة.</p>
            {!wallets.data?.length ? (
              <Empty text="لا توجد محافظ" hint="أضف محفظة لتقبل الدفع الإلكتروني في نقطة البيع." icon={<Wallet className="size-10" />} />
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {wallets.data.map((w) => (
                  <div key={w.id} className={`rounded-2xl border border-line bg-card p-5 space-y-4 shadow-xs ${w.is_active ? "" : "opacity-60"}`}>
                    <div className="flex items-center justify-between gap-2">
                      <span className="flex items-center gap-2 font-bold text-ink">
                        <Wallet className="size-5 text-indigo-500" /> {w.name}
                      </span>
                      <div className="flex items-center gap-1">
                        {!w.is_active && <Badge tone="danger">موقوفة</Badge>}
                        <Badge tone="brand">{WALLET_TYPES[w.type] ?? w.type}</Badge>
                      </div>
                    </div>
                    {w.phone && <p className="num text-xs text-muted" dir="ltr">{w.phone}</p>}
                    <div>
                      <span className="text-xs text-muted block mb-1">الرصيد المتاح</span>
                      <p className="num text-xl font-black text-ink">{w.balance != null ? moneyEGP(w.balance) : "—"}</p>
                    </div>
                    {manage && (
                      <div className="flex flex-wrap gap-2 pt-2 border-t border-line/60">
                        {w.is_active && (
                          <Button variant="outline" size="sm" className="flex-1 font-bold text-xs gap-1.5"
                                  disabled={!activeSafes.length} onClick={() => openMove({ kind: "transfer", wallet: w })}>
                            <ArrowLeftRight className="size-3.5" /> تحويل إلى خزنة
                          </Button>
                        )}
                        <Button variant="ghost" size="icon" aria-label={`سجل ${w.name}`} className="size-8 px-0!"
                                onClick={() => setHistory({ what: "wallet", id: w.id, name: w.name })}>
                          <History className="size-4" />
                        </Button>
                        <Button variant="ghost" size="icon" aria-label={`تعديل ${w.name}`} className="size-8 px-0!"
                                onClick={() => setWalletForm({ id: w.id, name: w.name, type: w.type, phone: w.phone ?? "" })}>
                          <Pencil className="size-4" />
                        </Button>
                        <Button variant="ghost" size="icon" aria-label={w.is_active ? `إيقاف ${w.name}` : `تفعيل ${w.name}`} className="size-8 px-0!"
                                disabled={setActive.isPending}
                                onClick={() => (w.is_active ? setStop({ what: "wallet", row: w }) : setActive.mutate({ what: "wallet", id: w.id, active: true }))}>
                          <Power className="size-4" />
                        </Button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>
        </>
      )}

      {/* Deposit / withdraw / transfer */}
      <Modal open={!!move} onClose={() => setMove(null)}
             title={!move ? "" : move.kind === "transfer" ? `تحويل من ${move.wallet.name} إلى خزنة`
               : move.kind === "deposit" ? `إيداع في ${move.safe.name}` : `سحب من ${move.safe.name}`}>
        <form className="flex flex-col gap-4"
              onSubmit={(e) => {
                e.preventDefault();
                if (!act.isPending && amount && (move?.kind !== "transfer" || toSafe)) act.mutate();
              }}>
          {move?.kind === "transfer" && (
            <div>
              <label htmlFor="move-safe" className="mb-1 block text-xs font-semibold text-muted">الخزنة المستلمة *</label>
              <Select id="move-safe" value={toSafe} onChange={(e) => setToSafe(e.target.value)}>
                <option value="">— اختر الخزنة —</option>
                {activeSafes.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </Select>
            </div>
          )}
          <div>
            <label htmlFor="move-amount" className="mb-1 block text-xs font-semibold text-muted">المبلغ (ج.م) *</label>
            <Input id="move-amount" autoFocus className="num text-lg font-bold" inputMode="decimal" value={amount}
                   onChange={(e) => setAmount(e.target.value)} />
          </div>
          <div>
            <label htmlFor="move-note" className="mb-1 block text-xs font-semibold text-muted">البيان</label>
            <Input id="move-note" maxLength={500} value={note} onChange={(e) => setNote(e.target.value)}
                   placeholder={move?.kind === "withdraw" ? "سبب السحب ومن استلم المبلغ" : "مصدر المبلغ"} />
          </div>
          {move?.kind !== "transfer" && (
            <p className="text-[11px] text-muted">
              {move?.kind === "deposit" ? "يُسجَّل إيداعاً يدوياً (إيراد آخر). نقدية الوردية تُورَّد من شاشة الوردية." : "يُسجَّل سحباً يدوياً (مصروف آخر)."}
            </p>
          )}
          {act.isError && <ErrorBox message={(act.error as Error).message} />}
          <Button type="submit" className="w-full h-11 font-bold text-xs rounded-xl"
                  disabled={act.isPending || !amount || (move?.kind === "transfer" && !toSafe)}>
            {act.isPending ? <Spinner /> : "تأكيد العملية"}
          </Button>
        </form>
      </Modal>

      {/* Create / edit a safe */}
      <Modal open={!!safeForm} onClose={() => setSafeForm(null)} title={safeForm?.id ? "تعديل الخزنة" : "خزنة أو حساب بنكي جديد"}>
        {safeForm && (
          <form className="flex flex-col gap-4"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (!saveSafe.isPending && safeForm.name.trim()) saveSafe.mutate(safeForm);
                }}>
            <div>
              <label htmlFor="safe-name" className="mb-1 block text-xs font-semibold text-muted">الاسم *</label>
              <Input id="safe-name" autoFocus maxLength={128} value={safeForm.name}
                     onChange={(e) => setSafeForm({ ...safeForm, name: e.target.value })} />
            </div>
            <div>
              <label htmlFor="safe-type" className="mb-1 block text-xs font-semibold text-muted">النوع</label>
              <Select id="safe-type" value={safeForm.safe_type}
                      onChange={(e) => setSafeForm({ ...safeForm, safe_type: e.target.value as Safe["safe_type"] })}>
                {Object.entries(SAFE_TYPE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </Select>
            </div>
            <div>
              <label htmlFor="safe-location" className="mb-1 block text-xs font-semibold text-muted">المكان أو رقم الحساب</label>
              <Input id="safe-location" maxLength={256} value={safeForm.location}
                     onChange={(e) => setSafeForm({ ...safeForm, location: e.target.value })} />
            </div>
            {saveSafe.isError && <ErrorBox message={(saveSafe.error as Error).message} />}
            <Button type="submit" className="w-full h-10 font-bold" disabled={saveSafe.isPending || !safeForm.name.trim()}>
              {saveSafe.isPending ? <Spinner /> : "حفظ"}
            </Button>
          </form>
        )}
      </Modal>

      {/* Create / edit a wallet */}
      <Modal open={!!walletForm} onClose={() => setWalletForm(null)} title={walletForm?.id ? "تعديل المحفظة" : "محفظة جديدة"}>
        {walletForm && (
          <form className="flex flex-col gap-4"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (!saveWallet.isPending && walletForm.name.trim()) saveWallet.mutate(walletForm);
                }}>
            <div>
              <label htmlFor="wallet-name" className="mb-1 block text-xs font-semibold text-muted">الاسم *</label>
              <Input id="wallet-name" autoFocus maxLength={128} value={walletForm.name}
                     onChange={(e) => setWalletForm({ ...walletForm, name: e.target.value })} />
            </div>
            <div>
              <label htmlFor="wallet-type" className="mb-1 block text-xs font-semibold text-muted">النوع</label>
              <Select id="wallet-type" value={walletForm.type} onChange={(e) => setWalletForm({ ...walletForm, type: e.target.value })}>
                {Object.entries(WALLET_TYPES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                {!(walletForm.type in WALLET_TYPES) && <option value={walletForm.type}>{walletForm.type}</option>}
              </Select>
            </div>
            <div>
              <label htmlFor="wallet-phone" className="mb-1 block text-xs font-semibold text-muted">رقم المحفظة</label>
              <Input id="wallet-phone" className="num" dir="ltr" maxLength={32} value={walletForm.phone}
                     onChange={(e) => setWalletForm({ ...walletForm, phone: e.target.value })} />
            </div>
            {saveWallet.isError && <ErrorBox message={(saveWallet.error as Error).message} />}
            <Button type="submit" className="w-full h-10 font-bold" disabled={saveWallet.isPending || !walletForm.name.trim()}>
              {saveWallet.isPending ? <Spinner /> : "حفظ"}
            </Button>
          </form>
        )}
      </Modal>

      <ConfirmDialog
        open={!!stop}
        onClose={() => setStop(null)}
        onConfirm={() => stop && setActive.mutate({ what: stop.what, id: stop.row.id, active: false })}
        title={stop ? `إيقاف ${stop.row.name}` : ""}
        message="لا يُستخدم بعد الإيقاف في الدفع أو التحصيل، ويبقى سجله كما هو. لا يُوقف إلا إذا كان رصيده صفراً."
        confirmLabel="إيقاف"
      />

      <HistoryModal target={history} onClose={() => setHistory(null)} />
    </div>
  );
}

interface Movement {
  id: string;
  tx_type: string;
  amount: string;
  note: string | null;
  created_at: string;
  user_name?: string | null;
}

const TX_LABEL: Record<string, string> = {
  deposit: "إيداع", withdraw: "سحب", sale: "بيع", return: "مرتجع", expense: "مصروف", expense_reversed: "إلغاء مصروف",
  safe_transfer: "تحويل إلى خزنة", adjustment: "تسوية", customer_payment: "تحصيل", customer_payment_reversal: "عكس تحصيل",
};

function HistoryModal({ target, onClose }: { target: { what: "safe" | "wallet"; id: string; name: string } | null; onClose: () => void }) {
  const rows = useQuery({
    queryKey: ["treasury-history", target?.what, target?.id],
    queryFn: () => api.get<Movement[]>(`/${target!.what === "safe" ? "safes" : "wallets"}/${target!.id}/history`),
    enabled: !!target,
  });
  return (
    <Modal open={!!target} onClose={onClose} title={`آخر الحركات — ${target?.name ?? ""}`} wide>
      {rows.isLoading ? (
        <div className="grid place-items-center p-8"><Spinner /></div>
      ) : rows.isError ? (
        <ErrorBox message={(rows.error as Error).message} onRetry={() => rows.refetch()} />
      ) : !rows.data?.length ? (
        <Empty text="لا توجد حركات بعد" />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-line">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line bg-elevated/50 text-xs font-bold text-muted">
                <th className="p-3 text-start">التاريخ</th>
                <th className="p-3 text-start">الحركة</th>
                <th className="p-3 text-start">البيان</th>
                <th className="p-3 text-end">المبلغ</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line/60">
              {rows.data.map((m) => {
                const out = m.tx_type === "withdraw" || Number(m.amount) < 0;
                return (
                  <tr key={m.id}>
                    <td className="num p-3 text-xs text-muted">{dateTime(m.created_at)}</td>
                    <td className="p-3 text-xs">{TX_LABEL[m.tx_type] ?? m.tx_type}</td>
                    <td className="p-3 text-xs text-muted">{m.note || "—"}{m.user_name ? ` · ${m.user_name}` : ""}</td>
                    <td className={`num p-3 text-end font-bold ${out ? "text-rose-600" : "text-emerald-600 dark:text-emerald-400"}`}>
                      {moneyEGP(Math.abs(Number(m.amount)))}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Modal>
  );
}
