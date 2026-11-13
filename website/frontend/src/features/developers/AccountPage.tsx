/** The developer's account: who they are, and changing the password (ends every portal session). */
import { useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { Button, Input, Spinner, useToast } from "@/components/ui";
import { useDevI18n } from "./i18n";
import { Field, PageHeader, Panel } from "./kit";
import { clearDeveloperSession, portal, PortalError, useDeveloper } from "./session";

export default function AccountPage() {
  const { me } = useDeveloper();
  const { t } = useDevI18n();
  const { toast } = useToast();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const change = useMutation({
    mutationFn: () => portal("POST", "/me/password", { current_password: current, new_password: next }),
    onSuccess: () => {
      toast("success", t("Password changed. Sign in with the new one.", "تغيّرت كلمة المرور. سجّل الدخول بها."));
      clearDeveloperSession();
    },
    onError: (e) => toast("error", e instanceof PortalError ? e.message : t("Couldn't change it", "تعذر التغيير")),
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    change.mutate();
  };
  return (
    <>
      <PageHeader
        title={t("Account", "حسابي")}
        description={t("A developer account is separate from a business owner's account; you can have both.",
                       "حساب المطور منفصل عن حساب مالك المنشأة، ويمكن أن يكون لك الاثنان.")}
      />
      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title={t("Details", "البيانات")}>
          <dl className="space-y-3 text-sm">
            <div><dt className="text-muted-foreground">{t("Name", "الاسم")}</dt><dd className="font-semibold">{me?.full_name}</dd></div>
            <div><dt className="text-muted-foreground">{t("Email (your sign-in)", "البريد (اسم الدخول)")}</dt><dd className="code" dir="ltr">{me?.email}</dd></div>
          </dl>
        </Panel>
        <Panel title={t("Change password", "تغيير كلمة المرور")}>
          <form onSubmit={submit} className="space-y-4">
            <Field label={t("Current password", "كلمة المرور الحالية")} htmlFor="pw-current">
              <Input id="pw-current" type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} required />
            </Field>
            <Field label={t("New password", "الجديدة")} htmlFor="pw-new"
                   hint={t("At least 8 characters. Every portal session ends; CLI tokens keep working.", "8 أحرف على الأقل. ستُغلق كل جلسات البوابة؛ رموز سطر الأوامر تبقى.")}>
              <Input id="pw-new" type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} minLength={8} required />
            </Field>
            <Button type="submit" disabled={!current || next.length < 8 || change.isPending}>
              {change.isPending ? <Spinner /> : t("Change", "تغيير")}
            </Button>
          </form>
        </Panel>
      </div>
    </>
  );
}
