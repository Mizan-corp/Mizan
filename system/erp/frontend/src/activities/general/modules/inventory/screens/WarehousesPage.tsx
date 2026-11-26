// Warehouses and branches (INV-9): add, edit, stop and bring back (`settings`). The server refuses
// to stop one that holds stock or has an open shift, and to add or bring one back beyond the plan.
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Power, Warehouse } from "lucide-react";
import { Skeleton } from "@/components/kit/skeleton";
import { api } from "@/lib/api";
import { Badge, Button, ConfirmDialog, Empty, ErrorBox, Input, Modal, Select, Spinner, useToast } from "@/components/ui";
import type { WarehouseRow } from "../api";
import { InventoryHeader } from "../components/InventoryHeader";
import { WAREHOUSE_TYPE_LABEL } from "../lib";

type Form = { id?: string; code: string; name: string; warehouse_type: string };

export default function WarehousesPage() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const list = useQuery({
    queryKey: ["warehouses", "all"],
    queryFn: () => api.get<WarehouseRow[]>("/stock/warehouses", { include_inactive: "true" }),
  });
  const [form, setForm] = useState<Form | null>(null);
  const [stopping, setStopping] = useState<WarehouseRow | null>(null);
  const refresh = () => qc.invalidateQueries({ queryKey: ["warehouses"] });

  const save = useMutation({
    mutationFn: (f: Form) => {
      const body = { code: f.code.trim(), name: f.name.trim(), warehouse_type: f.warehouse_type };
      return f.id ? api.put(`/stock/warehouses/${f.id}`, body) : api.post("/stock/warehouses", body);
    },
    onSuccess: (_r, f) => { toast("success", f.id ? "حُفظ المخزن" : "أُضيف المخزن"); setForm(null); refresh(); },
  });
  const setActive = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) => api.put(`/stock/warehouses/${id}`, { is_active: active }),
    onSuccess: (_r, v) => { toast("success", v.active ? "أُعيد تفعيل المخزن" : "أُوقف المخزن"); setStopping(null); refresh(); },
    onError: (e) => { setStopping(null); toast("error", (e as Error).message); },
  });
  const valid = !!form && !!form.code.trim() && !!form.name.trim();

  return (
    <div className="flex flex-col gap-6">
      <InventoryHeader
        title="المخازن والفروع"
        subtitle="كل فرع بيع أو مخزن له رصيده الخاص؛ يُوقف المخزن بعد تصفية رصيده"
        actions={<Button onClick={() => setForm({ code: "", name: "", warehouse_type: "warehouse" })}><Plus className="size-4" /> مخزن أو فرع</Button>}
      />
      {list.isLoading ? (
        <div className="flex flex-col gap-2">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}</div>
      ) : list.isError ? (
        <ErrorBox message={(list.error as Error).message} onRetry={() => list.refetch()} />
      ) : !list.data?.length ? (
        <Empty text="لا توجد مخازن" hint="أضف أول مخزن أو فرع بيع." icon={<Warehouse className="size-10" />} />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-line bg-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-xs text-muted">
                <th className="p-3 text-start">الكود</th>
                <th className="p-3 text-start">الاسم</th>
                <th className="p-3 text-start">النوع</th>
                <th className="p-3 text-start">الحالة</th>
                <th className="p-3 text-start"><span className="sr-only">إجراءات</span></th>
              </tr>
            </thead>
            <tbody>
              {list.data.map((w) => (
                <tr key={w.id} className={`border-b border-line/60 last:border-0 ${w.is_active === false ? "opacity-60" : ""}`}>
                  <td className="code p-3 text-xs" dir="ltr">{w.code}</td>
                  <td className="p-3 font-semibold">{w.name}</td>
                  <td className="p-3 text-xs">{WAREHOUSE_TYPE_LABEL[w.warehouse_type] ?? w.warehouse_type}</td>
                  <td className="p-3">{w.is_active === false ? <Badge tone="danger">موقوف</Badge> : <Badge tone="success">نشط</Badge>}</td>
                  <td className="p-3">
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="icon" className="size-8 px-0!" aria-label={`تعديل ${w.name}`}
                              onClick={() => setForm({ id: w.id, code: w.code, name: w.name, warehouse_type: w.warehouse_type })}>
                        <Pencil className="size-4" />
                      </Button>
                      <Button variant="ghost" size="icon" className="size-8 px-0!" disabled={setActive.isPending}
                              aria-label={w.is_active === false ? `تفعيل ${w.name}` : `إيقاف ${w.name}`}
                              onClick={() => (w.is_active === false ? setActive.mutate({ id: w.id, active: true }) : setStopping(w))}>
                        <Power className="size-4" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal open={!!form} onClose={() => setForm(null)} title={form?.id ? "تعديل المخزن" : "مخزن أو فرع جديد"}>
        {form && (
          <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); if (valid && !save.isPending) save.mutate(form); }}>
            <div>
              <label htmlFor="wh-name" className="mb-1 block text-xs font-semibold text-muted">الاسم *</label>
              <Input id="wh-name" autoFocus maxLength={128} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div>
              <label htmlFor="wh-code" className="mb-1 block text-xs font-semibold text-muted">الكود * (فريد في المنشأة)</label>
              <Input id="wh-code" className="code" dir="ltr" maxLength={32} value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
            </div>
            <div>
              <label htmlFor="wh-type" className="mb-1 block text-xs font-semibold text-muted">النوع</label>
              <Select id="wh-type" value={form.warehouse_type} onChange={(e) => setForm({ ...form, warehouse_type: e.target.value })}>
                {Object.entries(WAREHOUSE_TYPE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </Select>
            </div>
            {save.isError && <ErrorBox message={(save.error as Error).message} />}
            <Button type="submit" className="h-10 w-full font-bold" disabled={!valid || save.isPending}>
              {save.isPending ? <Spinner /> : "حفظ"}
            </Button>
          </form>
        )}
      </Modal>

      <ConfirmDialog
        open={!!stopping}
        onClose={() => setStopping(null)}
        onConfirm={() => stopping && setActive.mutate({ id: stopping.id, active: false })}
        title={stopping ? `إيقاف ${stopping.name}` : ""}
        message="لا يُستخدم المخزن الموقوف في البيع أو الشراء أو التحويل، ويبقى سجله. لا يُوقف إذا كان فيه رصيد أو وردية مفتوحة: صفِّ رصيده بتحويل أو تسوية أولاً."
        confirmLabel="إيقاف"
      />
    </div>
  );
}
