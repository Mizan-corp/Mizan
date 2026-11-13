/** The developer's teams; a team's handle is the first part of its modules' ids (acme → acme.visits). */
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, Plus, Users } from "lucide-react";
import { Badge, Button, Empty, Input, Modal, Spinner, useToast } from "@/components/ui";
import { useDevI18n } from "./i18n";
import { Field, PageHeader, Panel, useWhen } from "./kit";
import { devPath } from "./paths";
import { portal, PortalError, useDeveloper, type Team } from "./session";

const HANDLE = /^[a-z][a-z0-9_]{1,31}$/;

function NewTeam({ onDone }: { onDone: () => void }) {
  const { toast } = useToast();
  const { t } = useDevI18n();
  const qc = useQueryClient();
  const [handle, setHandle] = useState("");
  const [name, setName] = useState("");
  const create = useMutation({
    mutationFn: () => portal<Team>("POST", "/teams", { handle, name }),
    onSuccess: (team) => {
      toast("success", t(`Team ${team.handle} created`, `أُنشئ الفريق ${team.handle}`));
      qc.invalidateQueries({ queryKey: ["developer-me"] });
      onDone();
    },
    onError: (e) => toast("error", e instanceof PortalError ? e.message : t("Couldn't create the team", "تعذر إنشاء الفريق")),
  });
  const valid = HANDLE.test(handle) && name.trim().length >= 2;
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (valid) create.mutate();
  };
  const example = <span className="code inline-block" dir="ltr">{handle || "acme"}.visits</span>;
  return (
    <form onSubmit={submit} className="space-y-4">
      <Field label={t("Team handle", "معرّف الفريق")} htmlFor="team-handle"
             hint={<>{t("Every module id of yours starts with it: ", "يبدأ به معرّف كل وحداتك: ")}{example}.{" "}
               {t("Lower-case letters, digits and _; it can't change later.", "حروف إنجليزية صغيرة وأرقام و _ ، ولا يتغير بعد إنشائه.")}</>}>
        <Input id="team-handle" dir="ltr" className="text-start" value={handle} autoFocus
               onChange={(e) => setHandle(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ""))} maxLength={32} required />
      </Field>
      <Field label={t("Team name", "اسم الفريق")} htmlFor="team-name" hint={t("Business owners see it with your modules.", "كما يراه أصحاب المنشآت مع وحداتك.")}>
        <Input id="team-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={128} required />
      </Field>
      <div className="flex gap-2">
        <Button type="submit" disabled={!valid || create.isPending}>{create.isPending ? <Spinner /> : t("Create team", "إنشاء الفريق")}</Button>
        <Button type="button" variant="outline" onClick={onDone}>{t("Cancel", "إلغاء")}</Button>
      </div>
    </form>
  );
}

export default function TeamsPage() {
  const { me } = useDeveloper();
  const { t } = useDevI18n();
  const when = useWhen();
  const [creating, setCreating] = useState(false);
  const teams = me?.teams ?? [];
  const first = me?.full_name.split(" ")[0] ?? "";
  return (
    <>
      <PageHeader
        title={t(`Hello, ${first}`, `أهلًا ${first}`)}
        description={t("Your teams and their signing keys. Every module is signed by a team, and its id starts with the team's handle.",
                       "فرقك ومفاتيح توقيعها. كل وحدة توقّعها باسم فريق، ومعرّفها يبدأ بمعرّفه.")}
        actions={<Button onClick={() => setCreating(true)}><Plus className="size-4" /> {t("New team", "فريق جديد")}</Button>}
      />
      {teams.length === 0 ? (
        <Empty
          icon={<Users className="size-10" strokeWidth={1.25} />}
          text={t("No teams yet", "لا فرق بعد")}
          hint={t("Create a team to register a signing key and start building, or ask a team owner to add you by your email.",
                  "أنشئ فريقًا لتسجيل مفتاح توقيع وبدء بناء وحداتك، أو اطلب من مالك فريق إضافتك ببريدك.")}
          action={<Button onClick={() => setCreating(true)}><Plus className="size-4" /> {t("Create a team", "إنشاء فريق")}</Button>}
        />
      ) : (
        <Panel title={t("Your teams", "فرقك")} flush>
          <ul className="divide-y divide-line">
            {teams.map((team) => (
              <li key={team.id}>
                <Link to={devPath(`/portal/teams/${team.handle}`)}
                      className="flex items-center justify-between gap-3 px-5 py-4 transition hover:bg-muted/40 focus-visible:bg-muted/40 focus-visible:outline-none">
                  <span className="min-w-0">
                    <span className="flex items-center gap-2">
                      <span className="font-bold text-foreground">{team.name}</span>
                      <Badge tone={team.role === "owner" ? "brand" : "muted"}>{team.role === "owner" ? t("Owner", "مالك") : t("Member", "عضو")}</Badge>
                    </span>
                    <span className="mt-0.5 block text-xs text-muted-foreground">
                      <span className="code inline-block" dir="ltr">{team.handle}.*</span> · {t("created", "أُنشئ")} {when(team.created_at)}
                    </span>
                  </span>
                  <ChevronRight className="size-4 shrink-0 text-muted-foreground rtl:-scale-x-100" />
                </Link>
              </li>
            ))}
          </ul>
        </Panel>
      )}
      <Modal open={creating} onClose={() => setCreating(false)} title={t("New team", "فريق جديد")}>
        {creating && <NewTeam onDone={() => setCreating(false)} />}
      </Modal>
    </>
  );
}
