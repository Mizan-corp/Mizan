import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Plus } from "lucide-react";
import { Skeleton } from "@/components/kit/skeleton";
import { api } from "@/lib/api";
import { Badge, Button, Empty, ErrorBox, Input, Modal, Select, Spinner } from "@/components/ui";

interface RoleRef { id: string; code: string; name: string }
interface UserRow {
  id: string; username: string; full_name: string; role: string; is_active: boolean;
  is_manager: boolean; roles?: RoleRef[] | null; acting_role_name?: string | null;
  /** The owner's own login in this workspace: its password is managed in the owner panel (#75). */
  owner_account_id?: string | null;
  position_id?: string | null;
  position_name?: string | null;
}
interface RoleDef extends RoleRef { grants: string[]; standard: boolean }
interface PermDef { id: string; name: string; module: string }
/** A job title: general, the workspace's activity's, or the workspace's own. Suggests roles. */
interface PositionDef { id: string; name: string; activity: string | null; standard: boolean; suggested_role_ids: string[] }
export default function UsersPage() {
  const qc = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ username: "", full_name: "", password: "", role: "cashier" });
  const [permFor, setPermFor] = useState<UserRow | null>(null);
  const [perms, setPerms] = useState<string[]>([]);
  const [isManager, setIsManager] = useState(false);
  const [rolesFor, setRolesFor] = useState<UserRow | null>(null);
  const [roleIds, setRoleIds] = useState<string[]>([]);
  const [activeRoleId, setActiveRoleId] = useState<string | null>(null);
  const [positionId, setPositionId] = useState<string>("");
  const [pwFor, setPwFor] = useState<UserRow | null>(null);
  const [newPw, setNewPw] = useState("");

  const list = useQuery({ queryKey: ["users"], queryFn: () => api.get<UserRow[]>("/users") });
  // Permissions are declared by modules; roles are the platform's standard ones plus the workspace's own.
  const catalogue = useQuery({ queryKey: ["authz", "permissions"], queryFn: () => api.get<PermDef[]>("/authz/access/permissions") });
  const roles = useQuery({ queryKey: ["authz", "roles"], queryFn: () => api.get<RoleDef[]>("/authz/access/roles") });
  const positions = useQuery({ queryKey: ["authz", "positions"], queryFn: () => api.get<PositionDef[]>("/authz/access/positions") });

  const create = useMutation({
    mutationFn: () => api.post("/users", form),
    onSuccess: () => { setCreating(false); setForm({ username: "", full_name: "", password: "", role: "cashier" }); qc.invalidateQueries({ queryKey: ["users"] }); },
  });

  const savePerms = useMutation({
    mutationFn: () => api.put(`/permissions/${permFor!.id}`, { permissions: perms, is_manager: isManager }),
    onSuccess: () => { setPermFor(null); qc.invalidateQueries({ queryKey: ["users"] }); qc.invalidateQueries({ queryKey: ["authz"] }); },
  });

  const loadPerms = useMutation({
    mutationFn: (u: UserRow) => api.get<{ permissions: string[]; is_manager: boolean }>(`/permissions/${u.id}`),
    onSuccess: (res) => { setPerms(res.permissions); setIsManager(res.is_manager); },
  });

  const loadRoles = useMutation({
    mutationFn: (u: UserRow) => api.get<{ roles: RoleDef[]; active_role_id: string | null }>(`/authz/access/users/${u.id}/roles`),
    onSuccess: (res) => { setRoleIds(res.roles.map((r) => r.id)); setActiveRoleId(res.active_role_id); },
  });

  const saveRoles = useMutation({
    mutationFn: async () => {
      await api.put(`/authz/access/users/${rolesFor!.id}/position`, { position_id: positionId || null });
      return api.put(`/authz/access/users/${rolesFor!.id}/roles`, {
        role_ids: roleIds,
        active_role_id: activeRoleId && roleIds.includes(activeRoleId) ? activeRoleId : null,
      });
    },
    onSuccess: () => { setRolesFor(null); qc.invalidateQueries({ queryKey: ["users"] }); },
  });

  const resetPw = useMutation({
    mutationFn: () => api.post(`/users/${pwFor!.id}/reset-password`, { new_password: newPw }),
    onSuccess: () => { setPwFor(null); setNewPw(""); },
  });

  function openPerms(u: UserRow) {
    setPermFor(u);
    setPerms([]);
    loadPerms.mutate(u);
  }

  function openRoles(u: UserRow) {
    setRolesFor(u);
    setRoleIds([]);
    setActiveRoleId(null);
    setPositionId(u.position_id ?? "");
    loadRoles.mutate(u);
  }

  /** Picking a position pre-ticks the roles it suggests (they can still be changed). */
  function pickPosition(id: string) {
    setPositionId(id);
    const suggested = positions.data?.find((p) => p.id === id)?.suggested_role_ids ?? [];
    if (suggested.length) setRoleIds((s) => [...new Set([...s, ...suggested])]);
  }

  const roleLabel = (code: string) => roles.data?.find((r) => r.code === code && r.standard)?.name ?? code;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">المستخدمون والصلاحيات</h1>
        </div>
        <Button onClick={() => setCreating(true)}><Plus size={16} /> مستخدم جديد</Button>
      </div>

      {list.isLoading ? (
        <div className="flex flex-col gap-2" aria-busy="true" aria-label="جارٍ التحميل">
            <Skeleton className="h-10 w-full" />
            {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
          </div>
      ) : list.isError ? (
        <ErrorBox message={(list.error as Error).message} onRetry={() => list.refetch()} />
      ) : !list.data?.length ? (
        <Empty text="لا يوجد مستخدمون" />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-xs text-muted">
                <th className="p-3 text-start">اسم المستخدم</th>
                <th className="p-3 text-start">الاسم</th>
                <th className="hidden p-3 text-start lg:table-cell">المسمى الوظيفي</th>
                <th className="hidden p-3 text-start md:table-cell">الدور الحالي</th>
                <th className="hidden p-3 text-start sm:table-cell">الأدوار المسندة</th>
                <th className="p-3 text-start">الحالة</th>
                <th className="p-3 text-start"></th>
              </tr>
            </thead>
            <tbody>
              {list.data.map((u) => (
                <tr key={u.id} className="border-b border-line/60 last:border-0 hover:bg-elevated">
                  <td className="p-3 font-bold" dir="ltr">{u.username}</td>
                  <td className="w-full max-w-0 truncate p-3">{u.full_name}</td>
                  <td className="hidden p-3 text-muted lg:table-cell">{u.position_name ?? "—"}</td>
                  <td className="hidden p-3 md:table-cell"><Badge tone="brand">{u.acting_role_name ?? roleLabel(u.role)}</Badge></td>
                  <td className="hidden p-3 text-muted sm:table-cell">
                    <span className="line-clamp-1">{u.roles?.length ? u.roles.map((r) => r.name).join("، ") : "—"}</span>
                  </td>
                  <td className="p-3"><Badge tone={u.is_active ? "success" : "muted"}>{u.is_active ? "نشط" : "موقوف"}</Badge></td>
                  <td className="p-3">
                    <div className="flex gap-1">
                      <Button variant="outline" onClick={() => openRoles(u)}>الأدوار</Button>
                      <Button variant="outline" onClick={() => openPerms(u)}>الصلاحيات</Button>
                      {u.owner_account_id ? (
                        <span
                          className="rounded-md p-2 text-muted/50"
                          title="كلمة مرور المالك تُغيَّر من لوحة المالك"
                          aria-label="كلمة مرور المالك تُغيَّر من لوحة المالك"
                        >
                          <KeyRound size={16} />
                        </span>
                      ) : (
                        <button
                          className="rounded-md p-2 text-muted hover:bg-elevated hover:text-ink"
                          onClick={() => { setPwFor(u); setNewPw(""); }}
                          aria-label="كلمة مرور جديدة"
                        >
                          <KeyRound size={16} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal open={creating} onClose={() => setCreating(false)} title="مستخدم جديد">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!create.isPending && form.username && form.password && form.full_name) create.mutate();
          }}
          className="flex flex-col gap-3"
        >
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium">اسم المستخدم *</label>
              <Input autoFocus dir="ltr" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">الاسم الكامل *</label>
              <Input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium">كلمة المرور *</label>
              <Input type="password" dir="ltr" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">الدور</label>
              <Select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                {(roles.data ?? []).filter((r) => r.standard).map((r) => <option key={r.code} value={r.code}>{r.name}</option>)}
              </Select>
            </div>
          </div>
          {create.isError && <ErrorBox message={(create.error as Error).message} />}
          <Button type="submit" className="w-full h-10 font-bold" disabled={create.isPending || !form.username || !form.password || !form.full_name}>
            {create.isPending ? <Spinner /> : "إنشاء المستخدم"}
          </Button>
        </form>
      </Modal>

      <Modal open={!!permFor} onClose={() => setPermFor(null)} title={`صلاحيات — ${permFor?.full_name ?? ""}`} wide>
        <div className="flex flex-col gap-6">
          <p className="text-sm text-muted-foreground">
            صلاحيات الدور الذي يعمل به المستخدم الآن. إذا اختلفت عن دوره القياسي يُنشأ له دور خاص به بهذه الصلاحيات بالضبط.
          </p>
          {loadPerms.isPending || catalogue.isLoading ? (
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3" aria-busy="true">
              {Array.from({ length: 9 }).map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
            </div>
          ) : loadPerms.isError || catalogue.isError ? (
            <ErrorBox message={((loadPerms.error ?? catalogue.error) as Error).message} />
          ) : (
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {(catalogue.data ?? []).map((p) => (
                <label key={p.id} className={`flex cursor-pointer items-center gap-2 rounded-lg border p-2.5 text-sm transition-colors ${perms.includes(p.id) ? "border-primary bg-primary/10 font-bold text-primary" : "border-line hover:bg-secondary/40"}`}>
                  <input
                    type="checkbox"
                    checked={perms.includes(p.id)}
                    onChange={(e) => setPerms((s) => e.target.checked ? [...s, p.id] : s.filter((x) => x !== p.id))}
                  />
                  {p.name}
                </label>
              ))}
            </div>
          )}
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={isManager} onChange={(e) => setIsManager(e.target.checked)} />
            مدير (يعتمد المرتجعات والخصومات)
          </label>
          {savePerms.isError && <ErrorBox message={(savePerms.error as Error).message} />}
          <Button className="w-full h-10 font-bold" disabled={savePerms.isPending || loadPerms.isPending || !perms.length} onClick={() => savePerms.mutate()}>
            {savePerms.isPending ? <Spinner /> : "حفظ الصلاحيات"}
          </Button>
        </div>
      </Modal>

      <Modal open={!!rolesFor} onClose={() => setRolesFor(null)} title={`الأدوار — ${rolesFor?.full_name ?? ""}`} wide>
        <div className="flex flex-col gap-4">
          <div>
            <label htmlFor="user-position" className="mb-1 block text-sm font-medium">المسمى الوظيفي</label>
            <Select id="user-position" value={positionId} onChange={(e) => pickPosition(e.target.value)} disabled={positions.isLoading}>
              <option value="">— بدون مسمى —</option>
              {positions.data?.some((p) => p.standard && p.activity !== "general") && (
                <optgroup label="خاصة بنشاط المنشأة">
                  {positions.data.filter((p) => p.standard && p.activity !== "general").map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </optgroup>
              )}
              <optgroup label="عامة">
                {positions.data?.filter((p) => p.standard && p.activity === "general").map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </optgroup>
              {positions.data?.some((p) => !p.standard) && (
                <optgroup label="مسميات المنشأة">
                  {positions.data.filter((p) => !p.standard).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </optgroup>
              )}
            </Select>
            <p className="mt-1 text-xs text-muted">المسمى يقترح الأدوار المناسبة فقط؛ الأدوار وحدها تحدد الصلاحيات.</p>
          </div>
          <p className="text-sm text-muted-foreground">
            يعمل المستخدم بدور واحد في كل مرة، ويبدّل بين أدواره من القائمة العلوية. لا يمكنك إسناد دور يتجاوز صلاحيات دورك الحالي.
          </p>
          {loadRoles.isPending || roles.isLoading ? (
            <div className="flex flex-col gap-2" aria-busy="true">
              {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-11 w-full" />)}
            </div>
          ) : loadRoles.isError || roles.isError ? (
            <ErrorBox message={((loadRoles.error ?? roles.error) as Error).message} />
          ) : (
            <div className="flex max-h-[50vh] flex-col gap-2 overflow-y-auto">
              {(roles.data ?? []).map((r) => {
                const on = roleIds.includes(r.id);
                return (
                  <div key={r.id} className={`flex items-center gap-3 rounded-lg border p-2.5 text-sm ${on ? "border-primary bg-primary/10" : "border-line"}`}>
                    <label className="flex min-w-0 flex-1 cursor-pointer items-center gap-2">
                      <input
                        type="checkbox"
                        checked={on}
                        onChange={(e) => setRoleIds((s) => e.target.checked ? [...s, r.id] : s.filter((x) => x !== r.id))}
                      />
                      <span className={`truncate ${on ? "font-bold text-primary" : ""}`}>{r.name}</span>
                      {!r.standard && <Badge tone="muted">خاص بالمنشأة</Badge>}
                      <span className="num text-xs text-muted">{r.grants.length} صلاحية</span>
                    </label>
                    {on && (
                      <label className="flex shrink-0 cursor-pointer items-center gap-1 text-xs text-muted">
                        <input type="radio" name="active-role" checked={activeRoleId === r.id} onChange={() => setActiveRoleId(r.id)} />
                        الدور الحالي
                      </label>
                    )}
                  </div>
                );
              })}
            </div>
          )}
          {saveRoles.isError && <ErrorBox message={(saveRoles.error as Error).message} />}
          <Button className="w-full h-10 font-bold" disabled={saveRoles.isPending || loadRoles.isPending || !roleIds.length} onClick={() => saveRoles.mutate()}>
            {saveRoles.isPending ? <Spinner /> : "حفظ الأدوار"}
          </Button>
        </div>
      </Modal>

      <Modal open={!!pwFor} onClose={() => setPwFor(null)} title={`كلمة مرور جديدة — ${pwFor?.username ?? ""}`}>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!resetPw.isPending && newPw) resetPw.mutate();
          }}
          className="flex flex-col gap-3"
        >
          <div>
            <label className="mb-1 block text-sm font-medium">كلمة المرور الجديدة</label>
            <Input autoFocus type="password" dir="ltr" value={newPw} onChange={(e) => setNewPw(e.target.value)} />
          </div>
          {resetPw.isError && <ErrorBox message={(resetPw.error as Error).message} />}
          <Button type="submit" className="w-full h-10 font-bold" disabled={resetPw.isPending || !newPw}>
            {resetPw.isPending ? <Spinner /> : "تعيين كلمة المرور"}
          </Button>
        </form>
      </Modal>
    </div>
  );
}
