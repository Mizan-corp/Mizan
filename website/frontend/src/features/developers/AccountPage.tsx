/** The developer's account: who they are, and changing the password (ends every portal session). */
import { useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { Button, Input, Spinner, useToast } from "@/components/ui";
import { Field, PageHeader, Panel } from "./kit";
import { clearDeveloperSession, portal, PortalError, useDeveloper } from "./session";

export default function AccountPage() {
  const { me } = useDeveloper();
  const { toast } = useToast();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const change = useMutation({
    mutationFn: () => portal("POST", "/me/password", { current_password: current, new_password: next }),
    onSuccess: () => {
      toast("success", "تغيّرت كلمة المرور. سجّل الدخول بها.");
      clearDeveloperSession();
    },
    onError: (e) => toast("error", e instanceof PortalError ? e.message : "تعذر التغيير"),
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    change.mutate();
  };
  return (
    <>
      <PageHeader title="حسابي" description="حساب المطور منفصل عن حساب مالك المنشأة، ويمكن أن يكون لك الاثنان." />
      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="البيانات">
          <dl className="space-y-3 text-sm">
            <div><dt className="text-muted-foreground">الاسم</dt><dd className="font-semibold">{me?.full_name}</dd></div>
            <div><dt className="text-muted-foreground">البريد (اسم الدخول)</dt><dd className="code inline-block" dir="ltr">{me?.email}</dd></div>
          </dl>
        </Panel>
        <Panel title="تغيير كلمة المرور">
          <form onSubmit={submit} className="space-y-4">
            <Field label="كلمة المرور الحالية" htmlFor="pw-current">
              <Input id="pw-current" type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} required />
            </Field>
            <Field label="الجديدة" htmlFor="pw-new" hint="8 أحرف على الأقل. ستُغلق كل جلسات البوابة؛ رموز سطر الأوامر تبقى.">
              <Input id="pw-new" type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} minLength={8} required />
            </Field>
            <Button type="submit" disabled={!current || next.length < 8 || change.isPending}>{change.isPending ? <Spinner /> : "تغيير"}</Button>
          </form>
        </Panel>
      </div>
    </>
  );
}
