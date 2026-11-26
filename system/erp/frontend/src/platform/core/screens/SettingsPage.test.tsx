// @vitest-environment jsdom
// Gating tests for the module-based Settings page: permission gate, module navigation,
// read-only variation display, partial-save payload (only changed keys) and the
// failed-save reload requirement. Backend and visual acceptance: docs/module-settings-refactor.md.
import {afterEach,describe,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';

const state = vi.hoisted(() => ({
  perms: new Set<string>(['settings']),
  get: vi.fn(),
  post: vi.fn(),
}));

vi.mock('@/lib/api', () => ({api: {get: state.get, post: state.post, patch: vi.fn()}}));
vi.mock('@/stores/auth', () => ({
  useAuth: (sel: any) => sel({
    can: (p: string) => state.perms.has(p),
    user: {id: 'u1', acting_role: {id: 'r1'}},
  }),
}));
vi.mock('../WorkspaceSettings', () => ({default: () => null}));
vi.mock('./WorkspaceSettings', () => ({default: () => null}));

import SettingsPage from './SettingsPage';

const catalog = {
  catalog: [
    {id: 'helpdesk', name: 'مكتب الدعم', name_en: 'Help Desk', is_installed: true},
    {id: 'loyalty', name: 'الولاء', name_en: 'Loyalty', is_installed: false},
  ],
};
const helpdeskSettings = {
  module_id: 'helpdesk',
  module_name: 'مكتب الدعم',
  schema: [
    {key: 'service_catalog', label: 'كتالوج الخدمات', type: 'boolean', default: false, description: ''},
    {key: 'max_requests', label: 'حد الطلبات', type: 'number', default: 10, description: ''},
  ],
  values: {service_catalog: false, max_requests: 10},
  variation: {id: 'standard', source: 'activity', editable: false},
};

function mount() {
  const qc = new QueryClient({defaultOptions: {queries: {retry: false}}});
  return render(
    <QueryClientProvider client={qc}>
      <SettingsPage />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  state.get.mockReset();
  state.post.mockReset();
  state.perms = new Set(['settings']);
});

describe('SettingsPage gating', () => {
  it('hides module controls without the settings permission and never calls the API', () => {
    state.perms = new Set();
    mount();
    expect(screen.getByRole('alert').textContent).toContain('ليست لديك صلاحية');
    expect(state.get).not.toHaveBeenCalled();
  });

  it('lists installed modules first, marks inactive ones, and filters by search', async () => {
    state.get.mockImplementation((url: string) => {
      if (url === '/modules') return Promise.resolve(catalog);
      return Promise.reject(new Error('unexpected ' + url));
    });
    mount();
    const helpdeskBtn = await screen.findByRole('button', {name: /مكتب الدعم/});
    const loyaltyBtn = screen.getByRole('button', {name: /الولاء/});
    expect(helpdeskBtn.compareDocumentPosition(loyaltyBtn) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(loyaltyBtn.textContent).toContain('غير مفعّل في مساحة العمل');

    fireEvent.change(screen.getByLabelText('البحث في الموديولز'), {target: {value: 'loyal'}});
    expect(screen.queryByRole('button', {name: /مكتب الدعم/})).toBeNull();
    expect(screen.getByRole('button', {name: /الولاء/})).toBeTruthy();
  });

  it('shows the variation read-only and saves only changed keys', async () => {
    state.get.mockImplementation((url: string) => {
      if (url === '/modules') return Promise.resolve(catalog);
      if (url === '/modules/helpdesk/settings') return Promise.resolve(helpdeskSettings);
      return Promise.reject(new Error('unexpected ' + url));
    });
    state.post.mockResolvedValue({settings: {...helpdeskSettings.values, service_catalog: true}});
    mount();
    fireEvent.click(await screen.findByRole('button', {name: /مكتب الدعم/}));

    expect(await screen.findByText('الـ Variation الحالي')).toBeTruthy();
    expect(screen.getByText('standard')).toBeTruthy();
    expect(screen.getByText(/للعرض فقط/)).toBeTruthy();
    expect(screen.queryByRole('combobox', {name: /variation/i})).toBeNull();

    fireEvent.click(screen.getByLabelText('كتالوج الخدمات'));
    fireEvent.click(screen.getByRole('button', {name: 'حفظ إعدادات الموديول'}));
    await screen.findByText('تم حفظ التغييرات المرسلة فقط.');
    expect(state.post).toHaveBeenCalledWith('/modules/helpdesk/settings', {settings: {service_catalog: true}});
  });

  it('requires reloading values after a failed save before retrying', async () => {
    state.get.mockImplementation((url: string) => {
      if (url === '/modules') return Promise.resolve(catalog);
      if (url === '/modules/helpdesk/settings') return Promise.resolve(helpdeskSettings);
      return Promise.reject(new Error('unexpected ' + url));
    });
    state.post.mockRejectedValue(new Error('422'));
    mount();
    fireEvent.click(await screen.findByRole('button', {name: /مكتب الدعم/}));
    fireEvent.click(await screen.findByLabelText('كتالوج الخدمات'));
    fireEvent.click(screen.getByRole('button', {name: 'حفظ إعدادات الموديول'}));

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('أعد تحميل الإعدادات قبل المحاولة مجددًا');
    expect((screen.getByRole('button', {name: 'حفظ إعدادات الموديول'}) as HTMLButtonElement).disabled).toBe(true);
  });

  it('asks before discarding unsaved module changes when navigating away', async () => {
    state.get.mockImplementation((url: string) => {
      if (url === '/modules') return Promise.resolve(catalog);
      if (url === '/modules/helpdesk/settings') return Promise.resolve(helpdeskSettings);
      return Promise.reject(new Error('unexpected ' + url));
    });
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
    mount();
    fireEvent.click(await screen.findByRole('button', {name: /مكتب الدعم/}));
    fireEvent.click(await screen.findByLabelText('كتالوج الخدمات'));
    fireEvent.click(screen.getByRole('button', {name: /الولاء/}));

    expect(confirmSpy).toHaveBeenCalled();
    expect(await screen.findByText('الـ Variation الحالي')).toBeTruthy();
    expect(state.get).not.toHaveBeenCalledWith('/modules/loyalty/settings');
    confirmSpy.mockRestore();
  });
});
