/**
 * A role's screens: its main screen, its menu (groups, order, names) and its dashboard widgets.
 * Everything listed comes from the installed modules; a screen or widget the role has no
 * permission for can be placed but won't show (marked), since a layout never grants access.
 */
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderPlus, RotateCcw, Save, ShieldOff } from "lucide-react";
import { api } from "@/lib/api";
import { Badge, Button, ConfirmDialog, ErrorBox, Input, Select, Spinner, useToast } from "@/components/ui";
import { Skeleton } from "@/components/kit/skeleton";
import { iconFor } from "@app/lib/nav";
import {
  move, newId, SIZE_LABELS,
  type CatalogueScreen, type DashboardEntry, type MenuGroupDraft, type RoleLayoutDraft, type RoleLayoutResponse,
} from "./api";
import { EditorBlock, RowControls } from "./parts";

function toDraft(r: RoleLayoutResponse): RoleLayoutDraft {
  return {
    home: r.layout.home,
    menu: r.layout.menu.map((g) => ({ id: g.id, label: g.label, items: g.items.map((i) => ({ ...i })) })),
    dashboard: r.layout.dashboard.map((e) => (typeof e === "string" ? { id: e, size: null } : { id: e.id, size: e.size ?? null })),
  };
}

function NotAllowed() {
  return (
    <span className="inline-flex shrink-0 items-center gap-1 rounded bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700 dark:text-amber-400"
          title="الدور لا يملك صلاحية هذه الشاشة، فلن تظهر لمن يعمل به">
      <ShieldOff className="size-3" /> بلا صلاحية
    </span>
  );
}

export function RoleLayoutEditor({ roleId }: { roleId: string }) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const data = useQuery({
    queryKey: ["designer-role", roleId],
    queryFn: () => api.get<RoleLayoutResponse>(`/settings/designer/roles/${roleId}`),
  });
  const [draft, setDraft] = useState<RoleLayoutDraft | null>(null);
  const [confirmReset, setConfirmReset] = useState(false);
  useEffect(() => { if (data.data) setDraft(toDraft(data.data)); }, [data.data]);

  const screens = useMemo(() => new Map((data.data?.screens ?? []).map((s) => [s.id, s])), [data.data]);
  const widgets = useMemo(() => new Map((data.data?.widgets ?? []).map((w) => [w.id, w])), [data.data]);
  const dirty = !!draft && !!data.data && JSON.stringify(draft) !== JSON.stringify(toDraft(data.data));

  const after = (r: RoleLayoutResponse | null) => {
    if (r) qc.setQueryData(["designer-role", roleId], r);
    else qc.invalidateQueries({ queryKey: ["designer-role", roleId] });
    qc.invalidateQueries({ queryKey: ["designer"] });
    qc.invalidateQueries({ queryKey: ["role-screens"] });
  };
  const save = useMutation({
    mutationFn: () => api.put<RoleLayoutResponse>(`/settings/designer/roles/${roleId}`, draft),
    onSuccess: (r) => { after(r); toast("success", "تم حفظ شاشات الدور"); },
    onError: (e: Error) => toast("error", e.message),
  });
  const reset = useMutation({
    mutationFn: () => api.del(`/settings/designer/roles/${roleId}`),
    onSuccess: () => { after(null); setConfirmReset(false); toast("success", "عادت شاشات الدور إلى الافتراضي"); },
    onError: (e: Error) => toast("error", e.message),
  });

  if (data.isLoading || !draft) {
    return <div className="flex flex-col gap-4" aria-busy="true">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-40 w-full rounded-xl" />)}</div>;
  }
  if (data.isError) return <ErrorBox message={(data.error as Error).message} onRetry={() => data.refetch()} />;
  const role = data.data!;

  const setMenu = (menu: MenuGroupDraft[]) => setDraft({ ...draft, menu });
  const setGroup = (gi: number, g: MenuGroupDraft) => setMenu(draft.menu.map((x, i) => (i === gi ? g : x)));
  const inMenu = new Set(draft.menu.flatMap((g) => g.items.map((i) => i.screen)));
  const notInMenu = role.screens.filter((s) => !inMenu.has(s.id));
  const onDashboard = new Set(draft.dashboard.map((d) => d.id));
  const label = (s: CatalogueScreen | undefined, fallback: string) => s?.label ?? fallback;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-bold">{role.role.name}</h2>
          <Badge tone={role.custom ? "brand" : "muted"}>{role.custom ? "مخصص لهذه المنشأة" : "الافتراضي للنشاط"}</Badge>
        </div>
        <div className="flex items-center gap-2">
          {role.custom && (
            <Button variant="outline" size="sm" onClick={() => setConfirmReset(true)} disabled={reset.isPending}>
              <RotateCcw className="size-3.5" /> استعادة الافتراضي
            </Button>
          )}
          {dirty && <Button variant="ghost" size="sm" onClick={() => setDraft(toDraft(role))}>تجاهل التعديلات</Button>}
          <Button size="sm" onClick={() => save.mutate()} disabled={!dirty || save.isPending}>
            {save.isPending ? <Spinner /> : <Save className="size-3.5" />} حفظ
          </Button>
        </div>
      </div>

      <EditorBlock title="الشاشة الرئيسية" description="أول ما يفتح لمن يعمل بهذا الدور، وتظهر في أعلى لوحة التحكم.">
        <Select aria-label="الشاشة الرئيسية" className="max-w-md" value={draft.home ?? ""} onChange={(e) => setDraft({ ...draft, home: e.target.value || null })}>
          {role.screens.map((s) => <option key={s.id} value={s.id}>{s.label}{s.allowed ? "" : " (بلا صلاحية)"}</option>)}
        </Select>
      </EditorBlock>

      <EditorBlock
        title="القائمة"
        description="رتّب المجموعات والشاشات وسمّها كما يعرفها فريقك. تختفي المجموعة الفارغة."
        actions={
          <Button variant="outline" size="sm" onClick={() => setMenu([...draft.menu, { id: newId("g"), label: "مجموعة جديدة", items: [] }])}>
            <FolderPlus className="size-3.5" /> مجموعة
          </Button>
        }
      >
        <div className="flex flex-col gap-4">
          {draft.menu.map((g, gi) => (
            <div key={g.id} className="rounded-lg border border-border/70">
              <div className="flex items-center gap-2 border-b border-border/60 bg-secondary/40 px-3 py-2">
                <Input aria-label="اسم المجموعة" className="h-8 max-w-xs text-sm font-semibold" value={g.label} maxLength={64}
                       onChange={(e) => setGroup(gi, { ...g, label: e.target.value })} />
                <span className="text-xs text-muted-foreground">{g.items.length} شاشة</span>
                <div className="ms-auto">
                  <RowControls what={g.label} index={gi} count={draft.menu.length} onMove={(d) => setMenu(move(draft.menu, gi, d))}
                               onRemove={() => setMenu(draft.menu.filter((_, i) => i !== gi))} removeLabel="حذف المجموعة" />
                </div>
              </div>
              <ul className="divide-y divide-border/50">
                {g.items.map((item, ii) => {
                  const s = screens.get(item.screen);
                  const Icon = iconFor(item.icon ?? s?.icon);
                  return (
                    <li key={item.screen} className="flex flex-wrap items-center gap-2 px-3 py-1.5">
                      <Icon className="size-4 shrink-0 text-muted-foreground" />
                      <Input aria-label={`اسم «${label(s, item.screen)}» في القائمة`} className="h-8 min-w-0 flex-1 text-sm"
                             value={item.label ?? ""} placeholder={label(s, item.screen)} maxLength={64}
                             onChange={(e) => setGroup(gi, { ...g, items: g.items.map((x, i) => (i === ii ? { ...x, label: e.target.value || undefined } : x)) })} />
                      <span className="hidden font-mono text-[11px] text-muted-foreground sm:inline" dir="ltr">{s?.path ?? "—"}</span>
                      {!s && <Badge tone="danger">غير متاحة</Badge>}
                      {s && !s.allowed && <NotAllowed />}
                      <Select aria-label="نقل إلى مجموعة" className="h-8 w-auto text-xs" value={g.id}
                              onChange={(e) => {
                                const to = draft.menu.findIndex((x) => x.id === e.target.value);
                                setMenu(draft.menu.map((x, i) => i === gi ? { ...x, items: x.items.filter((_, j) => j !== ii) }
                                  : i === to ? { ...x, items: [...x.items, item] } : x));
                              }}>
                        {draft.menu.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
                      </Select>
                      <RowControls what={item.label || label(s, item.screen)} index={ii} count={g.items.length}
                                   onMove={(d) => setGroup(gi, { ...g, items: move(g.items, ii, d) })}
                                   onRemove={() => setGroup(gi, { ...g, items: g.items.filter((_, i) => i !== ii) })} removeLabel="إزالة من القائمة" />
                    </li>
                  );
                })}
              </ul>
              <div className="border-t border-border/50 px-3 py-2">
                <Select aria-label={`إضافة شاشة إلى «${g.label}»`} className="h-8 max-w-sm text-xs" value=""
                        onChange={(e) => e.target.value && setGroup(gi, { ...g, items: [...g.items, { screen: e.target.value }] })}
                        disabled={!notInMenu.length}>
                  <option value="">{notInMenu.length ? "+ إضافة شاشة…" : "كل الشاشات في القائمة"}</option>
                  {notInMenu.map((s) => <option key={s.id} value={s.id}>{s.label}{s.allowed ? "" : " (بلا صلاحية)"}</option>)}
                </Select>
              </div>
            </div>
          ))}
          {!draft.menu.length && <p className="text-sm text-muted-foreground">لا توجد مجموعات. أضف مجموعة لتبدأ القائمة.</p>}
        </div>
      </EditorBlock>

      <EditorBlock title="لوحة التحكم" description="المؤشرات التي تظهر لهذا الدور، بترتيبها ومقاسها.">
        <ul className="flex flex-col divide-y divide-border/50 rounded-lg border border-border/70">
          {draft.dashboard.map((d, di) => {
            const w = widgets.get(d.id);
            const setEntry = (entry: DashboardEntry) => setDraft({ ...draft, dashboard: draft.dashboard.map((x, i) => (i === di ? entry : x)) });
            return (
              <li key={d.id} className="flex flex-wrap items-center gap-2 px-3 py-1.5">
                <span className="min-w-0 flex-1 truncate text-sm">{w?.label ?? d.id}</span>
                {!w && <Badge tone="danger">غير متاح</Badge>}
                {w && !w.allowed && <NotAllowed />}
                <Select aria-label={`مقاس «${w?.label ?? d.id}»`} className="h-8 w-auto text-xs" value={d.size ?? w?.size ?? "s"}
                        onChange={(e) => setEntry({ ...d, size: e.target.value as DashboardEntry["size"] })}>
                  {Object.entries(SIZE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </Select>
                <RowControls what={w?.label ?? d.id} index={di} count={draft.dashboard.length}
                             onMove={(delta) => setDraft({ ...draft, dashboard: move(draft.dashboard, di, delta) })}
                             onRemove={() => setDraft({ ...draft, dashboard: draft.dashboard.filter((_, i) => i !== di) })} removeLabel="إزالة من اللوحة" />
              </li>
            );
          })}
          {!draft.dashboard.length && <li className="px-3 py-3 text-sm text-muted-foreground">اللوحة فارغة لهذا الدور.</li>}
        </ul>
        <Select aria-label="إضافة مؤشر" className="mt-3 h-8 max-w-sm text-xs" value=""
                onChange={(e) => e.target.value && setDraft({ ...draft, dashboard: [...draft.dashboard, { id: e.target.value, size: null }] })}>
          <option value="">+ إضافة مؤشر…</option>
          {role.widgets.filter((w) => !onDashboard.has(w.id)).map((w) => <option key={w.id} value={w.id}>{w.label}{w.allowed ? "" : " (بلا صلاحية)"}</option>)}
        </Select>
      </EditorBlock>

      {save.isError && <ErrorBox message={(save.error as Error).message} />}

      <ConfirmDialog
        open={confirmReset}
        onClose={() => setConfirmReset(false)}
        onConfirm={() => reset.mutate()}
        title="استعادة الشاشات الافتراضية"
        message={`ستعود الشاشة الرئيسية والقائمة ولوحة التحكم لدور «${role.role.name}» إلى ما يحدده النشاط.`}
        confirmLabel="استعادة"
      />
    </div>
  );
}
