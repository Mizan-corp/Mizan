/** Tokens for the `mizan` CLI (`mizan login`): shown once, revocable one by one. */
import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Plus, Terminal } from "lucide-react";
import { Button, ConfirmDialog, Empty, ErrorBox, Input, Modal, Spinner, useToast } from "@/components/ui";
import { CopyValue, Field, PageHeader, Panel, when } from "./kit";
import { portal, PortalError } from "./session";

interface CliToken { id: string; name: string; created_at: string | null; last_used_at: string | null; token?: string }

export default function TokensPage() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [made, setMade] = useState<CliToken | null>(null);
  const [revoking, setRevoking] = useState<CliToken | null>(null);

  const list = useQuery({ queryKey: ["developer-cli-tokens"], queryFn: () => portal<{ items: CliToken[] }>("GET", "/cli-tokens") });
  const create = useMutation({
    mutationFn: () => portal<CliToken>("POST", "/cli-tokens", { name: name.trim() || "CLI" }),
    onSuccess: (t) => { setMade(t); setName(""); qc.invalidateQueries({ queryKey: ["developer-cli-tokens"] }); },
    onError: (e) => toast("error", e instanceof PortalError ? e.message : "تعذر إنشاء الرمز"),
  });
  const revoke = useMutation({
    mutationFn: (t: CliToken) => portal("DELETE", `/cli-tokens/${t.id}`),
    onSuccess: () => { toast("success", "أُلغي الرمز"); setRevoking(null); qc.invalidateQueries({ queryKey: ["developer-cli-tokens"] }); },
    onError: (e) => toast("error", e instanceof PortalError ? e.message : "تعذر الإلغاء"),
  });
  const close = () => { setCreating(false); setMade(null); };
  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate();
  };

  return (
    <>
      <PageHeader
        title="رموز سطر الأوامر"
        description={<>رمز لكل جهاز تستخدم عليه <span className="code inline-block" dir="ltr">mizan</span>. يعمل بصلاحيات حسابك؛ ألغِ أي رمز لا تعرفه.</>}
        actions={<Button onClick={() => setCreating(true)}><Plus className="size-4" /> رمز جديد</Button>}
      />
      {list.isPending ? (
        <div className="flex justify-center p-12"><Spinner /></div>
      ) : list.isError ? (
        <ErrorBox message="تعذر تحميل الرموز" onRetry={() => list.refetch()} />
      ) : list.data.items.length === 0 ? (
        <Empty icon={<Terminal className="size-10" strokeWidth={1.25} />} text="لا رموز بعد"
               hint="أنشئ رمزًا ثم اكتب mizan login على جهازك."
               action={<Button onClick={() => setCreating(true)}><Plus className="size-4" /> رمز جديد</Button>} />
      ) : (
        <Panel flush>
          <ul className="divide-y divide-line">
            {list.data.items.map((t) => (
              <li key={t.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5">
                <span className="flex min-w-0 items-start gap-2.5">
                  <KeyRound className="mt-0.5 size-4 shrink-0 text-primary" />
                  <span>
                    <span className="block font-semibold text-foreground">{t.name}</span>
                    <span className="text-xs text-muted-foreground">
                      أُنشئ {when(t.created_at)} · {t.last_used_at ? `آخر استخدام ${when(t.last_used_at)}` : "لم يُستخدم بعد"}
                    </span>
                  </span>
                </span>
                <Button size="sm" variant="ghost" onClick={() => setRevoking(t)}>إلغاء</Button>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      <Modal open={creating} onClose={close} title="رمز جديد">
        {made?.token ? (
          <div className="space-y-4 text-sm">
            <p className="text-muted-foreground">انسخه الآن؛ لن يظهر مرة أخرى. ثم على جهازك:</p>
            <CopyValue value={made.token} label="الرمز" />
            <pre dir="ltr" className="code overflow-x-auto rounded-md border border-line bg-muted/40 p-3 text-start text-xs">mizan login</pre>
            <Button onClick={close}>تم</Button>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-4">
            <Field label="اسم يميزه" htmlFor="token-name" hint="مثل اسم الجهاز.">
              <Input id="token-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={64} placeholder="laptop" autoFocus />
            </Field>
            <div className="flex gap-2">
              <Button type="submit" disabled={create.isPending}>{create.isPending ? <Spinner /> : "إنشاء"}</Button>
              <Button type="button" variant="outline" onClick={close}>إلغاء</Button>
            </div>
          </form>
        )}
      </Modal>
      <ConfirmDialog
        open={!!revoking}
        onClose={() => setRevoking(null)}
        onConfirm={() => revoking && revoke.mutate(revoking)}
        title="إلغاء الرمز"
        message={`يتوقف الرمز «${revoking?.name ?? ""}» فورًا، وتحتاج mizan login من جديد على ذلك الجهاز.`}
        confirmLabel="إلغاء الرمز"
      />
    </>
  );
}
