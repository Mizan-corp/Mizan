import { type ReactNode, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useQueryClient } from "@tanstack/react-query";
import { actions, type Workspace } from "@app/lib/data";
import { appUrl } from "@/lib/urls";
import { staffLoginUrl } from "@app/lib/open";
import { Button } from "@app/ui";

interface Step {
  /** `data-tour` value of the element to spotlight; none = centred card. */
  target?: string;
  title: string;
  body: ReactNode;
}

function steps(w: Workspace): Step[] {
  return [
    {
      title: "أهلًا بك في حسابك على ميزان",
      body: (
        <>
          هذه <b>لوحة المالك</b>. منها تدير منشآتك واشتراكاتك وفواتيرك، وهي منفصلة عن نظام العمل اليومي الذي يستخدمه موظفوك. خذ دقيقة لتتعرف عليها.
        </>
      ),
    },
    {
      target: "workspace",
      title: "هذه مساحة عملك",
      body: (
        <>
          <b>{w.name}</b> مساحة عمل كاملة: مخزونها ومبيعاتها وموظفوها. لو عندك فرع آخر أو نشاط ثانٍ، تضيف له مساحة عمل منفصلة تحت نفس الحساب.
        </>
      ),
    },
    {
      target: "open",
      title: "افتح النظام من هنا",
      body: (
        <>
          يفتح نظام ميزان (نقطة البيع، المخزون، الحسابات) وأنت مسجّل دخولك كمدير. أما الموظفون فيدخلون من رابط مساحة العمل:
          {w.slug && <span className="code mt-1 block break-all text-start text-[12px] text-ink">{staffLoginUrl(w.slug).replace(/^https?:\/\//, "")}</span>}
        </>
      ),
    },
    {
      target: "plan",
      title: "الفترة التجريبية والاشتراك",
      body: <>هنا ترى كم يومًا تبقى من التجربة المجانية. عندما تكون جاهزًا، اشترك من صفحة مساحة العمل وادفع بالبطاقة أو المحفظة عبر Paymob.</>,
    },
    {
      target: "new",
      title: "منشأة جديدة؟",
      body: <>أنشئ مساحة عمل أخرى في أي وقت، بنفس اسم المستخدم وكلمة المرور.</>,
    },
    {
      target: "nav-invoices",
      title: "كل فواتيرك في مكان واحد",
      body: <>فواتير كل مساحات العمل وحالة الدفع ومدة كل اشتراك.</>,
    },
    {
      title: "كل شيء جاهز",
      body: (
        <>
          من الآن، سجّل الدخول من{" "}
          <span className="code text-[12px] text-ink">{appUrl("website", "/login").replace(/^https?:\/\//, "")}</span> لتصل إلى هنا
          مباشرة. يمكنك إعادة هذه الجولة من صفحة <b>حسابي</b>.
        </>
      ),
    },
  ];
}

const PAD = 8;
const CARD_W = 360;

export default function Tour({ workspace, onOpenWorkspace, onDone }: { workspace: Workspace; onOpenWorkspace: () => void; onDone: () => void }) {
  const qc = useQueryClient();
  const list = steps(workspace);
  const [i, setI] = useState(0);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const [cardH, setCardH] = useState(220);
  const card = useRef<HTMLDivElement>(null);
  const primary = useRef<HTMLButtonElement>(null);
  const step = list[i];
  const last = i === list.length - 1;

  const measure = useCallback(() => {
    const el = step.target ? document.querySelector<HTMLElement>(`[data-tour="${step.target}"]`) : null;
    setRect(el && el.offsetParent !== null ? el.getBoundingClientRect() : null);
    if (card.current) setCardH(card.current.offsetHeight);
  }, [step.target]);

  useLayoutEffect(() => {
    const el = step.target ? document.querySelector<HTMLElement>(`[data-tour="${step.target}"]`) : null;
    el?.scrollIntoView({ block: "center", behavior: "smooth" });
    measure();
    const t = setTimeout(measure, 350);
    primary.current?.focus();
    return () => clearTimeout(t);
  }, [step.target, measure]);

  useEffect(() => {
    let raf = 0;
    const on = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(measure);
    };
    window.addEventListener("resize", on);
    window.addEventListener("scroll", on, true);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", on);
      window.removeEventListener("scroll", on, true);
    };
  }, [measure]);

  const finish = useCallback(
    async (then?: () => void) => {
      try {
        const me = await actions.tourDone();
        qc.setQueryData(["me"], me);
      } catch {
        /* the tour shows again next time; nothing else depends on it */
      }
      onDone();
      then?.();
    },
    [qc, onDone],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") void finish();
      // Right-to-left: the left arrow moves forward.
      if (e.key === "ArrowLeft" && !last) setI((n) => n + 1);
      if (e.key === "ArrowRight" && i > 0) setI((n) => n - 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [finish, i, last]);

  // Place the card under the spotlight, or above it when there's no room.
  const vw = typeof window !== "undefined" ? window.innerWidth : 1200;
  const vh = typeof window !== "undefined" ? window.innerHeight : 800;
  const width = Math.min(CARD_W, vw - 24);
  let style: React.CSSProperties;
  if (rect) {
    const below = rect.bottom + PAD + 12 + cardH < vh;
    const top = below ? rect.bottom + PAD + 12 : Math.max(12, rect.top - PAD - 12 - cardH);
    const center = rect.left + rect.width / 2;
    const left = Math.min(Math.max(12, center - width / 2), vw - width - 12);
    style = { top, left, width };
  } else {
    style = { top: Math.max(12, vh / 2 - cardH / 2), left: vw / 2 - width / 2, width };
  }

  return createPortal(
    <div className="fixed inset-0 z-[60]" dir="rtl" role="dialog" aria-modal="true" aria-labelledby="tour-title">
      {rect ? (
        <div
          className="pointer-events-none absolute rounded-xl ring-2 ring-white/80 transition-all duration-300"
          style={{
            top: rect.top - PAD,
            left: rect.left - PAD,
            width: rect.width + PAD * 2,
            height: rect.height + PAD * 2,
            boxShadow: "0 0 0 9999px rgba(38, 35, 33, 0.58)",
          }}
        />
      ) : (
        <div className="absolute inset-0 bg-[rgba(38,35,33,0.58)]" />
      )}

      <div ref={card} className="absolute rounded-xl bg-card p-5 shadow-2xl transition-all duration-300" style={style}>
        <div className="mb-3 flex items-center justify-between">
          <div className="flex gap-1" aria-label={`الخطوة ${i + 1} من ${list.length}`}>
            {list.map((_, n) => (
              <span key={n} className={`h-1.5 rounded-full transition-all ${n === i ? "w-5 bg-wine" : "w-1.5 bg-line"}`} />
            ))}
          </div>
          {!last && (
            <button onClick={() => void finish()} className="text-[13px] text-mute hover:text-ink">
              تخطَّ الجولة
            </button>
          )}
        </div>
        <h2 id="tour-title" className="title text-xl text-ink">
          {step.title}
        </h2>
        <p className="mt-2 text-[14px] leading-7 text-ink-2">{step.body}</p>
        <div className="mt-5 flex flex-wrap items-center gap-2">
          {last ? (
            <>
              <Button ref={primary} variant="primary" onClick={() => void finish(onOpenWorkspace)}>
                افتح {workspace.name}
              </Button>
              <Button variant="ghost" onClick={() => void finish()}>
                سأستكشف اللوحة أولًا
              </Button>
            </>
          ) : (
            <>
              <Button ref={primary} variant="primary" onClick={() => setI(i + 1)}>
                {i === 0 ? "ابدأ الجولة" : "التالي"}
              </Button>
              {i > 0 && (
                <Button variant="ghost" onClick={() => setI(i - 1)}>
                  السابق
                </Button>
              )}
            </>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}
