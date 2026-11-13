/** A team: its marketplace packages (#105), its signing keys, each certified by Mizan (ADR-007 D5), and its members. */
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, KeyRound, Plus, Trash2, UserPlus } from "lucide-react";
import { Badge, Button, Empty, ErrorBox, Input, Modal, Select, Spinner, useToast } from "@/components/ui";
import { useDevI18n } from "./i18n";
import { Confirm, CopyValue, Field, PageHeader, Panel, useWhen } from "./kit";
import { Packages } from "./Packages";
import { devPath } from "./paths";
import { portal, PortalError, useDeveloper } from "./session";

interface Member { id: string; email: string; full_name: string; role: "owner" | "member" }
interface Key { id: string; key_id: string; name: string; public_key: string; certificate: string; created_at: string | null; revoked_at: string | null }
interface TeamDetail { id: string; handle: string; name: string; role: "owner" | "member"; members: Member[]; keys: Key[] }

const Code = ({ children }: { children: React.ReactNode }) => <span className="code inline-block" dir="ltr">{children}</span>;

function AddKey({ handle, onDone }: { handle: string; onDone: () => void }) {
  const { toast } = useToast();
  const { t } = useDevI18n();
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
    onError: (e) => toast("error", e instanceof PortalError ? e.message : t("Couldn't register the key", "تعذر تسجيل المفتاح")),
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    add.mutate();
  };
  if (issued) {
    return (
      <div className="space-y-4 text-sm">
        <p className="text-muted-foreground">
          {t("Mizan certified your key ", "شهد ميزان لمفتاحك ")}<Code>{issued.key_id}</Code>.{" "}
          {t("Save the certificate as ", "احفظ الشهادة في الملف ")}<Code>~/.mizan/{issued.name}.cert</Code>{" "}
          {t("so ", "ليوقّع بها ")}<Code>mizan package</Code>{t(" signs with it.", ".")}
        </p>
        <CopyValue value={issued.certificate} label={t("the certificate", "الشهادة")} />
        <Button onClick={onDone}>{t("Done", "تم")}</Button>
      </div>
    );
  }
  return (
    <form onSubmit={submit} className="space-y-4">
      <p className="text-sm text-muted-foreground">
        {t("Easiest: run ", "أسهل طريقة: ")}<Code>mizan keys new --team {handle}</Code>{t(" after ", " بعد ")}<Code>mizan login</Code>
        {t(", which registers the key and saves its certificate. Or paste the public key ", "، فتُسجَّل وتُحفظ شهادتها تلقائيًا. أو الصق هنا المفتاح العام الذي طبعه ")}
        <Code>mizan keys new</Code>{t(" printed.", ".")}
      </p>
      <Field label={t("Public key", "المفتاح العام")} htmlFor="key-public">
        <Input id="key-public" dir="ltr" className="code text-start" value={publicKey} onChange={(e) => setPublicKey(e.target.value)}
               placeholder="pUNlb8FG_1l3OII1VSFMVBDWv-fKl48zZCdXVxID0K8" autoFocus required />
      </Field>
      <Field label={t("Name", "اسم يميزه")} htmlFor="key-name" hint={t("Such as the machine: laptop, ci.", "مثل اسم الجهاز: laptop، ci.")}>
        <Input id="key-name" dir="ltr" className="text-start" value={name} onChange={(e) => setName(e.target.value)} maxLength={64} placeholder="default" />
      </Field>
      <div className="flex gap-2">
        <Button type="submit" disabled={publicKey.trim().length < 40 || add.isPending}>
          {add.isPending ? <Spinner /> : t("Register and certify", "تسجيل وإصدار الشهادة")}
        </Button>
        <Button type="button" variant="outline" onClick={onDone}>{t("Cancel", "إلغاء")}</Button>
      </div>
    </form>
  );
}

function AddMember({ handle, onDone }: { handle: string; onDone: () => void }) {
  const { toast } = useToast();
  const { t } = useDevI18n();
  const qc = useQueryClient();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"member" | "owner">("member");
  const add = useMutation({
    mutationFn: () => portal("POST", `/teams/${handle}/members`, { email: email.trim(), role }),
    onSuccess: () => {
      toast("success", t("Added to the team", "أُضيف إلى الفريق"));
      qc.invalidateQueries({ queryKey: ["developer-team", handle] });
      onDone();
    },
    onError: (e) => toast("error", e instanceof PortalError ? e.message : t("Couldn't add them", "تعذرت الإضافة")),
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    add.mutate();
  };
  return (
    <form onSubmit={submit} className="space-y-4">
      <Field label={t("Developer's email", "بريد المطور")} htmlFor="member-email" hint={t("They need a portal account.", "يجب أن يكون له حساب في البوابة.")}>
        <Input id="member-email" type="email" dir="ltr" className="text-start" value={email} onChange={(e) => setEmail(e.target.value)} autoFocus required />
      </Field>
      <Field label={t("Role", "الدور")} htmlFor="member-role"
             hint={t("Owners add and remove members and revoke keys. Members register keys and sign.",
                     "المالك يضيف الأعضاء ويزيلهم ويلغي المفاتيح. العضو يسجل مفاتيح ويوقّع.")}>
        <Select id="member-role" value={role} onChange={(e) => setRole(e.target.value as "member" | "owner")}>
          <option value="member">{t("Member", "عضو")}</option>
          <option value="owner">{t("Owner", "مالك")}</option>
        </Select>
      </Field>
      <div className="flex gap-2">
        <Button type="submit" disabled={!email.includes("@") || add.isPending}>{add.isPending ? <Spinner /> : t("Add", "إضافة")}</Button>
        <Button type="button" variant="outline" onClick={onDone}>{t("Cancel", "إلغاء")}</Button>
      </div>
    </form>
  );
}

export default function TeamPage() {
  const { handle = "" } = useParams();
  const { me } = useDeveloper();
  const { t } = useDevI18n();
  const when = useWhen();
  const { toast } = useToast();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [addingKey, setAddingKey] = useState(false);
  const [addingMember, setAddingMember] = useState(false);
  const [revoking, setRevoking] = useState<Key | null>(null);
  const [removing, setRemoving] = useState<Member | null>(null);
  const [showCert, setShowCert] = useState<Key | null>(null);
  const fail = (e: unknown, en: string, ar: string) => toast("error", e instanceof PortalError ? e.message : t(en, ar));

  const team = useQuery({ queryKey: ["developer-team", handle], queryFn: () => portal<TeamDetail>("GET", `/teams/${handle}`) });
  const refresh = () => qc.invalidateQueries({ queryKey: ["developer-team", handle] });
  const revoke = useMutation({
    mutationFn: (k: Key) => portal("POST", `/teams/${handle}/keys/${k.key_id}/revoke`),
    onSuccess: () => { toast("success", t("Key revoked", "أُلغي المفتاح")); setRevoking(null); refresh(); },
    onError: (e) => fail(e, "Couldn't revoke it", "تعذر الإلغاء"),
  });
  const remove = useMutation({
    mutationFn: (m: Member) => portal("DELETE", `/teams/${handle}/members/${m.id}`),
    onSuccess: (_, m) => {
      toast("success", m.id === me?.id ? t("You left the team", "غادرت الفريق") : t("Removed from the team", "أُزيل من الفريق"));
      setRemoving(null);
      qc.invalidateQueries({ queryKey: ["developer-me"] });
      if (m.id === me?.id) navigate(devPath("/portal"));
      else refresh();
    },
    onError: (e) => fail(e, "Couldn't remove them", "تعذرت الإزالة"),
  });

  const back = (
    <Link to={devPath("/portal")} className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
      <ChevronLeft className="size-4 rtl:-scale-x-100" /> {t("Teams", "الفرق")}
    </Link>
  );
  if (team.isPending) return <div className="flex justify-center p-12"><Spinner /></div>;
  if (team.isError) {
    return <>{back}<ErrorBox message={team.error instanceof PortalError ? team.error.message : t("Couldn't load the team", "تعذر تحميل الفريق")} onRetry={() => team.refetch()} /></>;
  }

  const data = team.data;
  const owner = data.role === "owner";
  const active = data.keys.filter((k) => !k.revoked_at);
  const revoked = data.keys.filter((k) => k.revoked_at);
  const self = removing?.id === me?.id;

  return (
    <>
      {back}
      <PageHeader
        title={data.name}
        description={<>{t("This team's modules start with ", "وحدات هذا الفريق تبدأ بـ ")}<Code>{data.handle}.</Code> · {t("your role: ", "دورك: ")}{owner ? t("owner", "مالك") : t("member", "عضو")}</>}
      />
      <div className="grid gap-6">
        <Packages handle={data.handle} />
        <Panel
          title={t("Signing keys", "مفاتيح التوقيع")}
          aside={<Button size="sm" onClick={() => setAddingKey(true)}><Plus className="size-4" /> {t("Key", "مفتاح")}</Button>}
          flush
        >
          {active.length === 0 ? (
            <div className="p-5">
              <Empty icon={<KeyRound className="size-10" strokeWidth={1.25} />} text={t("No active keys", "لا مفاتيح فعالة")}
                     hint={t("Register a key for Mizan to certify, then sign your modules' packages with it.", "سجّل مفتاحًا ليشهد له ميزان فتوقّع به حزم وحداتك.")} />
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
                    <span className="text-xs text-muted-foreground">{t("registered", "سُجّل")} {when(k.created_at)}</span>
                  </span>
                  <span className="flex gap-1">
                    <Button size="sm" variant="ghost" onClick={() => setShowCert(k)}>{t("Certificate", "الشهادة")}</Button>
                    {owner && (
                      <Button size="sm" variant="ghost" onClick={() => setRevoking(k)} aria-label={t(`Revoke the key ${k.name}`, `إلغاء المفتاح ${k.name}`)}>
                        <Trash2 className="size-4" /> {t("Revoke", "إلغاء")}
                      </Button>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          )}
          {revoked.length > 0 && (
            <details className="border-t border-line px-5 py-3 text-xs text-muted-foreground">
              <summary className="cursor-pointer select-none">{t(`Revoked keys (${revoked.length})`, `مفاتيح ملغاة (${revoked.length})`)}</summary>
              <ul className="mt-2 space-y-1">
                {revoked.map((k) => (
                  <li key={k.id}>{k.name} <Code>{k.key_id}</Code> · {t("revoked", "أُلغي")} {when(k.revoked_at)}</li>
                ))}
              </ul>
            </details>
          )}
        </Panel>

        <Panel
          title={t("Members", "الأعضاء")}
          aside={owner && <Button size="sm" variant="outline" onClick={() => setAddingMember(true)}><UserPlus className="size-4" /> {t("Member", "عضو")}</Button>}
          flush
        >
          <ul className="divide-y divide-line">
            {data.members.map((m) => (
              <li key={m.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3">
                <span className="min-w-0">
                  <span className="flex items-center gap-2 text-sm font-semibold text-foreground">
                    {m.full_name} {m.id === me?.id && <span className="text-xs font-normal text-muted-foreground">{t("(you)", "(أنت)")}</span>}
                    <Badge tone={m.role === "owner" ? "brand" : "muted"}>{m.role === "owner" ? t("Owner", "مالك") : t("Member", "عضو")}</Badge>
                  </span>
                  <span className="code block text-xs text-muted-foreground" dir="ltr">{m.email}</span>
                </span>
                {(owner || m.id === me?.id) && (
                  <Button size="sm" variant="ghost" onClick={() => setRemoving(m)}>{m.id === me?.id ? t("Leave", "مغادرة") : t("Remove", "إزالة")}</Button>
                )}
              </li>
            ))}
          </ul>
        </Panel>
      </div>

      <Modal open={addingKey} onClose={() => setAddingKey(false)} title={t("Register a signing key", "تسجيل مفتاح توقيع")}>
        {addingKey && <AddKey handle={data.handle} onDone={() => setAddingKey(false)} />}
      </Modal>
      <Modal open={addingMember} onClose={() => setAddingMember(false)} title={t("Add a member", "إضافة عضو")}>
        {addingMember && <AddMember handle={data.handle} onDone={() => setAddingMember(false)} />}
      </Modal>
      <Modal open={!!showCert} onClose={() => setShowCert(null)} title={showCert ? t(`Certificate: ${showCert.name}`, `شهادة ${showCert.name}`) : ""}>
        {showCert && (
          <div className="space-y-3 text-sm">
            <p className="text-muted-foreground">
              {t("Save it as ", "احفظها في ")}<Code>~/.mizan/{showCert.name}.cert</Code>{t(", next to the private key.", " بجانب المفتاح الخاص.")}
            </p>
            <CopyValue value={showCert.certificate} label={t("the certificate", "الشهادة")} />
          </div>
        )}
      </Modal>
      <Confirm
        open={!!revoking}
        onClose={() => setRevoking(null)}
        onConfirm={() => revoking && revoke.mutate(revoking)}
        busy={revoke.isPending}
        title={t("Revoke the key", "إلغاء المفتاح")}
        message={t("Mizan won't accept any new package signed with this key. Modules already installed stay. This can't be undone.",
                   "لن يقبل ميزان أي حزمة جديدة موقّعة بهذا المفتاح. الوحدات المثبتة سابقًا تبقى. لا يمكن التراجع.")}
        confirmLabel={t("Revoke key", "إلغاء المفتاح")}
      />
      <Confirm
        open={!!removing}
        onClose={() => setRemoving(null)}
        onConfirm={() => removing && remove.mutate(removing)}
        busy={remove.isPending}
        title={self ? t("Leave the team", "مغادرة الفريق") : t("Remove the member", "إزالة العضو")}
        message={self
          ? t("You won't see this team or sign in its name.", "لن ترى هذا الفريق ولن توقّع باسمه.")
          : t(`${removing?.full_name ?? ""} won't be able to register keys for this team.`, `لن يتمكن ${removing?.full_name ?? ""} من تسجيل مفاتيح لهذا الفريق.`)}
        confirmLabel={self ? t("Leave", "مغادرة") : t("Remove", "إزالة")}
      />
    </>
  );
}
