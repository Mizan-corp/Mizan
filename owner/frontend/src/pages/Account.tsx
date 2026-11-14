import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { actions, type Owner, useAction, useMe } from "@app/lib/data";
import { date, errorText } from "@app/lib/format";
import { Badge, Button, ErrorNote, Field, Input, PageHeader, PageSkeleton, Panel } from "@app/ui";
import { VerifyEmailForm } from "@app/components/VerifyEmail";

function Profile({ me }: { me: Owner }) {
  const save = useAction(actions.updateMe);
  const [form, setForm] = useState({ full_name: me.full_name, email: me.email ?? "", phone: me.phone ?? "" });
  const [error, setError] = useState<string | null>(null);
  const dirty = form.full_name !== me.full_name || form.email !== (me.email ?? "") || form.phone !== (me.phone ?? "");

  function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    save.mutateAsync(form).then(() => toast.success("تم الحفظ"), (err) => setError(errorText(err)));
  }

  return (
    <Panel title="بياناتك">
      <form onSubmit={submit} className="grid max-w-lg gap-4">
        <Field label="اسم المستخدم" hint="تدخل به هنا وفي صفحات الدخول لمساحات عملك.">
          <Input value={me.login} disabled dir="ltr" className="code text-start disabled:bg-sand/50" />
        </Field>
        <Field label="الاسم">
          <Input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required minLength={2} />
        </Field>
        <Field label="رقم الموبايل">
          <Input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} inputMode="tel" dir="ltr" className="text-start" />
        </Field>
        <Field label="البريد الإلكتروني" hint="تصلك عليه إيصالات الدفع والتذكيرات، ورمز استعادة كلمة المرور. تغييره يحتاج تأكيدًا جديدًا.">
          <Input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} type="email" dir="ltr" className="text-start" />
        </Field>
        {error && <ErrorNote>{error}</ErrorNote>}
        <div>
          <Button type="submit" variant="primary" busy={save.isPending} disabled={!dirty}>
            حفظ
          </Button>
        </div>
      </form>
      {me.email && form.email === me.email && (
        me.email_verified ? (
          <p className="mt-4"><Badge tone="ok">البريد مؤكَّد</Badge></p>
        ) : me.email_service && (
          <div className="mt-4 max-w-lg rounded-lg border border-warn/30 bg-warn-soft p-3">
            <p className="mb-2 text-[13px] font-semibold text-ink">بريدك غير مؤكَّد بعد</p>
            <VerifyEmailForm me={me} />
          </div>
        )
      )}
    </Panel>
  );
}

function Password() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [error, setError] = useState<string | null>(null);
  const change = useAction(actions.changePassword);

  function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    change.mutateAsync({ current_password: current, new_password: next }).then(
      (r) => {
        toast.success(r.workspace_logins_updated ? "تم تغيير كلمة المرور هنا وفي مساحات عملك" : "تم تغيير كلمة المرور");
        setCurrent("");
        setNext("");
      },
      (err) => setError(errorText(err)),
    );
  }

  return (
    <Panel title="كلمة المرور">
      <form onSubmit={submit} className="grid max-w-lg gap-4">
        <Field label="كلمة المرور الحالية">
          <Input type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} required dir="ltr" className="text-start" />
        </Field>
        <Field label="كلمة المرور الجديدة" hint="8 أحرف على الأقل. تتغير أيضًا لحسابك في كل مساحات عملك.">
          <Input type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} required minLength={8} dir="ltr" className="text-start" />
        </Field>
        {error && <ErrorNote>{error}</ErrorNote>}
        <div>
          <Button type="submit" variant="primary" busy={change.isPending}>
            غيّر كلمة المرور
          </Button>
        </div>
      </form>
    </Panel>
  );
}

export default function Account() {
  const me = useMe();
  const navigate = useNavigate();
  if (!me.data) return <PageSkeleton />;
  return (
    <>
      <PageHeader
        title="حسابي"
        description={me.data.created_at ? `حساب مالك منذ ${date(me.data.created_at)}` : undefined}
        actions={<Button onClick={() => navigate("/?tour=1")}>أعد الجولة التعريفية</Button>}
      />
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Profile me={me.data} />
        <Password />
      </div>
    </>
  );
}
