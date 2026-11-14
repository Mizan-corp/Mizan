/**
 * Verifying the owner's email (#72): a 6-digit code to the address, typed back here. Used on the
 * account page and in the banner the panel shows until the address is verified.
 */
import { type FormEvent, useState } from "react";
import { MailCheck } from "lucide-react";
import { toast } from "sonner";
import { Link } from "react-router-dom";
import { actions, type Owner, useAction, useMe } from "@app/lib/data";
import { errorText } from "@app/lib/format";
import { Button, ErrorNote, Field, Input, Modal } from "@app/ui";

export function VerifyEmailForm({ me, onDone }: { me: Owner; onDone?: () => void }) {
  const send = useAction(actions.sendEmailCode);
  const verify = useAction(actions.verifyEmail);
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  function ask() {
    setError(null);
    send.mutateAsync(undefined).then((r) => setSentTo(r.to ?? me.email), (err) => setError(errorText(err)));
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    verify.mutateAsync(code).then(
      () => {
        toast.success("تم تأكيد بريدك");
        onDone?.();
      },
      (err) => setError(errorText(err)),
    );
  }

  return (
    <form onSubmit={submit} className="grid gap-3">
      <p className="text-sm text-ink-2">
        {sentTo
          ? <>أرسلنا رمزًا جديدًا إلى <span className="code" dir="ltr">{sentTo}</span>. صالح 15 دقيقة؛ إن لم يصل فانظر في البريد غير المرغوب.</>
          : <>اكتب الرمز المكوّن من 6 أرقام الذي أرسلناه إلى <span className="code" dir="ltr">{me.email}</span>، أو اطلب رمزًا جديدًا.</>}
      </p>
      <Field label="الرمز">
        <Input value={code} onChange={(e) => setCode(e.target.value.replace(/[^0-9]/g, "").slice(0, 6))} inputMode="numeric"
               autoComplete="one-time-code" dir="ltr" className="code text-center text-lg tracking-[0.4em]" placeholder="••••••" />
      </Field>
      {error && <ErrorNote>{error}</ErrorNote>}
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" variant="primary" busy={verify.isPending} disabled={code.length !== 6}>تأكيد</Button>
        <Button type="button" variant="ghost" busy={send.isPending} onClick={ask}>
          {sentTo ? "أرسل رمزًا آخر" : "أرسل رمزًا جديدًا"}
        </Button>
      </div>
    </form>
  );
}

/** Across the panel until the email is verified: password reset and receipts depend on it. */
export function VerifyEmailBanner() {
  const me = useMe();
  const [open, setOpen] = useState(false);
  const o = me.data;
  if (!o || o.email_verified || !o.email_service) return null;
  return (
    <div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-warn/30 bg-warn-soft px-4 py-3 text-sm text-ink-2">
      <span className="flex items-center gap-2">
        <MailCheck className="size-4 shrink-0 text-warn" aria-hidden />
        {o.email
          ? <>أكّد بريدك <span className="code" dir="ltr">{o.email}</span> لتصلك الإيصالات والتذكيرات، ولتستعيد كلمة المرور إن نسيتها.</>
          : "أضف بريدك الإلكتروني لتصلك الإيصالات والتذكيرات، ولتستعيد كلمة المرور إن نسيتها."}
      </span>
      {o.email ? (
        <Button size="sm" variant="primary" onClick={() => setOpen(true)}>أكّد الآن</Button>
      ) : (
        <Link to="/account"><Button size="sm" variant="primary">أضف بريدك</Button></Link>
      )}
      {open && (
        <Modal open onClose={() => setOpen(false)} title="تأكيد بريدك الإلكتروني">
          <VerifyEmailForm me={o} onDone={() => setOpen(false)} />
        </Modal>
      )}
    </div>
  );
}
