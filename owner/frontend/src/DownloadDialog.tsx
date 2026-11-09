import { useQuery } from "@tanstack/react-query";
import { Check, Copy, Download as DownloadIcon, FileKey2, MonitorDown, Server } from "lucide-react";
import { useState } from "react";
import { actions, type Workspace } from "@app/lib/data";
import { date, errorText, MODE } from "@app/lib/format";
import { Button, ErrorNote, Modal, Skeleton } from "@app/ui";

const PLATFORM = { windows: "Windows", linux: "Linux" } as const;

/** Save the key as "Mizan - <workspace>.mzn": Mizan Setup finds it in Downloads by itself. */
function saveLicenceFile(name: string, key: string) {
  const safe = name.replace(/[\\/:*?"<>|]+/g, " ").trim() || "workspace";
  const blob = new Blob([`# Mizan licence: ${name}\n${key}\n`], { type: "application/octet-stream" });
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement("a"), { href: url, download: `Mizan - ${safe}.mzn` });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** What a single-device or LAN workspace needs: the installer and its licence key. */
export function DownloadDialog({ workspace, open, onClose }: { workspace: Workspace; open: boolean; onClose: () => void }) {
  const q = useQuery({ queryKey: ["download", workspace.id], queryFn: () => actions.download(workspace.id), enabled: open, staleTime: 0 });
  const [copied, setCopied] = useState(false);
  const lan = workspace.deployment_mode === "lan";

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`تنزيل ${workspace.name}`}
      description={MODE[workspace.deployment_mode]?.desc}
    >
      {q.isPending ? (
        <div className="grid gap-3">
          <Skeleton className="h-12" />
          <Skeleton className="h-24" />
        </div>
      ) : q.isError ? (
        <ErrorNote>{errorText(q.error)}</ErrorNote>
      ) : (
        <div className="grid gap-5">
          <section>
            <h3 className="mb-2 text-sm font-bold text-ink">برنامج التثبيت</h3>
            {q.data.installers.length ? (
              <div className="grid gap-2">
                {q.data.installers.map((i) => (
                  <a key={i.platform} href={i.url} className="block">
                    <Button variant="primary" className="w-full justify-between">
                      <span className="flex items-center gap-2">
                        {lan ? <Server /> : <MonitorDown />} ميزان لـ {PLATFORM[i.platform]}
                      </span>
                      <span className="data text-xs opacity-80">
                        {i.version && `v${i.version}`} {i.size_mb && `· ${i.size_mb} MB`}
                      </span>
                    </Button>
                  </a>
                ))}
              </div>
            ) : (
              <p className="rounded-lg bg-sand/70 px-3.5 py-3 text-sm leading-relaxed text-ink-2">
                برنامج التثبيت قيد التجهيز وسيظهر هنا فور توفره. احتفظ بملف الترخيص أدناه: ستحتاجه عند التثبيت.
              </p>
            )}
            <Button variant="secondary" className="mt-2 w-full" onClick={() => saveLicenceFile(workspace.name, q.data.licence_key)}>
              <FileKey2 /> ملف الترخيص (.mzn)
            </Button>
          </section>

          <section>
            <h3 className="mb-2 text-sm font-bold text-ink">الخطوات</h3>
            <ol className="grid gap-1.5 text-sm leading-relaxed text-ink-2 [counter-reset:step]">
              {(lan
                ? [
                    "نزّل برنامج التثبيت وملف الترخيص على الجهاز الذي سيعمل كخادم (يبقى مُشغّلًا أثناء العمل).",
                    "شغّل برنامج التثبيت: يجد ملف الترخيص تلقائيًا. اختر كلمة مرور المدير.",
                    "على أجهزة الكاشير والمكاتب: افتح العنوان الذي يعرضه المعالج في المتصفح (مثل https://mizan.local).",
                  ]
                : [
                    "نزّل برنامج التثبيت وملف الترخيص على الكمبيوتر الذي ستعمل عليه.",
                    "شغّل برنامج التثبيت: يجد ملف الترخيص تلقائيًا. اختر كلمة مرور المدير.",
                    "افتح ميزان من سطح المكتب. يعمل بدون إنترنت.",
                  ]
              ).map((s, i) => (
                <li key={i} className="flex gap-2.5">
                  <span className="data grid size-5 shrink-0 place-items-center rounded-full bg-wine-soft text-[11px] font-bold text-wine">{i + 1}</span>
                  {s}
                </li>
              ))}
            </ol>
          </section>

          <section>
            <div className="mb-2 flex items-baseline justify-between">
              <h3 className="text-sm font-bold text-ink">مفتاح الترخيص</h3>
              <span className="text-xs text-mute">ساري حتى {date(q.data.valid_until)}</span>
            </div>
            <div className="relative">
              <textarea
                readOnly
                value={q.data.licence_key}
                rows={3}
                dir="ltr"
                className="code w-full resize-none rounded-lg border border-line bg-sand/40 p-3 pr-11 text-[11px] leading-relaxed text-ink-2"
                onFocus={(e) => e.currentTarget.select()}
                aria-label="مفتاح الترخيص"
              />
              <button
                onClick={() =>
                  navigator.clipboard.writeText(q.data.licence_key).then(() => {
                    setCopied(true);
                    setTimeout(() => setCopied(false), 1800);
                  })
                }
                className="absolute right-2 top-2 rounded-md p-1.5 text-mute hover:bg-card hover:text-ink"
                aria-label="نسخ المفتاح"
              >
                {copied ? <Check className="size-4 text-ok" /> : <Copy className="size-4" />}
              </button>
            </div>
            <p className="mt-1.5 text-xs leading-relaxed text-mute">
              بعد الدفع يتجدد الترخيص تلقائيًا عندما يتصل الجهاز بالإنترنت. إذا كان الجهاز لا يتصل أبدًا، انسخ المفتاح الجديد من هنا
              وأدخله في البرنامج.
            </p>
          </section>
        </div>
      )}
    </Modal>
  );
}

export function DownloadButton({ workspace, className }: { workspace: Workspace; className?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant="primary" onClick={() => setOpen(true)} className={className} disabled={workspace.status === "suspended"}>
        تنزيل <DownloadIcon />
      </Button>
      {open && <DownloadDialog workspace={workspace} open onClose={() => setOpen(false)} />}
    </>
  );
}
