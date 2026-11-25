// @vitest-environment jsdom
import { it, expect, beforeEach, afterEach } from 'vitest';
import { createElement as h } from 'react';
import { render, fireEvent, waitFor, cleanup } from '@testing-library/react';
import MediaPickerField from './MediaPicker';
import { registerMediaClient, type MediaItem } from './mediaLibrary';
import { setUILang } from './uiStrings';

const items: MediaItem[] = [
  { id: 'm1', url: '/uploads/t/w/site_image/file-aaa111.png', size: 2048, content_type: 'image/png', created_at: null },
  { id: 'm2', url: '/uploads/t/w/site_image/file-bbb222.png', size: 2 * 1024 * 1024, content_type: 'image/png', created_at: null },
];

function client(overrides: Partial<{ upload: (f: File) => Promise<MediaItem>; remove: (id: string) => Promise<void> }> = {}) {
  return {
    async list() { return { items, total_bytes: items.reduce((a, b) => a + b.size, 0) }; },
    async upload(file: File) { return overrides.upload ? overrides.upload(file) : { id: 'm3', url: '/uploads/t/w/site_image/file-ccc333.png', size: 10, content_type: 'image/png', created_at: null }; },
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
    async upload(f) { uploaded.push(f.name); if (f.name === 'bad.png') throw new Error('type'); return { id: 'm3', url: '/uploads/t/w/site_image/file-ccc333.png', size: 1, content_type: 'image/png', created_at: null }; },
  }));
  const r = render(h(MediaPickerField, { onSelect: () => undefined }));
  fireEvent.click(r.getByRole('button', { name: 'Media library' }));
  await r.findByRole('dialog');
  const input = r.container.querySelector('input[type=file]') as HTMLInputElement;
  expect(input.multiple).toBe(true);
  fireEvent.change(input, { target: { files: [new File(['a'], 'ok.png', { type: 'image/png' }), new File(['b'], 'bad.png', { type: 'image/png' })] } });
  await waitFor(() => expect(uploaded).toEqual(['ok.png', 'bad.png']));
  await r.findByText('Some images were refused. Check the image type and size.');
});

it('surfaces the in-use conflict message on delete', async () => {
  registerMediaClient(client({
    async remove() { const { SiteApiError } = await import('./sitePages'); throw new SiteApiError(409, 'in use'); },
  }));
  window.confirm = () => true;
  const r = render(h(MediaPickerField, { onSelect: () => undefined }));
  fireEvent.click(r.getByRole('button', { name: 'Media library' }));
  await r.findByRole('dialog');
  fireEvent.click(r.getByRole('button', { name: 'Delete image file-aaa111.png' }));
  await r.findByText('This image is used in a page. Remove it from the page first.');
});
