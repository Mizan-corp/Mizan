/** The developer's teams; a team's handle is the first part of its modules' ids (acme → acme.visits). */
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, Plus, Users } from "lucide-react";
import { Badge, Button, Empty, Input, Modal, Spinner, useToast } from "@/components/ui";
import { Field, PageHeader, Panel, when } from "./kit";
import { devPath } from "./paths";
import { portal, PortalError, useDeveloper, type Team } from "./session";

const HANDLE = /^[a-z][a-z0-9_]{1,31}$/;

function NewTeam({ onDone }: { onDone: () => void }) {
  const { toast } = useToast();
  const qc = useQueryClient();
  const [handle, setHandle] = useState("");
  const [name, setName] = useState("");
  const create = useMutation({
    mutationFn: () => portal<Team>("POST", "/teams", { handle, name }),
    onSuccess: (t) => {
      toast("success", `أُنشئ الفريق ${t.handle}`);
      qc.invalidateQueries({ queryKey: ["developer-me"] });
      onDone();
    },
    onError: (e) => toast("error", e instanceof PortalError ? e.message : "تعذر إنشاء الفريق"),
  });
  const valid = HANDLE.test(handle) && name.trim().length >= 2;
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (valid) create.mutate();
  };
  return (
    <form onSubmit={submit} className="space-y-4">
      <Field label="معرّف الفريق" htmlFor="team-handle"
             hint={<>يبدأ به معرّف كل وحداتك: <span className="code inline-block" dir="ltr">{handle || "acme"}.visits</span>. حروف إنجليزية صغيرة وأرقام و _ ، ولا يتغير بعد إنشائه.</>}>
        <Input id="team-handle" dir="ltr" className="text-start" value={handle} autoFocus
               onChange={(e) => setHandle(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ""))} maxLength={32} required />
      </Field>
      <Field label="اسم الفريق" htmlFor="team-name" hint="كما يراه أصحاب المنشآت مع وحداتك.">
        <Input id="team-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={128} required />
      </Field>
      <div className="flex gap-2">
        <Button type="submit" disabled={!valid || create.isPending}>{create.isPending ? <Spinner /> : "إنشاء الفريق"}</Button>
        <Button type="button" variant="outline" onClick={onDone}>إلغاء</Button>
      </div>
    </form>
  );
}

export default function TeamsPage() {
  const { me } = useDeveloper();
  const [creating, setCreating] = useState(false);
  const teams = me?.teams ?? [];
  return (
    <>
      <PageHeader
        title={`أهلًا ${me?.full_name.split(" ")[0] ?? ""}`}
        description="فرقك ومفاتيح توقيعها. كل وحدة توقّعها باسم فريق، ومعرّفها يبدأ بمعرّفه."
        actions={<Button onClick={() => setCreating(true)}><Plus className="size-4" /> فريق جديد</Button>}
      />
      {teams.length === 0 ? (
        <Empty
          icon={<Users className="size-10" strokeWidth={1.25} />}
          text="لا فرق بعد"
          hint="أنشئ فريقًا لتسجيل مفتاح توقيع وبدء بناء وحداتك، أو اطلب من مالك فريق إضافتك ببريدك."
          action={<Button onClick={() => setCreating(true)}><Plus className="size-4" /> إنشاء فريق</Button>}
        />
      ) : (
        <Panel title="فرقك" flush>
          <ul className="divide-y divide-line">
            {teams.map((t) => (
              <li key={t.id}>
                <Link to={devPath(`/portal/teams/${t.handle}`)}
                      className="flex items-center justify-between gap-3 px-5 py-4 transition hover:bg-muted/40 focus-visible:bg-muted/40 focus-visible:outline-none">
                  <span className="min-w-0">
                    <span className="flex items-center gap-2">
                      <span className="font-bold text-foreground">{t.name}</span>
                      <Badge tone={t.role === "owner" ? "brand" : "muted"}>{t.role === "owner" ? "مالك" : "عضو"}</Badge>
                    </span>
                    <span className="mt-0.5 block text-xs text-muted-foreground">
                      <span className="code inline-block" dir="ltr">{t.handle}.*</span> · أُنشئ {when(t.created_at)}
                    </span>
                  </span>
                  <ChevronLeft className="size-4 shrink-0 text-muted-foreground" />
                </Link>
              </li>
            ))}
          </ul>
        </Panel>
      )}
      <Modal open={creating} onClose={() => setCreating(false)} title="فريق جديد">
        {creating && <NewTeam onDone={() => setCreating(false)} />}
      </Modal>
    </>
  );
}
