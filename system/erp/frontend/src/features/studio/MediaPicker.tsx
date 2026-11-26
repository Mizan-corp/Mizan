import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { isInUseError, mediaClient, type MediaItem } from './mediaLibrary';
import { t } from './uiStrings';

function fileName(url: string): string {
  try { return decodeURIComponent(url.split('/').pop() ?? url) || url; } catch { return url; }
}
/** The original upload filename when the library has it, else the stored URL tail. */
function displayName(item: MediaItem): string {
  return item.name || fileName(item.url);
}
function formatSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${bytes} B`;
}

/** Opens the workspace media library as a centered modal: multi-upload, tile grid
 * with selection, per-item delete, and a confirm bar that writes the durable
 * /uploads URL into the block field via onSelect. The modal portals to <body> so
 * canvas overlays never stack above it, traps focus, locks background scroll and
 * marks the app root inert while open. */
export default function MediaPickerField({ onSelect }: { onSelect: (url: string) => void }) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<MediaItem[] | null>(null);
  const [totalBytes, setTotalBytes] = useState(0);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [view, setView] = useState<'grid' | 'list'>('grid');
  const openBtn = useRef<HTMLButtonElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const modalRef = useRef<HTMLDivElement>(null);

  // While open: move focus in, lock background scroll, inert the app root so the
  // modal alone owns interaction; on close: restore everything and refocus the
  // button that opened it.
  useEffect(() => {
    if (!open) return;
    const root = document.getElementById('root');
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    root?.setAttribute('inert', '');
    closeRef.current?.focus();
    return () => {
      document.body.style.overflow = prevOverflow;
      root?.removeAttribute('inert');
      openBtn.current?.focus();
    };
  }, [open]);

  const onModalKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') { close(); return; }
    if (e.key !== 'Tab') return;
    const modal = modalRef.current;
    if (!modal) return;
    const focusables = [...modal.querySelectorAll<HTMLElement>('button:not(:disabled), input:not([hidden])')];
    if (!focusables.length) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (e.shiftKey && document.activeElement === first) { last.focus(); e.preventDefault(); }
    else if (!e.shiftKey && document.activeElement === last) { first.focus(); e.preventDefault(); }
  };

  const refresh = async () => {
    const api = mediaClient();
    if (!api) { setError(t('المكتبة غير متاحة في الجلسة دي.')); return; }
    try {
      const list = await api.list();
      setItems(list.items); setTotalBytes(list.total_bytes); setError('');
    } catch { setError(t('تعذّر تحميل مكتبة الصور. حاول تاني.')); }
  };
  useEffect(() => { if (open) { setSelected(null); void refresh(); } }, [open]);

  const uploadFiles = async (files: File[]) => {
    if (!files.length) return;
    const api = mediaClient();
    if (!api) { setError(t('المكتبة غير متاحة في الجلسة دي.')); return; }
    setUploading(true); setError('');
    let failed = 0;
    let detail = '';
    for (const file of files) {
      try { await api.upload(file); }
      catch (e) { failed++; if (!detail && e instanceof Error && e.message) detail = e.message; }
    }
    await refresh().catch(() => undefined);
    if (failed) {
      setError(failed === files.length && detail
        ? detail
        : t('بعض الصور اترفضت. راجع نوع الصورة وحجمها.'));
    }
    setUploading(false);
  };

  const remove = async (item: MediaItem) => {
    const api = mediaClient();
    if (!api) return;
    if (!window.confirm(t('تحذف الصورة دي من المكتبة؟ لو مش مستخدمة في صفحة هتتمسح نهائيًا.'))) return;
    setBusy(true);
    try {
      await api.remove(item.id);
      if (selected === item.url) setSelected(null);
      await refresh(); setError('');
    } catch (e) {
      setError(isInUseError(e)
        ? t('الصورة مستخدمة في صفحة. احذفها من الصفحة الأول.')
        : t('تعذّر حذف الصورة. حاول تاني.'));
    } finally { setBusy(false); }
  };

  const pick = (url: string) => { onSelect(url); setOpen(false); setSelected(null); };
  const close = () => { if (!uploading) setOpen(false); };

  const modal = open && <div className="media-overlay" onClick={e => { if (e.target === e.currentTarget) close(); }}>
    <div className="media-modal" role="dialog" aria-modal="true" aria-label={t('مكتبة الصور')} ref={modalRef} onKeyDown={onModalKeyDown}>
      <header className="media-modal-head">
        <div>
          <strong>{t('مكتبة الصور')}</strong>
          {items !== null && <span className="media-count">{items.length} {t('صور')} · {formatSize(totalBytes)}</span>}
        </div>
        <div className="media-head-side">
          {items !== null && items.length > 0 && <div className="media-view-toggle" role="group" aria-label={t('طريقة العرض')}>
            <button type="button" aria-pressed={view === 'grid'} aria-label={t('عرض شبكي')} onClick={() => setView('grid')}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>
            </button>
            <button type="button" aria-pressed={view === 'list'} aria-label={t('عرض قائمة')} onClick={() => setView('list')}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M8 6h13M8 12h13M8 18h13"/><circle cx="4" cy="6" r="1" fill="currentColor"/><circle cx="4" cy="12" r="1" fill="currentColor"/><circle cx="4" cy="18" r="1" fill="currentColor"/></svg>
            </button>
          </div>}
          <button ref={closeRef} aria-label={t('قفل المكتبة')} onClick={close}>×</button>
        </div>
      </header>
      <div className={uploading ? 'media-drop busy' : 'media-drop'}
        onDragOver={e => e.preventDefault()}
        onDrop={e => { e.preventDefault(); if (!uploading) void uploadFiles([...e.dataTransfer.files]); }}>
        <input ref={fileInput} type="file" multiple accept="image/png,image/jpeg,image/gif,image/webp" hidden
          onChange={e => { void uploadFiles([...(e.target.files ?? [])]); e.target.value = ''; }} />
        {uploading
          ? <p className="media-drop-state">{t('بنرفع الصور…')}</p>
          : <>
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <rect x="3" y="3" width="18" height="18" rx="3" /><circle cx="9" cy="9" r="1.8" /><path d="M21 15.5 16.5 11 5 22" />
            </svg>
            <button type="button" className="mz-btn ghost" onClick={() => fileInput.current?.click()}>{t('ارفع صور')}</button>
            <p className="hint">{t('اسحب الصور هنا أو اضغط للاختيار')} · {t('PNG أو JPEG أو GIF أو WebP، حتى ٥ ميجا للصورة')}</p>
          </>}
      </div>
      {error && <p role="alert" className="media-error">{error}</p>}
      <div className="media-body">
        {items === null && !error && <p className="hint">{t('بنحمل الصور…')}</p>}
        {items !== null && items.length === 0 && <div className="media-empty">
          <p>{t('مفيش صور لسه. ارفع أول صورة.')}</p>
        </div>}
        {view === 'grid' && <div className="media-grid">
          {(items ?? []).map(item => {
            const active = selected === item.url;
            return <figure key={item.id} className={active ? 'selected' : ''}>
              <button type="button" className="media-tile" aria-pressed={active} aria-label={displayName(item)}
                onClick={() => setSelected(active ? null : item.url)}
                onDoubleClick={() => pick(item.url)}>
                <img src={item.url} alt="" loading="lazy" />
              </button>
              <figcaption>
                <span title={displayName(item)}>{displayName(item)}</span>
                <small>{formatSize(item.size)}</small>
              </figcaption>
              <button type="button" className="media-delete" disabled={busy || uploading}
                aria-label={`${t('احذف الصورة')} ${displayName(item)}`} onClick={() => void remove(item)}>×</button>
            </figure>;
          })}
        </div>}
        {view === 'list' && <div className="media-list">
          {(items ?? []).map(item => {
            const active = selected === item.url;
            return <div key={item.id} className={active ? 'media-row-item selected' : 'media-row-item'}>
              <button type="button" className="media-row" aria-pressed={active} aria-label={displayName(item)}
                onClick={() => setSelected(active ? null : item.url)}
                onDoubleClick={() => pick(item.url)}>
                <img src={item.url} alt="" loading="lazy" />
                <span className="media-row-name" title={displayName(item)}>{displayName(item)}</span>
                <small>{formatSize(item.size)}</small>
              </button>
              <button type="button" className="media-delete" disabled={busy || uploading}
                aria-label={`${t('احذف الصورة')} ${displayName(item)}`} onClick={() => void remove(item)}>×</button>
            </div>;
          })}
        </div>}
      </div>
      <footer className="media-foot">
        <span className="media-selected-name">{selected ? (items?.find(i => i.url === selected)?.name ?? fileName(selected)) : t('اختار صورة من المكتبة')}</span>
        <div className="media-foot-actions">
          <button type="button" className="mz-btn ghost" onClick={close}>{t('إلغاء')}</button>
          <button type="button" className="mz-btn primary" disabled={!selected} onClick={() => selected && pick(selected)}>{t('استخدم الصورة')}</button>
        </div>
      </footer>
      <p className="hint media-note">{t('الصور بتتخزن لمساحة عملك بس. الصورة المستخدمة في صفحة مش بتتمسح غير بعد ما تشيلها منها.')}</p>
    </div>
  </div>;

  return <>
    <button ref={openBtn} type="button" className="media-library-open" onClick={() => setOpen(true)}>{t('مكتبة الصور')}</button>
    {modal && createPortal(modal, document.body)}
  </>;
}
