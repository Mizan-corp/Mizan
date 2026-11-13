/**
 * A team's marketplace packages (ADR-007 milestone 2, #105; activities ADR-012): what is listed,
 * and every version sent for review with its outcome. Sending is a signed .mzm, here or with
 * `mizan publish`.
 */
import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Blocks, Palette, Store, Upload, Building2 } from "lucide-react";
import { Badge, Button, Empty, ErrorBox, Spinner, useToast } from "@/components/ui";
import { useDevI18n } from "./i18n";
import { Confirm, Panel, useWhen } from "./kit";
import { portal, PortalError } from "./session";

type Kind = "community" | "theme" | "activity";
interface Item {
  id: string; kind: Kind; name: string; name_en: string | null; version: string;
  status: "listed" | "delisted"; status_note: string | null; installs: number;
}
interface Version {
  id: string; item_id: string; version: string; kind: Kind; name: string | null; name_en: string | null;
  status: "in_review" | "approved" | "rejected" | "withdrawn"; submitted_at: string | null; reviewed_at: string | null; review_note: string | null;
}

const Code = ({ children }: { children: React.ReactNode }) => <span className="code inline-block" dir="ltr">{children}</span>;

export function Packages({ handle }: { handle: string }) {
  const { t, isAr } = useDevI18n();
  const when = useWhen();
  const { toast } = useToast();
  const qc = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [withdrawing, setWithdrawing] = useState<Version | null>(null);
  const key = ["developer-packages", handle];
  const q = useQuery({ queryKey: key, queryFn: () => portal<{ items: Item[]; versions: Version[] }>("GET", `/teams/${handle}/packages`) });
  const fail = (e: unknown, en: string, ar: string) => toast("error", e instanceof PortalError ? e.message : t(en, ar));

  const send = useMutation({
    mutationFn: (file: File) => portal<Version>("POST", `/teams/${handle}/packages`, file),
    onSuccess: (v) => {
      toast("success", t(`${v.item_id} ${v.version} was sent for review`, `أُرسل ${v.item_id} ${v.version} للمراجعة`));
      qc.invalidateQueries({ queryKey: key });
    },
    onError: (e) => fail(e, "Couldn't send the package", "تعذر إرسال الحزمة"),
  });
  const withdraw = useMutation({
    mutationFn: (v: Version) => portal("DELETE", `/teams/${handle}/packages/${encodeURIComponent(v.item_id)}/${encodeURIComponent(v.version)}`),
    onSuccess: () => {
      toast("success", t("Withdrawn", "سُحب الإرسال"));
      setWithdrawing(null);
      qc.invalidateQueries({ queryKey: key });
    },
    onError: (e) => fail(e, "Couldn't withdraw it", "تعذر السحب"),
  });

  const STATUS: Record<Version["status"], [string, "warning" | "success" | "danger" | "muted"]> = {
    in_review: [t("In review", "قيد المراجعة"), "warning"],
    approved: [t("Approved", "مقبول"), "success"],
    rejected: [t("Rejected", "مرفوض"), "danger"],
    withdrawn: [t("Withdrawn", "مسحوب"), "muted"],
  };
  const name = (x: { name: string | null; name_en: string | null }) => (isAr ? x.name || x.name_en : x.name_en || x.name) ?? "";
  const Icon = ({ kind }: { kind: Kind }) => {
    const I = kind === "theme" ? Palette : kind === "activity" ? Building2 : Blocks;
    return <I className="size-4 shrink-0 text-primary" />;
  };

  return (
    <Panel
      title={t("Marketplace", "السوق")}
      aside={
        <>
          <input ref={input} type="file" accept=".mzm" className="hidden" aria-label={t("Package file", "ملف الحزمة")}
                 onChange={(e) => { const f = e.target.files?.[0]; if (f) send.mutate(f); e.target.value = ""; }} />
          <Button size="sm" disabled={send.isPending} onClick={() => input.current?.click()}>
            {send.isPending ? <Spinner /> : <Upload className="size-4" />} {t("Send a package", "إرسال حزمة")}
          </Button>
        </>
      }
      flush
    >
      {q.isPending ? (
        <div className="flex justify-center p-8"><Spinner /></div>
      ) : q.isError ? (
        <div className="p-5"><ErrorBox message={q.error instanceof PortalError ? q.error.message : t("Couldn't load packages", "تعذر تحميل الحزم")} onRetry={() => q.refetch()} /></div>
      ) : !q.data.versions.length ? (
        <div className="p-5">
          <Empty icon={<Store className="size-10" strokeWidth={1.25} />} text={t("Nothing sent yet", "لم ترسل شيئًا بعد")}
                 hint={t("Send a signed module, theme or activity (.mzm) here, or run mizan publish. The Mizan team reviews it; then workspaces install modules and themes from their store, and can change to your activity. Free listings only for now.",
                         "أرسل وحدة أو مظهرًا أو نشاطًا موقّعًا (.mzm) من هنا أو نفّذ mizan publish. يراجعه فريق ميزان، ثم تثبّت المنشآت الوحدات والمظاهر من متجرها، ويمكنها التحوّل إلى نشاطك. القوائم المجانية فقط حاليًا.")} />
        </div>
      ) : (
        <>
          {q.data.items.length > 0 && (
            <ul className="divide-y divide-line border-b border-line">
              {q.data.items.map((it) => (
                <li key={it.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5">
                  <span className="min-w-0">
                    <span className="flex items-center gap-2 font-semibold text-foreground"><Icon kind={it.kind} /> {name(it)}</span>
                    <span className="text-xs text-muted-foreground">
                      <Code>{it.id} v{it.version}</Code> · {it.kind === "activity" ? t("chosen through an activity change", "يُختار عند تغيير نشاط المنشأة")
                        : t(it.installs === 1 ? "1 install" : `${it.installs} installs`, `عدد التثبيتات ${it.installs}`)}
                    </span>
                    {it.status === "delisted" && it.status_note && <span className="block text-xs text-destructive">{it.status_note}</span>}
                  </span>
                  {it.status === "listed"
                    ? <Badge tone="success">{it.kind === "activity" ? t("Available to workspaces", "متاح للمنشآت") : t("In the store", "في المتجر")}</Badge>
                    : <Badge tone="danger">{t("Removed from the store", "أُزيل من المتجر")}</Badge>}
                </li>
              ))}
            </ul>
          )}
          <p className="px-5 pt-3 text-xs font-semibold text-muted-foreground">{t("Versions sent", "الإصدارات المرسلة")}</p>
          <ul className="divide-y divide-line">
            {q.data.versions.map((v) => (
              <li key={v.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3">
                <span className="min-w-0">
                  <span className="flex items-center gap-2 text-sm text-foreground">
                    <Icon kind={v.kind} /> <span className="font-semibold">{name(v)}</span> <Code>v{v.version}</Code>
                    <Badge tone={STATUS[v.status][1]}>{STATUS[v.status][0]}</Badge>
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {t("sent", "أُرسل")} {when(v.submitted_at)}
                    {v.reviewed_at && <> · {t("reviewed", "رُوجع")} {when(v.reviewed_at)}</>}
                  </span>
                  {v.review_note && <span dir="auto" className="block text-xs text-foreground">“{v.review_note}”</span>}
                </span>
                {v.status === "in_review" && (
                  <Button size="sm" variant="ghost" onClick={() => setWithdrawing(v)}>{t("Withdraw", "سحب")}</Button>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
      <Confirm
        open={!!withdrawing}
        onClose={() => setWithdrawing(null)}
        onConfirm={() => withdrawing && withdraw.mutate(withdrawing)}
        busy={withdraw.isPending}
        title={t("Withdraw this version", "سحب هذا الإصدار")}
        message={t("It leaves the review queue. Send a newer version when it's ready.", "يخرج من قائمة المراجعة. أرسل إصدارًا أحدث عندما يجهز.")}
        confirmLabel={t("Withdraw", "سحب")}
      />
    </Panel>
  );
}
