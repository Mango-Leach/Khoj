import { useState, type CSSProperties, type ReactNode } from "react";
import {
  ArrowRight,
  BarChart3,
  BookOpen,
  Briefcase,
  Building2,
  Calculator,
  Check,
  CheckCircle2,
  ClipboardCheck,
  Clapperboard,
  Cog,
  Compass,
  FileSearch,
  GraduationCap,
  HelpCircle,
  Landmark,
  Lock,
  Mic,
  Milk,
  Plus,
  Scale,
  Scissors,
  ShieldAlert,
  ShieldCheck,
  Smartphone,
  Tag,
  UserCheck,
  Users,
  Wallet,
  XCircle,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { Link } from "../../components/Link";
import { entryPath } from "../../lib/routes";
import { useSession } from "../../lib/session";
import { Logo, cx } from "../../components/ui";
import { LANGS, translate, useLang, type MessageKey } from "../../lib/i18n";
import { CYCLE, useLanguageCycle, useScrollProgress } from "./hooks";
import { JobsScreen, MentorScreen, PathsScreen, ReviewScreen, SpeakScreen, Waveform } from "./mocks";
import { Reveal, WhenSeen } from "./Reveal";

const WRAP = "mx-auto w-full max-w-[1240px] px-8";

function SectionTitle({ children, id, className }: { children: ReactNode; id?: string; className?: string }) {
  return (
    <h2 id={id} className={cx("text-[clamp(32px,4.4vw,56px)] leading-[1.08] font-bold tracking-[-0.025em] text-balance", className)}>
      {children}
    </h2>
  );
}

/** One sentence per line, so a statement breaks where its meaning does. */
function Lines({ text }: { text: string }) {
  return (
    <>
      {text.split(/(?<=[.।])\s+/).map((s, i) => (
        <span key={i} className="block">
          {s}
        </span>
      ))}
    </>
  );
}

function CtaLink({ children, tone = "primary", to }: { children: ReactNode; tone?: "primary" | "light"; to?: string }) {
  const { user } = useSession();
  return (
    <Link
      to={to ?? entryPath(user)}
      className={cx(
        "group inline-flex h-16 items-center gap-3 rounded-2xl px-9 text-xl font-semibold transition-all",
        tone === "primary"
          ? "bg-accent text-white shadow-[0_14px_34px_-10px_rgb(29_78_216/0.7)] hover:bg-accent-hover"
          : "bg-white text-deep shadow-[0_14px_34px_-10px_rgb(0_0_0/0.5)] hover:bg-tint",
      )}
    >
      {children}
      <ArrowRight className="size-6 transition-transform group-hover:translate-x-1" aria-hidden="true" />
    </Link>
  );
}

// ---------------------------------------------------------------------------
// The problem: separate worlds, then KHOJ draws the lines between them
// ---------------------------------------------------------------------------

const NODES: { key: MessageKey; icon: LucideIcon; x: number; y: number }[] = [
  { key: "lp.node.school", icon: GraduationCap, x: 50, y: 12 },
  { key: "lp.node.courses", icon: BookOpen, x: 86, y: 38 },
  { key: "lp.node.mentors", icon: Users, x: 72, y: 82 },
  { key: "lp.node.schemes", icon: Landmark, x: 28, y: 82 },
  { key: "lp.node.employers", icon: Briefcase, x: 14, y: 38 },
];

function ConnectVisual() {
  const { t } = useLang();
  return (
    <div className="relative mx-auto aspect-square w-full max-w-[540px]">
      <svg viewBox="0 0 100 100" className="absolute inset-0 size-full" aria-hidden="true">
        {NODES.map((n, i) => (
          <line
            key={n.key}
            x1="50"
            y1="50"
            x2={n.x}
            y2={n.y}
            stroke="#1d4ed8"
            strokeOpacity="0.45"
            strokeWidth="0.55"
            strokeLinecap="round"
            strokeDasharray="1.4 1.6"
            className="draw"
            style={{ "--len": 60, "--d": `${700 + i * 160}ms` } as CSSProperties}
          />
        ))}
      </svg>
      {NODES.map(({ key, icon: Icon, x, y }, i) => (
        <div
          key={key}
          className="pop absolute flex -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-2"
          style={{ left: `${x}%`, top: `${y}%`, "--d": `${i * 120}ms` } as CSSProperties}
        >
          <span className="float grid size-[68px] place-items-center rounded-2xl border border-line bg-white text-accent shadow-(--shadow-lift)" style={{ "--d": `${i * 700}ms` } as CSSProperties}>
            <Icon className="size-8" aria-hidden="true" />
          </span>
          <span className="rounded-full bg-white/90 px-3 py-1 text-base font-semibold whitespace-nowrap shadow-(--shadow-soft)">{t(key)}</span>
        </div>
      ))}
      <div className="pop absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" style={{ "--d": "1500ms" } as CSSProperties}>
        <span className="ring absolute inset-0 rounded-full bg-accent/30" />
        <span className="relative grid size-[92px] place-items-center rounded-full bg-accent text-xl font-bold tracking-wide text-white shadow-(--shadow-lift)">KHOJ</span>
      </div>
    </div>
  );
}

export function Problem() {
  const { t } = useLang();
  return (
    <section className="py-28">
      <div className={cx(WRAP, "grid items-center gap-16 lg:grid-cols-[1fr_1fr]")}>
        <Reveal className="flex flex-col gap-7">
          <SectionTitle>
            <Lines text={t("lp.problem.title")} />
          </SectionTitle>
          <p className="max-w-[34rem] text-xl leading-relaxed text-pretty text-muted">{t("lp.problem.body")}</p>
        </Reveal>
        <WhenSeen minHeight={420}>
          <ConnectVisual />
        </WhenSeen>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// The journey: a line that draws itself down the page as the visitor scrolls
// ---------------------------------------------------------------------------

const STEPS: { n: 1 | 2 | 3 | 4 | 5; Screen: () => ReactNode }[] = [
  { n: 1, Screen: SpeakScreen },
  { n: 2, Screen: PathsScreen },
  { n: 3, Screen: MentorScreen },
  { n: 4, Screen: ReviewScreen },
  { n: 5, Screen: JobsScreen },
];

export function Journey() {
  const { t } = useLang();
  const [ref, progress] = useScrollProgress<HTMLDivElement>();
  return (
    <section id="how" className="scroll-mt-20 bg-bg py-28">
      <div className={WRAP}>
        <Reveal className="max-w-[44rem]">
          <SectionTitle>{t("lp.how.title")}</SectionTitle>
        </Reveal>

        <div ref={ref} className="relative mt-20">
          <div className="absolute top-8 bottom-8 left-[27px] w-[3px] rounded-full bg-line-strong" aria-hidden="true">
            <div className="w-full rounded-full bg-accent" style={{ height: `${progress * 100}%` }} />
          </div>

          <ol className="flex flex-col gap-24">
            {STEPS.map(({ n, Screen }, i) => {
              const reached = progress * STEPS.length >= i + 0.12;
              return (
                <li key={n} className="relative grid items-center gap-x-10 gap-y-8 lg:grid-cols-[56px_minmax(0,0.85fr)_minmax(0,1.2fr)]">
                  <span
                    className={cx(
                      "relative z-10 grid size-14 place-items-center rounded-full border-[3px] text-xl font-bold transition-colors duration-500",
                      reached ? "border-accent bg-accent text-white" : "border-line-strong bg-white text-muted",
                    )}
                  >
                    {n}
                  </span>
                  <Reveal variant="left" className="flex flex-col gap-4">
                    <h3 className="text-[34px] leading-tight font-bold tracking-tight">{t(`lp.how.s${n}.t` as MessageKey)}</h3>
                    <p className="max-w-[28rem] text-xl leading-relaxed text-pretty text-muted">{t(`lp.how.s${n}.d` as MessageKey)}</p>
                  </Reveal>
                  <Reveal variant="scale" delay={120}>
                    <div className="h-[440px] overflow-hidden rounded-3xl border border-line bg-white shadow-[0_24px_60px_-28px_rgb(29_78_216/0.4)]">
                      <WhenSeen className="h-full">
                        <Screen />
                      </WhenSeen>
                    </div>
                  </Reveal>
                </li>
              );
            })}
          </ol>
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Five rungs, drawn as a staircase, and the careers that climb them
// ---------------------------------------------------------------------------

const STAIRS: { key: MessageKey; fill: string; ink: string; height: number }[] = [
  { key: "lp.rung1", fill: "#dce6ff", ink: "#0b2a6f", height: 150 },
  { key: "lp.rung2", fill: "#b6cbff", ink: "#0b2a6f", height: 210 },
  { key: "lp.rung3", fill: "#7ba0f6", ink: "#0b1220", height: 270 },
  { key: "lp.rung4", fill: "#3566df", ink: "#ffffff", height: 330 },
  { key: "lp.rung5", fill: "#0b2a6f", ink: "#ffffff", height: 390 },
];

const CAREERS: { key: MessageKey; icon: LucideIcon }[] = [
  { key: "lp.career.tailoring", icon: Scissors },
  { key: "lp.career.accounting", icon: Calculator },
  { key: "lp.career.dairy", icon: Milk },
  { key: "lp.career.content", icon: Clapperboard },
  { key: "lp.career.electrician", icon: Zap },
  { key: "lp.career.pump", icon: Cog },
  { key: "lp.career.mobile", icon: Smartphone },
];

function CareerChips() {
  const { t } = useLang();
  return (
    <div className="flex shrink-0 gap-4 pr-4">
      {CAREERS.map(({ key, icon: Icon }) => (
        <span key={key} className="inline-flex h-16 items-center gap-3.5 rounded-2xl border border-line bg-white px-6 text-lg font-semibold whitespace-nowrap shadow-(--shadow-soft)">
          <span className="grid size-10 place-items-center rounded-xl bg-tint text-accent" aria-hidden="true">
            <Icon className="size-5" />
          </span>
          {t(key)}
        </span>
      ))}
    </div>
  );
}

export function Careers() {
  const { t } = useLang();
  return (
    <section className="overflow-hidden py-28">
      <div className={cx(WRAP, "grid items-end gap-16 lg:grid-cols-[1fr_1.15fr]")}>
        <Reveal className="flex flex-col gap-7 pb-4">
          <SectionTitle>{t("lp.careers.title")}</SectionTitle>
          <p className="max-w-[32rem] text-xl leading-relaxed text-pretty text-muted">{t("lp.careers.body")}</p>
        </Reveal>
        <WhenSeen minHeight={400}>
          <ol className="flex items-end gap-3">
            {STAIRS.map(({ key, fill, ink, height }, i) => (
              <li
                key={key}
                className="grow-up flex min-w-0 flex-1 flex-col justify-end rounded-t-2xl p-4 pb-5"
                style={{ height, background: fill, color: ink, "--d": `${i * 130}ms` } as CSSProperties}
              >
                <span className="text-[44px] leading-none font-bold tracking-tight">{i + 1}</span>
                <span className="mt-2 text-[17px] leading-snug font-semibold text-balance">{t(key)}</span>
              </li>
            ))}
          </ol>
        </WhenSeen>
      </div>

      <div className="mt-20">
        <div className="overflow-hidden [mask-image:linear-gradient(90deg,transparent,#000_8%,#000_92%,transparent)]">
          <div className="marquee">
            <CareerChips />
            <CareerChips />
          </div>
        </div>
        <p className="mt-6 text-center text-base font-medium text-muted">{t("lp.careers.more")}</p>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Voice and languages
// ---------------------------------------------------------------------------

export function Voice() {
  const { t } = useLang();
  const active = useLanguageCycle();
  const points: MessageKey[] = ["lp.voice.p1", "lp.voice.p2", "lp.voice.p3", "lp.voice.p4"];
  return (
    <section className="relative overflow-hidden bg-deep py-28 text-white">
      <div
        aria-hidden="true"
        className="absolute inset-0"
        style={{ backgroundImage: "radial-gradient(rgb(255 255 255 / 0.07) 1px, transparent 1px)", backgroundSize: "28px 28px" }}
      />
      <div aria-hidden="true" className="drift absolute -right-32 -bottom-40 size-[520px] rounded-full bg-accent/40 blur-3xl" />
      <div className={cx(WRAP, "relative grid items-center gap-16 lg:grid-cols-[1.05fr_1fr]")}>
        <Reveal className="flex flex-col gap-8">
          <SectionTitle>{t("lp.voice.title")}</SectionTitle>
          <p className="max-w-[34rem] text-xl leading-relaxed text-pretty text-[#dce6ff]">{t("lp.voice.body")}</p>
          <ul className="flex flex-col gap-4">
            {points.map((k, i) => (
              <Reveal as="li" key={k} delay={i * 90} className="flex items-center gap-4 text-xl font-medium">
                <span className="grid size-8 shrink-0 place-items-center rounded-full bg-white text-deep" aria-hidden="true">
                  <Check className="size-[18px]" strokeWidth={3} />
                </span>
                {t(k)}
              </Reveal>
            ))}
          </ul>
        </Reveal>

        <Reveal variant="scale" delay={150}>
          <div className="rounded-[32px] border border-white/15 bg-white/[0.07] p-8 shadow-[0_30px_80px_-30px_rgb(0_0_0/0.6)]">
            <div className="flex gap-2.5" role="presentation">
              {CYCLE.map((code) => {
                const meta = LANGS.find((l) => l.code === code)!;
                return (
                  <span
                    key={code}
                    lang={code}
                    className={cx(
                      "rounded-xl px-4 py-2 text-base font-semibold transition-colors duration-500",
                      active === code ? "bg-white text-deep" : "bg-white/10 text-[#dce6ff]",
                    )}
                  >
                    {meta.label}
                  </span>
                );
              })}
            </div>
            <p key={active} lang={active} className="cross-fade mt-9 min-h-[190px] text-[clamp(30px,3.4vw,44px)] leading-[1.25] font-bold tracking-tight text-balance">
              {translate(active, "app.tagline")}
            </p>
            <div className="mt-6 flex items-center gap-6">
              <span className="relative grid size-16 shrink-0 place-items-center rounded-full bg-white text-deep" aria-hidden="true">
                <span className="ring absolute inset-0 rounded-full bg-white/40" />
                <Mic className="relative size-7" />
              </span>
              <Waveform tone="white" className="h-14 grow" count={18} />
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Who it is for
// ---------------------------------------------------------------------------

type Audience = "student" | "teacher" | "org";

const AUDIENCES: {
  id: Audience;
  tab: MessageKey;
  lead: MessageKey;
  items: MessageKey[];
  cta?: MessageKey;
  icon: LucideIcon;
  orbit: LucideIcon[];
}[] = [
  {
    id: "student",
    tab: "lp.who.tab.student",
    lead: "lp.who.student.lead",
    items: ["lp.who.student.1", "lp.who.student.2", "lp.who.student.3", "lp.who.student.4", "lp.who.student.5"],
    cta: "lp.who.student.cta",
    icon: GraduationCap,
    orbit: [Mic, Compass, Briefcase],
  },
  {
    id: "teacher",
    tab: "lp.who.tab.teacher",
    lead: "lp.who.teacher.lead",
    items: ["lp.who.teacher.1", "lp.who.teacher.2", "lp.who.teacher.3", "lp.who.teacher.4", "lp.who.teacher.5"],
    cta: "lp.who.teacher.cta",
    icon: Users,
    orbit: [ClipboardCheck, UserCheck, Wallet],
  },
  {
    id: "org",
    tab: "lp.who.tab.org",
    lead: "lp.who.org.lead",
    items: ["lp.who.org.1", "lp.who.org.2", "lp.who.org.3", "lp.who.org.4", "lp.who.org.5"],
    icon: Building2,
    orbit: [BarChart3, ShieldCheck, Landmark],
  },
];

export function Who() {
  const { t } = useLang();
  const [tab, setTab] = useState<Audience>("student");
  const current = AUDIENCES.find((a) => a.id === tab)!;
  const Icon = current.icon;
  const ORBIT_POS = ["top-[10%] left-[10%]", "top-[14%] right-[10%]", "bottom-[12%] left-[22%]"];

  return (
    <section id="who" className="scroll-mt-20 py-28">
      <div className={WRAP}>
        <Reveal className="flex flex-col items-start justify-between gap-8 lg:flex-row lg:items-end">
          <SectionTitle className="max-w-[36rem]">{t("lp.who.title")}</SectionTitle>
          <div role="tablist" aria-label={t("lp.who.title")} className="flex flex-wrap gap-1.5 rounded-2xl border border-line bg-white p-1.5 shadow-(--shadow-soft)">
            {AUDIENCES.map((a) => (
              <button
                key={a.id}
                type="button"
                role="tab"
                aria-selected={tab === a.id}
                onClick={() => setTab(a.id)}
                className={cx(
                  "h-14 rounded-xl px-6 text-lg font-semibold transition-colors",
                  tab === a.id ? "bg-ink text-white" : "text-muted hover:bg-tint hover:text-accent",
                )}
              >
                {t(a.tab)}
              </button>
            ))}
          </div>
        </Reveal>

        <div key={tab} role="tabpanel" className="tour-screen mt-14 grid items-center gap-14 lg:grid-cols-[1.1fr_1fr]">
          <div className="flex flex-col gap-8">
            <p className="max-w-[34rem] text-2xl leading-snug font-semibold text-balance">{t(current.lead)}</p>
            <ul className="flex flex-col gap-4">
              {current.items.map((k, i) => (
                <li key={k} className="pop flex items-start gap-4 text-xl" style={{ "--d": `${i * 70}ms` } as CSSProperties}>
                  <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-full bg-tint text-accent" aria-hidden="true">
                    <Check className="size-[18px]" strokeWidth={3} />
                  </span>
                  {t(k)}
                </li>
              ))}
            </ul>
            {current.cta && (
              <div>
                <CtaLink>{t(current.cta)}</CtaLink>
              </div>
            )}
          </div>

          <div className="relative aspect-[5/4] overflow-hidden rounded-[32px] bg-tint" aria-hidden="true">
            {[0, 900, 1800].map((d, i) => (
              <span
                key={d}
                className="ring absolute top-1/2 left-1/2 -ml-24 -mt-24 size-48 rounded-full border-2 border-accent/30"
                style={{ "--d": `${d}ms`, scale: 1 + i * 0.1 } as CSSProperties}
              />
            ))}
            <span className="absolute top-1/2 left-1/2 grid size-32 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-[36px] bg-accent text-white shadow-[0_24px_50px_-16px_rgb(29_78_216/0.7)]">
              <Icon className="size-16" />
            </span>
            {current.orbit.map((O, i) => (
              <span
                key={i}
                className={cx("float absolute grid size-16 place-items-center rounded-2xl bg-white text-accent shadow-(--shadow-lift)", ORBIT_POS[i])}
                style={{ "--d": `${i * 900}ms` } as CSSProperties}
              >
                <O className="size-8" />
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Trust: a promise, and how it is kept
// ---------------------------------------------------------------------------

const TRUST: { n: 1 | 2 | 3 | 4 | 5 | 6; icon: LucideIcon }[] = [
  { n: 1, icon: Scale },
  { n: 2, icon: FileSearch },
  { n: 3, icon: UserCheck },
  { n: 4, icon: ShieldAlert },
  { n: 5, icon: Lock },
  { n: 6, icon: Tag },
];

export function Trust() {
  const { t } = useLang();
  return (
    <section id="trust" className="scroll-mt-20 bg-bg py-28">
      <div className={cx(WRAP, "grid gap-16 lg:grid-cols-[0.85fr_1.4fr]")}>
        <Reveal className="flex flex-col gap-6 self-start lg:sticky lg:top-28">
          <SectionTitle>
            <Lines text={t("lp.trust.title")} />
          </SectionTitle>
          <p className="max-w-[26rem] text-xl leading-relaxed text-pretty text-muted">{t("lp.trust.sub")}</p>
        </Reveal>
        <ul className="divide-y divide-line-strong/60 border-y border-line-strong/60">
          {TRUST.map(({ n, icon: Icon }, i) => (
            <Reveal as="li" key={n} delay={i * 70}>
              <div className="group grid gap-x-8 gap-y-2 py-8 transition-colors md:grid-cols-[minmax(0,0.9fr)_minmax(0,1.3fr)]">
                <div className="flex items-center gap-4">
                  <span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-white text-accent shadow-(--shadow-soft) transition-colors group-hover:bg-accent group-hover:text-white" aria-hidden="true">
                    <Icon className="size-6" />
                  </span>
                  <h3 className="text-[22px] leading-snug font-bold tracking-tight">{t(`lp.trust.${n}.t` as MessageKey)}</h3>
                </div>
                <p className="text-lg leading-relaxed text-pretty text-muted">{t(`lp.trust.${n}.d` as MessageKey)}</p>
              </div>
            </Reveal>
          ))}
        </ul>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// The three honest answers of the rules engine
// ---------------------------------------------------------------------------

export function Rules() {
  const { t } = useLang();
  const rows: { icon: LucideIcon; title: string; body: MessageKey; tone: string }[] = [
    { icon: CheckCircle2, title: t("lp.mock.eligible"), body: "lp.rules.eligible.d", tone: "bg-ok-bg text-ok" },
    { icon: XCircle, title: t("lp.rules.not.t"), body: "lp.rules.not.d", tone: "bg-bad-bg text-bad" },
    { icon: HelpCircle, title: t("lp.mock.checkOffice"), body: "lp.rules.office.d", tone: "bg-warn-bg text-warn" },
  ];
  return (
    <section className="py-28">
      <div className={cx(WRAP, "grid items-center gap-16 lg:grid-cols-2")}>
        <Reveal className="flex flex-col gap-7">
          <SectionTitle>{t("lp.rules.title")}</SectionTitle>
          <p className="max-w-[32rem] text-xl leading-relaxed text-pretty text-muted">{t("lp.rules.body")}</p>
        </Reveal>
        <WhenSeen minHeight={380}>
          <div className="flex flex-col gap-4 rounded-[32px] border border-line bg-white p-5 shadow-[0_30px_70px_-34px_rgb(29_78_216/0.45)]">
            {rows.map(({ icon: Icon, title, body, tone }, i) => (
              <div key={title} className="pop flex items-start gap-5 rounded-2xl bg-bg p-5" style={{ "--d": `${i * 260}ms` } as CSSProperties}>
                <span className={cx("grid size-14 shrink-0 place-items-center rounded-2xl", tone)} aria-hidden="true">
                  <Icon className="size-7" />
                </span>
                <div className="flex flex-col gap-1">
                  <h3 className="text-[22px] font-bold tracking-tight">{title}</h3>
                  <p className="text-lg leading-relaxed text-pretty text-muted">{t(body)}</p>
                </div>
              </div>
            ))}
          </div>
        </WhenSeen>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// FAQ
// ---------------------------------------------------------------------------

function FaqItem({ n, open, onToggle }: { n: number; open: boolean; onToggle: () => void }) {
  const { t } = useLang();
  const q = t(`lp.faq.${n}.q` as MessageKey);
  const a = t(`lp.faq.${n}.a` as MessageKey);
  return (
    <div className="border-b border-line-strong/60">
      <h3>
        <button
          type="button"
          aria-expanded={open}
          aria-controls={`faq-${n}`}
          onClick={onToggle}
          className="flex min-h-20 w-full items-center justify-between gap-6 py-5 text-left text-[22px] leading-snug font-semibold transition-colors hover:text-accent"
        >
          {q}
          <span className={cx("grid size-10 shrink-0 place-items-center rounded-full transition-colors", open ? "bg-accent text-white" : "bg-tint text-accent")} aria-hidden="true">
            <Plus className={cx("size-5 transition-transform duration-300", open && "rotate-45")} />
          </span>
        </button>
      </h3>
      <div id={`faq-${n}`} role="region" className={cx("grid transition-[grid-template-rows] duration-500 ease-(--ease-out-expo)", open ? "grid-rows-[1fr]" : "grid-rows-[0fr]")}>
        <div className="overflow-hidden">
          <p className="max-w-[40rem] pb-7 text-xl leading-relaxed text-pretty text-muted">{a}</p>
        </div>
      </div>
    </div>
  );
}

export function Faq() {
  const { t } = useLang();
  const [open, setOpen] = useState<number | null>(1);
  return (
    <section id="faq" className="scroll-mt-20 bg-bg py-28">
      <div className={cx(WRAP, "grid gap-16 lg:grid-cols-[0.85fr_1.4fr]")}>
        <Reveal className="self-start lg:sticky lg:top-28">
          <SectionTitle>{t("lp.faq.title")}</SectionTitle>
        </Reveal>
        <Reveal className="border-t border-line-strong/60">
          {[1, 2, 3, 4, 5, 6, 7].map((n) => (
            <FaqItem key={n} n={n} open={open === n} onToggle={() => setOpen(open === n ? null : n)} />
          ))}
        </Reveal>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Closing call to action and footer
// ---------------------------------------------------------------------------

export function FinalCta() {
  const { t } = useLang();
  return (
    <section className="relative overflow-hidden bg-deep py-32 text-center text-white">
      <div
        aria-hidden="true"
        className="absolute inset-0"
        style={{ backgroundImage: "radial-gradient(rgb(255 255 255 / 0.07) 1px, transparent 1px)", backgroundSize: "28px 28px" }}
      />
      <div aria-hidden="true" className="drift absolute -top-40 left-[10%] size-[480px] rounded-full bg-accent/45 blur-3xl" />
      <div className={cx(WRAP, "relative flex flex-col items-center gap-8")}>
        <Waveform tone="white" className="h-16 w-full max-w-[420px] opacity-90" count={22} />
        <Reveal className="flex flex-col items-center gap-6">
          <SectionTitle className="max-w-[18ch]">{t("lp.final.title")}</SectionTitle>
          <p className="max-w-[34rem] text-xl leading-relaxed text-pretty text-[#dce6ff]">{t("lp.final.body")}</p>
        </Reveal>
        <Reveal delay={150}>
          <CtaLink tone="light">{t("lp.cta.start.free")}</CtaLink>
        </Reveal>
      </div>
    </section>
  );
}

export function Footer() {
  const { t } = useLang();
  const { user } = useSession();
  const links: { href: string; label: MessageKey }[] = [
    { href: "#how", label: "lp.nav.how" },
    { href: "#who", label: "lp.nav.who" },
    { href: "#trust", label: "lp.nav.trust" },
    { href: "#faq", label: "lp.nav.faq" },
  ];
  return (
    <footer className="border-t border-line bg-white py-14">
      <div className={cx(WRAP, "flex flex-col gap-10 md:flex-row md:items-start md:justify-between")}>
        <div className="flex max-w-sm flex-col gap-4">
          <Logo />
          <p className="text-lg font-medium text-ink">{t("app.tagline")}</p>
          <p className="text-base text-muted">{t("app.expansion")}</p>
        </div>
        <nav aria-label={t("nav.main")} className="flex flex-wrap gap-x-8 gap-y-3 text-lg font-semibold">
          {links.map(({ href, label }) => (
            <a key={href} href={href} className="text-muted transition-colors hover:text-accent">
              {t(label)}
            </a>
          ))}
          <Link to={entryPath(user)} className="text-muted transition-colors hover:text-accent">
            {user ? t("lp.nav.open") : t("lp.nav.signin")}
          </Link>
        </nav>
      </div>
      <p className={cx(WRAP, "mt-10 text-base text-muted")}>{t("lp.footer.note")}</p>
    </footer>
  );
}
