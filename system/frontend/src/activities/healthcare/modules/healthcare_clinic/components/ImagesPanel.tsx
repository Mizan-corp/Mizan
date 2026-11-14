import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Download, FileScan, Trash2, Upload, X } from "lucide-react";
import { api, apiUrl } from "@/lib/api";
import { Badge } from "@/components/kit/badge";
import { Button } from "@/components/kit/button";
import { Input } from "@/components/kit/input";
import { useDialogMutation } from "../useClinicActions";
import type { ClinicImage, ImageModality } from "../types";
import QueryState from "./QueryState";
import { labelClass, selectClass } from "./formStyles";

const MODALITIES: Record<ImageModality, string> = { XR: "أشعة سينية", US: "موجات صوتية", CT: "مقطعية", MRI: "رنين مغناطيسي", other: "أخرى" };
const MAX_MB = 50;
const ACCEPT = "image/jpeg,image/png,image/webp,.dcm,application/dicom";
const size = (bytes: number) => (bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`);

function Lightbox({ images, index, onIndex, onClose }: { images: ClinicImage[]; index: number; onIndex: (i: number) => void; onClose: () => void }) {
  const img = images[index];
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.stopPropagation(); onClose(); }
      // RTL: the right arrow goes back, the left arrow goes forward.
      if (e.key === "ArrowLeft" && index < images.length - 1) onIndex(index + 1);
      if (e.key === "ArrowRight" && index > 0) onIndex(index - 1);
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [index, images.length, onIndex, onClose]);
  return (
    <div className="fixed inset-0 z-[60] bg-black/90 flex flex-col" role="dialog" aria-modal="true" aria-label="عارض الصور الطبية" dir="rtl">
      <div className="flex items-center justify-between p-3 text-white text-xs">
        <div className="space-x-2 space-x-reverse">
          <span className="font-bold">{MODALITIES[img.modality]}</span>
          <span className="opacity-70">{img.original_name}</span>
          {img.notes && <span className="opacity-90">— {img.notes}</span>}
        </div>
        <div className="flex items-center gap-2">
          <span className="num opacity-70">{index + 1} / {images.length}</span>
          <a href={apiUrl(img.url)} download={img.original_name || undefined} className="p-2 rounded hover:bg-white/10" aria-label="تنزيل الصورة"><Download className="size-4" /></a>
          <button type="button" onClick={onClose} className="p-2 rounded hover:bg-white/10" aria-label="إغلاق العارض"><X className="size-4" /></button>
        </div>
      </div>
      <div className="flex-1 flex items-center justify-center gap-2 p-4 min-h-0">
        <button type="button" disabled={index === 0} onClick={() => onIndex(index - 1)} className="p-2 text-white disabled:opacity-20" aria-label="السابقة"><ChevronRight className="size-6" /></button>
        <img src={apiUrl(img.url)} alt={`${MODALITIES[img.modality]} ${img.original_name}`} className="max-h-full max-w-full object-contain" />
        <button type="button" disabled={index === images.length - 1} onClick={() => onIndex(index + 1)} className="p-2 text-white disabled:opacity-20" aria-label="التالية"><ChevronLeft className="size-6" /></button>
      </div>
    </div>
  );
}

// Medical images of a patient (#44): upload (clinicians), thumbnail grid, lightbox for JPEG/PNG/WebP,
// a download tile for DICOM. Every file is loaded through a short-lived signed link.
export default function ImagesPanel({ patientId, encounterId, canUpload }: { patientId: string; encounterId?: string; canUpload: boolean }) {
  const { run, busy } = useDialogMutation();
  const queryClient = useQueryClient();
  const [onlyEncounter, setOnlyEncounter] = useState(!!encounterId);
  const [file, setFile] = useState<File | null>(null);
  const [modality, setModality] = useState<ImageModality>("XR");
  const [notes, setNotes] = useState("");
  const [open, setOpen] = useState<number | null>(null);
  const key = ["clinic-images", patientId, onlyEncounter ? encounterId : "all"];
  const query = useQuery<ClinicImage[]>({
    queryKey: key,
    queryFn: () => api.get(`/clinic/patients/${patientId}/images`, { encounter_id: onlyEncounter ? encounterId : undefined }),
    refetchInterval: 4 * 60 * 1000, // links live 5 minutes
  });
  const rows = query.data ?? [];
  const viewable = rows.filter((r) => !r.is_dicom);
  const tooBig = !!file && file.size > MAX_MB * 1024 * 1024;

  const upload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || tooBig) return;
    const form = new FormData();
    form.append("file", file);
    form.append("modality", modality);
    form.append("notes", notes);
    if (encounterId) form.append("encounter_id", encounterId);
    const ok = await run(() => api.postForm(`/clinic/patients/${patientId}/images`, form), "تم رفع الصورة الطبية", "تعذر رفع الصورة", []);
    if (ok) {
      setFile(null);
      setNotes("");
      (e.target as HTMLFormElement).reset();
      void queryClient.invalidateQueries({ queryKey: ["clinic-images", patientId] });
    }
  };
  const remove = async (img: ClinicImage) => {
    if (!window.confirm(`حذف الصورة ${img.original_name || ""} نهائياً؟`)) return;
    const ok = await run(() => api.del(`/clinic/images/${img.id}`), "تم حذف الصورة", "تعذر حذف الصورة", []);
    if (ok) void queryClient.invalidateQueries({ queryKey: ["clinic-images", patientId] });
  };

  return (
    <div className="space-y-3">
      {canUpload && (
        <form onSubmit={upload} className="grid grid-cols-1 sm:grid-cols-6 gap-2 text-xs rounded-lg border border-border/60 p-3 bg-muted/10">
          <div className="sm:col-span-2">
            <label htmlFor="img-file" className={labelClass}>الملف (JPEG، PNG، WebP، DICOM حتى {MAX_MB} ميجابايت) *</label>
            <input id="img-file" type="file" required accept={ACCEPT} onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="block w-full text-xs file:me-2 file:rounded-md file:border file:border-border file:bg-background file:px-2 file:py-1.5" />
            {tooBig && <p role="alert" className="text-[10px] text-destructive-ink mt-1">الملف أكبر من {MAX_MB} ميجابايت</p>}
          </div>
          <div>
            <label htmlFor="img-modality" className={labelClass}>النوع</label>
            <select id="img-modality" value={modality} onChange={(e) => setModality(e.target.value as ImageModality)} className={selectClass}>
              {(Object.keys(MODALITIES) as ImageModality[]).map((m) => <option key={m} value={m}>{MODALITIES[m]} ({m})</option>)}
            </select>
          </div>
          <div className="sm:col-span-2">
            <label htmlFor="img-notes" className={labelClass}>ملاحظات</label>
            <Input id="img-notes" value={notes} onChange={(e) => setNotes(e.target.value)} className="h-9 text-xs" placeholder="مثال: أشعة صدر أمامية" />
          </div>
          <div className="flex items-end">
            <Button type="submit" size="sm" className="h-9 text-xs gap-1.5 w-full" disabled={busy || !file || tooBig}><Upload className="size-3.5" />رفع</Button>
          </div>
        </form>
      )}
      {encounterId && (
        <label className="flex items-center gap-2 text-xs text-muted-foreground">
          <input type="checkbox" checked={onlyEncounter} onChange={(e) => setOnlyEncounter(e.target.checked)} />
          صور هذا الكشف فقط
        </label>
      )}
      <QueryState query={query} what="الصور الطبية" className="">
        {rows.length === 0 ? (
          <p className="py-8 text-center text-xs text-muted-foreground rounded-xl border border-dashed border-border">لا توجد صور طبية مرفوعة.</p>
        ) : (
          <ul className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
            {rows.map((img) => (
              <li key={img.id} className="rounded-lg border border-border/60 overflow-hidden bg-card">
                {img.is_dicom ? (
                  <a href={apiUrl(img.url)} download={img.original_name || undefined}
                    className="aspect-square flex flex-col items-center justify-center gap-1 bg-muted/30 text-muted-foreground hover:text-foreground"
                    aria-label={`تنزيل ملف DICOM ${img.original_name}`}>
                    <FileScan className="size-8" />
                    <span className="text-[10px] font-semibold">DICOM — تنزيل</span>
                    <span className="text-[10px]">يُفتح في برنامج عرض DICOM</span>
                  </a>
                ) : (
                  <button type="button" onClick={() => setOpen(viewable.indexOf(img))} className="block w-full aspect-square bg-black/90 cursor-zoom-in"
                    aria-label={`عرض ${MODALITIES[img.modality]} ${img.original_name}`}>
                    <img src={apiUrl(img.url)} alt="" loading="lazy" className="w-full h-full object-contain" />
                  </button>
                )}
                <div className="p-2 text-[10px] space-y-0.5">
                  <div className="flex items-center justify-between gap-1">
                    <Badge variant="outline" className="text-[10px]">{img.modality}</Badge>
                    <span className="num text-muted-foreground">{size(img.size)}</span>
                  </div>
                  <div className="truncate" title={img.original_name}>{img.notes || img.original_name}</div>
                  <div className="flex items-center justify-between text-muted-foreground">
                    <span className="num">{new Date(img.created_at).toLocaleDateString("ar-EG")}</span>
                    {canUpload && (
                      <button type="button" onClick={() => void remove(img)} className="p-1 rounded hover:bg-muted hover:text-destructive-ink" aria-label={`حذف ${img.original_name}`}>
                        <Trash2 className="size-3" />
                      </button>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </QueryState>
      {open !== null && viewable[open] && <Lightbox images={viewable} index={open} onIndex={setOpen} onClose={() => setOpen(null)} />}
    </div>
  );
}
