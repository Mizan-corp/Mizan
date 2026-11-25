// @vitest-environment jsdom
import { it, expect, beforeEach, afterEach, vi } from 'vitest';
import { createElement as h } from 'react';
import { render, fireEvent, waitFor, cleanup } from '@testing-library/react';
import MediaPickerField from './MediaPicker';
import { registerMediaClient, type MediaItem } from './mediaLibrary';
import { setUILang } from './uiStrings';

const items: MediaItem[] = [
  { id: 'm1', url: '/uploads/t/w/site_image/file-aaa111.png', size: 2048, content_type: 'image/png', name: 'hero-sunset.png', created_at: null },
  { id: 'm2', url: '/uploads/t/w/site_image/file-bbb222.png', size: 2 * 1024 * 1024, content_type: 'image/png', name: null, created_at: null },
];

function client(overrides: Partial<{ upload: (f: File) => Promise<MediaItem>; remove: (id: string) => Promise<void> }> = {}) {
  return {
    async list() { return { items, total_bytes: items.reduce((a, b) => a + b.size, 0) }; },
    async upload(file: File) { return overrides.upload ? overrides.upload(file) : { id: 'm3', url: '/uploads/t/w/site_image/file-ccc333.png', size: 10, content_type: 'image/png', name: file.name, created_at: null }; },
    async remove(id: string) { if (overrides.remove) return overrides.remove(id); },
  };
}

beforeEach(() => { setUILang('en'); });
afterEach(() => { registerMediaClient(null); cleanup(); });

it('opens a modal dialog with the library grid and picks through the confirm bar', async () => {
  registerMediaClient(client());
  let picked = '';
  const r = render(h(MediaPickerField, { onSelect: (u: string) => { picked = u; } }));
  fireEvent.click(r.getByRole('button', { name: 'Media library' }));
  const dialog = await r.findByRole('dialog', { name: 'Media library' });
  expect(dialog.getAttribute('aria-modal')).toBe('true');
  // count + total size summary
  await waitFor(() => expect(dialog.textContent).toContain('2 images'));
  // original filenames show when stored; URL tail is the fallback
  expect(dialog.textContent).toContain('hero-sunset.png');
  expect(dialog.textContent).toContain('file-bbb222.png');
  expect(dialog.textContent).toContain('2.0 MB');
  // Use stays disabled until a tile is selected
  const useBtn = r.getByRole('button', { name: 'Use image' }) as HTMLButtonElement;
  expect(useBtn.disabled).toBe(true);
  fireEvent.click(r.getByRole('button', { name: 'file-bbb222.png' }));
  expect((r.getByRole('button', { name: 'Use image' }) as HTMLButtonElement).disabled).toBe(false);
  fireEvent.click(r.getByRole('button', { name: 'Use image' }));
  expect(picked).toBe('/uploads/t/w/site_image/file-bbb222.png');
  await waitFor(() => expect(r.queryByRole('dialog')).toBeNull());
});

it('uploads every selected file and reports partial refusals', async () => {
  const uploaded: string[] = [];
  registerMediaClient(client({
    async upload(f) { uploaded.push(f.name); if (f.name === 'bad.png') throw new Error('type'); return { id: 'm3', url: '/uploads/t/w/site_image/file-ccc333.png', size: 1, content_type: 'image/png', name: f.name, created_at: null }; },
  }));
  const r = render(h(MediaPickerField, { onSelect: () => undefined }));
  fireEvent.click(r.getByRole('button', { name: 'Media library' }));
  await r.findByRole('dialog');
  const input = r.baseElement.querySelector('input[type=file]') as HTMLInputElement;
  expect(input.multiple).toBe(true);
  fireEvent.change(input, { target: { files: [new File(['a'], 'ok.png', { type: 'image/png' }), new File(['b'], 'bad.png', { type: 'image/png' })] } });
  await waitFor(() => expect(uploaded).toEqual(['ok.png', 'bad.png']));
  await r.findByText('Some images were refused. Check the image type and size.');
});

it('traps focus, locks background scroll, closes on Escape and restores focus', async () => {
  registerMediaClient(client());
  const r = render(h(MediaPickerField, { onSelect: () => undefined }));
  const opener = r.getByRole('button', { name: 'Media library' });
  (opener as HTMLButtonElement).focus = vi.fn();
  fireEvent.click(opener);
  const dialog = await r.findByRole('dialog');
  // scroll locked and focus moved into the modal
  expect(document.body.style.overflow).toBe('hidden');
  expect(dialog.contains(document.activeElement)).toBe(true);
  // Tab from the last focusable wraps to the first; Shift+Tab from first wraps to last
  const focusables = [...dialog.querySelectorAll('button:not(:disabled)')];
  (focusables[focusables.length - 1] as HTMLElement).focus();
  fireEvent.keyDown(dialog, { key: 'Tab' });
  expect(document.activeElement).toBe(focusables[0]);
  (focusables[0] as HTMLElement).focus();
  fireEvent.keyDown(dialog, { key: 'Tab', shiftKey: true });
  expect(document.activeElement).toBe(focusables[focusables.length - 1]);
  // Escape closes, scroll restored, focus returned to the opener
  fireEvent.keyDown(dialog, { key: 'Escape' });
  await waitFor(() => expect(r.queryByRole('dialog')).toBeNull());
  expect(document.body.style.overflow).toBe('');
  expect((opener as HTMLButtonElement).focus).toHaveBeenCalled();
});

it('surfaces the in-use conflict message on delete', async () => {
  registerMediaClient(client({
    async remove() { const { SiteApiError } = await import('./sitePages'); throw new SiteApiError(409, 'in use'); },
  }));
  window.confirm = () => true;
  const r = render(h(MediaPickerField, { onSelect: () => undefined }));
  fireEvent.click(r.getByRole('button', { name: 'Media library' }));
  await r.findByRole('dialog');
  fireEvent.click(r.getByRole('button', { name: 'Delete image hero-sunset.png' }));
  await r.findByText('This image is used in a page. Remove it from the page first.');
});
