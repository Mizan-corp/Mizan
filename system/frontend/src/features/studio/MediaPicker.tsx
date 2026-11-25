import { useEffect, useRef, useState } from 'react';
import { isInUseError, mediaClient, type MediaItem } from './mediaLibrary';
import { t } from './uiStrings';

/** Button + dialog that lets an image field pick an uploaded file from the workspace
 * media library, upload a new one, or delete unused ones. Selection writes the durable
 * /uploads URL into the block field via onSelect. */
export default function MediaPickerField({ onSelect }: { onSelect: (url: string) => void }) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<MediaItem[] | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const refresh = async () => {
    const api = mediaClient();
    if (!api) { setError(t('المكتبة غير متاحة في الجلسة دي.')); return; }
    try { setItems((await api.list()).items); setError(''); }
    catch { setError(t('تعذّر تحميل مكتبة الصور. حاول تاني.')); }
  };
  useEffect(() => { if (open) void refresh(); }, [open]);

  const upload = async (file: File) => {
    const api = mediaClient();
    if (!api) return;
    setBusy(true);
    try { await api.upload(file); await refresh(); setError(''); }
    catch (e) { setError(e instanceof Error && e.message ? e.message : t('الرفع اترفض. راجع نوع الصورة وحجمها.')); }
    finally { setBusy(false); }
  };

  const remove = async (item: MediaItem) => {
    const api = mediaClient();
    if (!api) return;
    setBusy(true);
    try { await api.remove(item.id); await refresh(); setError(''); }
    catch (e) {
      setError(isInUseError(e)
        ? t('الصورة مستخدمة في صفحة. احذفها من الصفحة الأول.')
        : t('تعذّر حذف الصورة. حاول تاني.'));
    } finally { setBusy(false); }
  };

  // The dialog is absolutely positioned; this wrapper is its anchor so the panel
  // opens under the button instead of escaping to the nearest positioned ancestor.
  return <div className="media-picker-field">
    <button type="button" className="media-library-open" onClick={() => setOpen(true)}>{t('مكتبة الصور')}</button>
    {open && <div className="media-picker" role="dialog" aria-label={t('مكتبة الصور')}>
      <div className="simple-panel-head">
        <strong>{t('مكتبة الصور')}</strong>
        <button aria-label={t('قفل المكتبة')} onClick={() => setOpen(false)}>×</button>
      </div>
      <div className="media-picker-actions">
        <button type="button" disabled={busy} onClick={() => fileInput.current?.click()}>{t('ارفع صورة')}</button>
        <input ref={fileInput} type="file" accept="image/png,image/jpeg,image/gif,image/webp" hidden
          onChange={e => { const f = e.target.files?.[0]; if (f) void upload(f); e.target.value = ''; }} />
      </div>
      {error && <p role="alert" className="link-error">{error}</p>}
      {items === null && !error && <p className="hint">{t('بنحمل الصور…')}</p>}
      {items !== null && items.length === 0 && <p className="hint">{t('مفيش صور لسه. ارفع أول صورة.')}</p>}
      <div className="media-picker-grid">
        {(items ?? []).map(item => <figure key={item.id}>
          <button type="button" className="media-pick" onClick={() => { onSelect(item.url); setOpen(false); }}>
            <img src={item.url} alt="" loading="lazy" />
          </button>
          <figcaption>
            <button type="button" disabled={busy} className="media-delete" aria-label={t('احذف الصورة')} onClick={() => void remove(item)}>{t('حذف')}</button>
          </figcaption>
        </figure>)}
      </div>
      <p className="hint">{t('الصور بتتخزن لمساحة عملك بس. الصورة المستخدمة في صفحة مش بتتمسح غير بعد ما تشيلها منها.')}</p>
    </div>}
  </div>;
}
