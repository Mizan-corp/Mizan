// @vitest-environment jsdom
// Gating tests for the Help Desk page: no-permission gate, disabled-catalog state with
// records-preserved copy, and work-completion feature gating on the unified work list.
// Backend and hosted acceptance: docs/helpdesk-current-status.md.
import {afterEach,describe,expect,it,vi} from 'vitest';
import {cleanup,render,screen} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';

const state = vi.hoisted(() => ({
  perms: new Set<string>(),
  get: vi.fn(),
}));

vi.mock('@/lib/api', () => ({api: {get: state.get, post: vi.fn(), patch: vi.fn()}}));
vi.mock('@/stores/auth', () => ({
  useAuth: (sel: any) => sel({
    can: (p: string) => state.perms.has(p),
    user: {id: 'u1', acting_role: {id: 'r1'}},
  }),
}));
vi.mock('./ExecutionWorksheet', () => ({default: () => null}));

import HelpdeskPage from './HelpdeskPage';

const workRow = {source_module: 'field_service', source_id: 'w1', reference: 'WO-1', description: 'تسريب', source_status: 'dispatched'};
function workPayload(overrides: Record<string, unknown> = {}) {
  return {
    items: [workRow],
    read_only: true,
    source_modules: ['field_service'],
    truncated_sources: [],
    invalid_source_rows: {},
    work_completion_enabled: false,
    work_intake_enabled: false,
    work_actuals_enabled: false,
    ...overrides,
  };
}

function mount() {
  const qc = new QueryClient({defaultOptions: {queries: {retry: false}}});
  return render(
    <QueryClientProvider client={qc}>
      <HelpdeskPage />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  state.get.mockReset();
  state.perms = new Set();
});

describe('HelpdeskPage gating', () => {
  it('shows the no-permission alert and calls no endpoint without view/work grants', () => {
    mount();
    expect(screen.getByRole('alert').textContent).toContain('ليست لديك صلاحية عرض خدمات مكتب الدعم');
    expect(state.get).not.toHaveBeenCalled();
  });

  it('shows the disabled-catalog state with records-preserved copy when offerings fail (409)', async () => {
    state.perms = new Set(['helpdesk:view']);
    state.get.mockImplementation((url: string) =>
      url === '/helpdesk/offerings' ? Promise.reject(new Error('409 disabled')) : Promise.reject(new Error('unexpected ' + url)),
    );
    mount();
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('كتالوج الخدمات غير متاح');
    expect(alert.textContent).toContain('لم تُحذف أي بيانات');
    expect(alert.textContent).toContain('راجع إعدادات الموديول');
  });

  it('keeps the work list read-only and hides completion when work_completion is off', async () => {
    state.perms = new Set(['helpdesk:work:view', 'operations', 'helpdesk:work:complete']);
    state.get.mockImplementation((url: string) =>
      url === '/helpdesk/work' ? Promise.resolve(workPayload()) : Promise.reject(new Error('unexpected ' + url)),
    );
    mount();
    expect(await screen.findByText(/عرض موحّد للقراءة فقط/)).toBeTruthy();
    expect(await screen.findByText('WO-1')).toBeTruthy();
    expect(screen.queryByRole('button', {name: 'مراجعة إنهاء أمر الصيانة'})).toBeNull();
  });

  it('offers completion for a completable field-service row only when the feature is on', async () => {
    state.perms = new Set(['helpdesk:work:view', 'operations', 'helpdesk:work:complete']);
    state.get.mockImplementation((url: string) =>
      url === '/helpdesk/work'
        ? Promise.resolve(workPayload({work_completion_enabled: true}))
        : Promise.reject(new Error('unexpected ' + url)),
    );
    mount();
    expect(await screen.findByRole('button', {name: 'مراجعة إنهاء أمر الصيانة'})).toBeTruthy();
  });

  it('hides completion without the completion grant even when the feature is on', async () => {
    state.perms = new Set(['helpdesk:work:view', 'operations']);
    state.get.mockImplementation((url: string) =>
      url === '/helpdesk/work'
        ? Promise.resolve(workPayload({work_completion_enabled: true}))
        : Promise.reject(new Error('unexpected ' + url)),
    );
    mount();
    await screen.findByText('WO-1');
    expect(screen.queryByRole('button', {name: 'مراجعة إنهاء أمر الصيانة'})).toBeNull();
  });
});
