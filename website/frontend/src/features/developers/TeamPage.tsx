/** A team: its members and its signing keys, each certified by Mizan (ADR-007 D5). */
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, KeyRound, Plus, Trash2, UserPlus } from "lucide-react";
import { Badge, Button, ConfirmDialog, Empty, ErrorBox, Input, Modal, Select, Spinner, useToast } from "@/components/ui";
import { CopyValue, Field, PageHeader, Panel, when } from "./kit";
import { devPath } from "./paths";
import { portal, PortalError, useDeveloper } from "./session";

interface Member { id: string; email: string; full_name: string; role: "owner" | "member" }
interface Key { id: string; key_id: string; name: string; public_key: string; certificate: string; created_at: string | null; revoked_at: string | null }
interface TeamDetail { id: string; handle: string; name: string; role: "owner" | "member"; members: Member[]; keys: Key[] }

const message = (e: unknown, fallback: string) => (e instanceof PortalError ? e.message : fallback);

function AddKey({ handle, onDone }: { handle: string; onDone: () => void }) {
  const { toast } = useToast();
  const qc = useQueryClient();
  const [publicKey, setPublicKey] = useState("");
  const [name, setName] = useState("");
  const [issued, setIssued] = useState<Key | null>(null);
  const add = useMutation({
    mutationFn: () => portal<Key>("POST", `/teams/${handle}/keys`, { public_key: publicKey.trim(), name: name.trim() || "default" }),
    onSuccess: (k) => {
      setIssued(k);
      qc.invalidateQueries({ queryKey: ["developer-team", handle] });
    },
    onError: (e) => toast("error", message(e, "تعذر تسجيل المفتاح")),
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    add.mutate();
  };
  if (issued) {
    return (
      <div className="space-y-4 text-sm">
        <p className="text-muted-foreground">
          شهد ميزان لمفتاحك <span className="code inline-block" dir="ltr">{issued.key_id}</span>. احفظ الشهادة في الملف
          <span className="code inline-block" dir="ltr"> ~/.mizan/{issued.name}.cert </span> ليوقّع بها <span className="code inline-block" dir="ltr">mizan package</span>.
        </p>
        <CopyValue value={issued.certificate} label="الشهادة" />
        <Button onClick={onDone}>تم</Button>
      </div>
    );
  }
  return (
    <form onSubmit={submit} className="space-y-4">
      <p className="text-sm text-muted-foreground">
        أسهل طريقة: <span className="code inline-block" dir="ltr">mizan keys new --team {handle}</span> بعد <span className="code inline-block" dir="ltr">mizan login</span>،
        فتُسجَّل وتُحفظ شهادتها تلقائيًا. أو الصق هنا المفتاح العام الذي طبعه <span className="code inline-block" dir="ltr">mizan keys new</span>.
      </p>
      <Field label="المفتاح العام" htmlFor="key-public">
        <Input id="key-public" dir="ltr" className="code text-start" value={publicKey} onChange={(e) => setPublicKey(e.target.value)}
               placeholder="pUNlb8FG_1l3OII1VSFMVBDWv-fKl48zZCdXVxID0K8" autoFocus required />
      </Field>
      <Field label="اسم يميزه" htmlFor="key-name" hint="مثل اسم الجهاز: laptop، ci.">
        <Input id="key-name" dir="ltr" className="text-start" value={name} onChange={(e) => setName(e.target.value)} maxLength={64} placeholder="default" />
      </Field>
      <div className="flex gap-2">
        <Button type="submit" disabled={publicKey.trim().length < 40 || add.isPending}>{add.isPending ? <Spinner /> : "تسجيل وإصدار الشهادة"}</Button>
        <Button type="button" variant="outline" onClick={onDone}>إلغاء</Button>
      </div>
    </form>
  );
}

function AddMember({ handle, onDone }: { handle: string; onDone: () => void }) {
  const { toast } = useToast();
  const qc = useQueryClient();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"member" | "owner">("member");
  const add = useMutation({
    mutationFn: () => portal("POST", `/teams/${handle}/members`, { email: email.trim(), role }),
    onSuccess: () => {
      toast("success", "أُضيف إلى الفريق");
      qc.invalidateQueries({ queryKey: ["developer-team", handle] });
      onDone();
    },
    onError: (e) => toast("error", message(e, "تعذرت الإضافة")),
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    add.mutate();
  };
  return (
    <form onSubmit={submit} className="space-y-4">
      <Field label="بريد المطور" htmlFor="member-email" hint="يجب أن يكون له حساب في البوابة.">
        <Input id="member-email" type="email" dir="ltr" className="text-start" value={email} onChange={(e) => setEmail(e.target.value)} autoFocus required />
      </Field>
      <Field label="الدور" htmlFor="member-role" hint="المالك يضيف الأعضاء ويزيلهم ويلغي المفاتيح. العضو يسجل مفاتيح ويوقّع.">
        <Select id="member-role" value={role} onChange={(e) => setRole(e.target.value as "member" | "owner")}>
          <option value="member">عضو</option>
          <option value="owner">مالك</option>
        </Select>
      </Field>
      <div className="flex gap-2">
        <Button type="submit" disabled={!email.includes("@") || add.isPending}>{add.isPending ? <Spinner /> : "إضافة"}</Button>
        <Button type="button" variant="outline" onClick={onDone}>إلغاء</Button>
      </div>
    </form>
  );
}

export default function TeamPage() {
  const { handle = "" } = useParams();
  const { me } = useDeveloper();
  const { toast } = useToast();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [addingKey, setAddingKey] = useState(false);
  const [addingMember, setAddingMember] = useState(false);
  const [revoking, setRevoking] = useState<Key | null>(null);
  const [removing, setRemoving] = useState<Member | null>(null);
  const [showCert, setShowCert] = useState<Key | null>(null);

  const team = useQuery({ queryKey: ["developer-team", handle], queryFn: () => portal<TeamDetail>("GET", `/teams/${handle}`) });
  const refresh = () => qc.invalidateQueries({ queryKey: ["developer-team", handle] });
  const revoke = useMutation({
    mutationFn: (k: Key) => portal("POST", `/teams/${handle}/keys/${k.key_id}/revoke`),
    onSuccess: () => { toast("success", "أُلغي المفتاح"); setRevoking(null); refresh(); },
    onError: (e) => toast("error", message(e, "تعذر الإلغاء")),
  });
  const remove = useMutation({
    mutationFn: (m: Member) => portal("DELETE", `/teams/${handle}/members/${m.id}`),
    onSuccess: (_, m) => {
      toast("success", m.id === me?.id ? "غادرت الفريق" : "أُزيل من الفريق");
      setRemoving(null);
      qc.invalidateQueries({ queryKey: ["developer-me"] });
      if (m.id === me?.id) navigate(devPath("/portal"));
      else refresh();
    },
    onError: (e) => toast("error", message(e, "تعذرت الإزالة")),
  });

  const back = (
    <Link to={devPath("/portal")} className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
      <ChevronRight className="size-4" /> الفرق
    </Link>
  );
  if (team.isPending) return <div className="flex justify-center p-12"><Spinner /></div>;
  if (team.isError) return <>{back}<ErrorBox message={message(team.error, "تعذر تحميل الفريق")} onRetry={() => team.refetch()} /></>;

  const t = team.data;
  const owner = t.role === "owner";
  const active = t.keys.filter((k) => !k.revoked_at);
  const revoked = t.keys.filter((k) => k.revoked_at);

  return (
    <>
      {back}
      <PageHeader
        title={t.name}
        description={<>وحدات هذا الفريق تبدأ بـ <span className="code inline-block" dir="ltr">{t.handle}.</span> · دورك: {owner ? "مالك" : "عضو"}</>}
      />
      <div className="grid gap-6">
        <Panel
          title="مفاتيح التوقيع"
          aside={<Button size="sm" onClick={() => setAddingKey(true)}><Plus className="size-4" /> مفتاح</Button>}
          flush
        >
          {active.length === 0 ? (
            <div className="p-5">
              <Empty icon={<KeyRound className="size-10" strokeWidth={1.25} />} text="لا مفاتيح فعالة"
                     hint="سجّل مفتاحًا ليشهد له ميزان فتوقّع به حزم وحداتك." />
            </div>
          ) : (
            <ul className="divide-y divide-line">
              {active.map((k) => (
                <li key={k.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5">
                  <span className="min-w-0">
                    <span className="flex items-center gap-2 font-semibold text-foreground">
                      {k.name} <span className="code text-xs font-normal text-muted-foreground" dir="ltr">{k.key_id}</span>
                    </span>
                    <span className="code block truncate text-xs text-muted-foreground" dir="ltr">{k.public_key}</span>
                    <span className="text-xs text-muted-foreground">سُجّل {when(k.created_at)}</span>
                  </span>
                  <span className="flex gap-1">
                    <Button size="sm" variant="ghost" onClick={() => setShowCert(k)}>الشهادة</Button>
                    {owner && (
                      <Button size="sm" variant="ghost" onClick={() => setRevoking(k)} aria-label={`إلغاء المفتاح ${k.name}`}>
                        <Trash2 className="size-4" /> إلغاء
                      </Button>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          )}
          {revoked.length > 0 && (
            <details className="border-t border-line px-5 py-3 text-xs text-muted-foreground">
              <summary className="cursor-pointer select-none">مفاتيح ملغاة ({revoked.length})</summary>
              <ul className="mt-2 space-y-1">
                {revoked.map((k) => (
                  <li key={k.id}>{k.name} <span className="code inline-block" dir="ltr">{k.key_id}</span> · أُلغي {when(k.revoked_at)}</li>
                ))}
              </ul>
            </details>
          )}
        </Panel>

        <Panel
          title="الأعضاء"
          aside={owner && <Button size="sm" variant="outline" onClick={() => setAddingMember(true)}><UserPlus className="size-4" /> عضو</Button>}
          flush
        >
          <ul className="divide-y divide-line">
            {t.members.map((m) => (
              <li key={m.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3">
                <span className="min-w-0">
                  <span className="flex items-center gap-2 text-sm font-semibold text-foreground">
                    {m.full_name} {m.id === me?.id && <span className="text-xs font-normal text-muted-foreground">(أنت)</span>}
                    <Badge tone={m.role === "owner" ? "brand" : "muted"}>{m.role === "owner" ? "مالك" : "عضو"}</Badge>
                  </span>
                  <span className="code block text-xs text-muted-foreground" dir="ltr">{m.email}</span>
                </span>
                {(owner || m.id === me?.id) && (
                  <Button size="sm" variant="ghost" onClick={() => setRemoving(m)}>{m.id === me?.id ? "مغادرة" : "إزالة"}</Button>
                )}
              </li>
            ))}
          </ul>
        </Panel>
      </div>

      <Modal open={addingKey} onClose={() => setAddingKey(false)} title="تسجيل مفتاح توقيع">
        {addingKey && <AddKey handle={t.handle} onDone={() => setAddingKey(false)} />}
      </Modal>
      <Modal open={addingMember} onClose={() => setAddingMember(false)} title="إضافة عضو">
        {addingMember && <AddMember handle={t.handle} onDone={() => setAddingMember(false)} />}
      </Modal>
      <Modal open={!!showCert} onClose={() => setShowCert(null)} title={showCert ? `شهادة ${showCert.name}` : ""}>
        {showCert && (
          <div className="space-y-3 text-sm">
            <p className="text-muted-foreground">احفظها في <span className="code inline-block" dir="ltr">~/.mizan/{showCert.name}.cert</span> بجانب المفتاح الخاص.</p>
            <CopyValue value={showCert.certificate} label="الشهادة" />
          </div>
        )}
      </Modal>
      <ConfirmDialog
        open={!!revoking}
        onClose={() => setRevoking(null)}
        onConfirm={() => revoking && revoke.mutate(revoking)}
        title="إلغاء المفتاح"
        message="لن يقبل ميزان أي حزمة جديدة موقّعة بهذا المفتاح. الوحدات المثبتة سابقًا تبقى. لا يمكن التراجع."
        confirmLabel="إلغاء المفتاح"
      />
      <ConfirmDialog
        open={!!removing}
        onClose={() => setRemoving(null)}
        onConfirm={() => removing && remove.mutate(removing)}
        title={removing?.id === me?.id ? "مغادرة الفريق" : "إزالة العضو"}
        message={removing?.id === me?.id ? "لن ترى هذا الفريق ولن توقّع باسمه." : `لن يتمكن ${removing?.full_name ?? ""} من تسجيل مفاتيح لهذا الفريق.`}
        confirmLabel={removing?.id === me?.id ? "مغادرة" : "إزالة"}
      />
    </>
  );
}
