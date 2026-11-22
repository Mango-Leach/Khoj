import { useState, type CSSProperties, type ReactNode } from "react";
import {
  ArrowUpRight,
  BarChart3,
  Briefcase,
  Calculator,
  Check,
  ClipboardCheck,
  Clapperboard,
  Cog,
  Compass,
  FileSearch,
  Landmark,
  Lock,
  Mic,
  Milk,
  Scale,
  Scissors,
  ShieldAlert,
  ShieldCheck,
  Smartphone,
  Tag,
  UserCheck,
  Wallet,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { Link } from "../../components/Link";
import { entryPath } from "../../lib/routes";
import { useSession } from "../../lib/session";
import { Person, type PersonName } from "../../components/People";
import { Logo, cx } from "../../components/ui";
import { LANGS, translate, useLang, type MessageKey } from "../../lib/i18n";
import { CYCLE, useLanguageCycle, useScrollProgress } from "./hooks";
import { JobsScreen, MentorScreen, PathsScreen, ReviewScreen, SpeakScreen, Waveform } from "./mocks";
import { Reveal, WhenSeen } from "./Reveal";

const WRAP = "mx-auto w-full max-w-[1540px] px-[clamp(20px,3vw,56px)]";

function SectionTitle({ children, id, className }: { children: ReactNode; id?: string; className?: string }) {
  return (
    <h2 id={id} className={cx("text-[clamp(28px,3.9vw,54px)] leading-[1.08] font-bold tracking-[-0.025em] text-balance", className)}>
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

/** A pill with a round arrow. "dark" for light backgrounds, "lime" for the blue ones. */
function CtaLink({ children, tone = "dark", to }: { children: ReactNode; tone?: "dark" | "lime"; to?: string }) {
  const { user } = useSession();
  return (
    <Link
      to={to ?? entryPath(user)}
      className={cx(
        "group inline-flex h-14 items-center gap-3 rounded-full py-2 pr-2 pl-7 text-[15px] font-bold transition-colors lg:h-16 lg:text-[17px]",
        tone === "dark" ? "bg-night text-white hover:bg-black" : "bg-lime text-night hover:bg-[#e8ff5a]",
      )}
    >
      {children}
      <span
        className={cx(
          "grid size-10 place-items-center rounded-full transition-transform group-hover:translate-x-0.5 lg:size-12",
          tone === "dark" ? "bg-lime text-night" : "bg-night text-lime",
        )}
        aria-hidden="true"
      >
        <ArrowUpRight className="size-6" />
      </span>
    </Link>
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
    <section id="how" className="scroll-mt-28 py-14 sm:py-20 lg:py-24">
      <div className={WRAP}>
        <Reveal className="max-w-[44rem]">
          <SectionTitle>{t("lp.how.title")}</SectionTitle>
        </Reveal>

        <div ref={ref} className="relative mt-20">
          <div className="absolute top-8 bottom-8 left-[27px] hidden w-[3px] rounded-full bg-line-strong lg:block" aria-hidden="true">
            <div className="w-full rounded-full bg-accent" style={{ height: `${progress * 100}%` }} />
          </div>

          <ol className="flex flex-col gap-24">
            {STEPS.map(({ n, Screen }, i) => {
              const reached = progress * STEPS.length >= i + 0.12;
              return (
                <li key={n} className="relative grid grid-cols-[minmax(0,1fr)] items-center gap-x-10 gap-y-6 lg:grid-cols-[56px_minmax(0,0.85fr)_minmax(0,1.2fr)] lg:gap-y-8">
                  <span
                    className={cx(
                      "relative z-10 grid size-14 place-items-center rounded-full border-[3px] text-[16px] font-bold transition-colors duration-500",
                      reached ? "border-lime bg-lime text-night" : "border-line-strong bg-white text-muted",
                    )}
                  >
                    {n}
                  </span>
                  <Reveal variant="left" className="flex flex-col gap-4">
                    <h3 className="text-[25px] leading-tight font-bold tracking-tight sm:text-[31px]">{t(`lp.how.s${n}.t` as MessageKey)}</h3>
                    <p className="max-w-[28rem] text-[16px] leading-relaxed text-pretty text-muted">{t(`lp.how.s${n}.d` as MessageKey)}</p>
                  </Reveal>
                  <Reveal variant="scale" delay={120}>
                    <div className="min-h-[300px] overflow-hidden rounded-[32px] border border-line bg-white shadow-[0_24px_60px_-28px_rgb(36_51_166/0.4)] lg:h-[440px]">
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
  { key: "lp.rung1", fill: "#e4e7ff", ink: "#121a6e", height: 130 },
  { key: "lp.rung2", fill: "#bfc6fb", ink: "#121a6e", height: 185 },
  { key: "lp.rung3", fill: "#8591ec", ink: "#0b0d1c", height: 240 },
  { key: "lp.rung4", fill: "#2433a6", ink: "#ffffff", height: 290 },
  { key: "lp.rung5", fill: "#dcf53f", ink: "#0b0d1c", height: 340 },
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
        <span key={key} className="inline-flex h-16 items-center gap-3.5 rounded-full border border-line bg-white pr-7 pl-3 text-[15px] font-semibold whitespace-nowrap shadow-(--shadow-soft)">
          <span className="grid size-10 place-items-center rounded-full bg-lime text-night" aria-hidden="true">
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
    <section className="overflow-hidden py-14 sm:py-20 lg:py-24">
      <div className={cx(WRAP, "grid grid-cols-[minmax(0,1fr)] items-end gap-16 lg:grid-cols-[1fr_1.15fr]")}>
        <Reveal className="flex flex-col gap-7 pb-4">
          <SectionTitle>{t("lp.careers.title")}</SectionTitle>
          <p className="max-w-[32rem] text-[16px] leading-relaxed text-pretty text-muted">{t("lp.careers.body")}</p>
        </Reveal>
        <WhenSeen minHeight={400}>
          <ol className="flex flex-col gap-2.5 sm:flex-row sm:items-end sm:gap-3">
            {STAIRS.map(({ key, fill, ink, height }, i) => (
              <li
                key={key}
                className="grow-up flex w-(--w) min-w-0 flex-row items-center gap-4 rounded-[20px] p-4 sm:h-(--h) sm:w-auto sm:flex-1 sm:flex-col sm:items-start sm:justify-end sm:gap-0 sm:rounded-t-[28px] sm:rounded-b-none sm:pb-5"
                style={{ "--h": `${height}px`, "--w": `${54 + i * 11.5}%`, background: fill, color: ink, "--d": `${i * 130}ms` } as CSSProperties}
              >
                <span className="text-[29px] leading-none font-bold tracking-tight sm:text-[40px]">{i + 1}</span>
                <span className="text-[15px] leading-snug font-semibold text-balance sm:mt-2">{t(key)}</span>
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
        <p className="mt-6 text-center text-[14px] font-medium text-muted">{t("lp.careers.more")}</p>
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
    <section className="px-[clamp(12px,2vw,32px)] py-6">
      <div className="relative mx-auto max-w-[1540px] overflow-hidden rounded-[32px] bg-deep py-20 text-white sm:rounded-[48px] sm:py-28">
      <div
        aria-hidden="true"
        className="absolute inset-0"
        style={{ backgroundImage: "radial-gradient(rgb(255 255 255 / 0.07) 1px, transparent 1px)", backgroundSize: "28px 28px" }}
      />
      <div aria-hidden="true" className="drift absolute -right-32 -bottom-40 size-[520px] rounded-full bg-accent/60 blur-3xl" />
      <div className={cx(WRAP, "relative grid grid-cols-[minmax(0,1fr)] items-center gap-16 lg:grid-cols-[1.05fr_1fr]")}>
        <Reveal className="flex flex-col gap-8">
          <SectionTitle>{t("lp.voice.title")}</SectionTitle>
          <p className="max-w-[34rem] text-[16px] leading-relaxed text-pretty text-white/80">{t("lp.voice.body")}</p>
          <ul className="flex flex-col gap-4">
            {points.map((k, i) => (
              <Reveal as="li" key={k} delay={i * 90} className="flex items-center gap-4 text-[16px] font-medium">
                <span className="grid size-8 shrink-0 place-items-center rounded-full bg-lime text-night" aria-hidden="true">
                  <Check className="size-[18px]" strokeWidth={3} />
                </span>
                {t(k)}
              </Reveal>
            ))}
          </ul>
        </Reveal>

        <Reveal variant="scale" delay={150}>
          <div className="rounded-[40px] border border-white/15 bg-white/[0.07] p-8 shadow-[0_30px_80px_-30px_rgb(0_0_0/0.6)]">
            <div className="flex gap-2.5" role="presentation">
              {CYCLE.map((code) => {
                const meta = LANGS.find((l) => l.code === code)!;
                return (
                  <span
                    key={code}
                    lang={code}
                    className={cx(
                      "rounded-full px-5 py-2 text-[14px] font-semibold transition-colors duration-500",
                      active === code ? "bg-lime text-night" : "bg-white/10 text-white/80",
                    )}
                  >
                    {meta.label}
                  </span>
                );
              })}
            </div>
            <p key={active} lang={active} className="cross-fade mt-9 min-h-[160px] text-[clamp(26px,3vw,38px)] leading-[1.25] font-bold tracking-tight text-balance">
              {translate(active, "app.tagline")}
            </p>
            <div className="mt-6 flex items-center gap-6">
              <span className="relative grid size-16 shrink-0 place-items-center rounded-full bg-lime text-night" aria-hidden="true">
                <span className="ring absolute inset-0 rounded-full bg-lime/50" />
                <Mic className="relative size-7" />
              </span>
              <Waveform tone="white" className="h-14 grow" count={18} />
            </div>
          </div>
        </Reveal>
      </div>
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
  people: [PersonName, PersonName];
  orbit: LucideIcon[];
}[] = [
  {
    id: "student",
    tab: "lp.who.tab.student",
    lead: "lp.who.student.lead",
    items: ["lp.who.student.1", "lp.who.student.2", "lp.who.student.3", "lp.who.student.4", "lp.who.student.5"],
    cta: "lp.who.student.cta",
    people: ["asha", "arjun"],
    orbit: [Mic, Compass, Briefcase],
  },
  {
    id: "teacher",
    tab: "lp.who.tab.teacher",
    lead: "lp.who.teacher.lead",
    items: ["lp.who.teacher.1", "lp.who.teacher.2", "lp.who.teacher.3", "lp.who.teacher.4", "lp.who.teacher.5"],
    cta: "lp.who.teacher.cta",
    people: ["meena", "dev"],
    orbit: [ClipboardCheck, UserCheck, Wallet],
  },
  {
    id: "org",
    tab: "lp.who.tab.org",
    lead: "lp.who.org.lead",
    items: ["lp.who.org.1", "lp.who.org.2", "lp.who.org.3", "lp.who.org.4", "lp.who.org.5"],
    people: ["ravi", "kiran"],
    orbit: [BarChart3, ShieldCheck, Landmark],
  },
];

export function Who() {
  const { t } = useLang();
  const [tab, setTab] = useState<Audience>("student");
  const current = AUDIENCES.find((a) => a.id === tab)!;
  const ORBIT_POS = ["top-[8%] left-[8%]", "top-[12%] right-[8%]", "top-[40%] left-[3%]"];

  return (
    <section id="who" className="scroll-mt-28 py-14 sm:py-20 lg:py-24">
      <div className={WRAP}>
        <Reveal className="flex flex-col items-start justify-between gap-8 lg:flex-row lg:items-end">
          <SectionTitle className="max-w-[36rem]">{t("lp.who.title")}</SectionTitle>
          <div role="tablist" aria-label={t("lp.who.title")} className="flex w-full flex-col gap-1.5 rounded-[28px] border border-line bg-white p-1.5 shadow-(--shadow-soft) sm:w-auto sm:flex-row">
            {AUDIENCES.map((a) => (
              <button
                key={a.id}
                type="button"
                role="tab"
                aria-selected={tab === a.id}
                onClick={() => setTab(a.id)}
                className={cx(
                  "h-14 w-full rounded-full px-6 text-[15px] font-semibold transition-colors sm:w-auto",
                  tab === a.id ? "bg-night text-white" : "text-muted hover:bg-tint hover:text-accent",
                )}
              >
                {t(a.tab)}
              </button>
            ))}
          </div>
        </Reveal>

        <div key={tab} role="tabpanel" className="tour-screen mt-14 grid grid-cols-[minmax(0,1fr)] items-center gap-14 lg:grid-cols-[1.1fr_1fr]">
          <div className="flex flex-col gap-8">
            <p className="max-w-[34rem] text-[20px] leading-snug font-semibold text-balance">{t(current.lead)}</p>
            <ul className="flex flex-col gap-4">
              {current.items.map((k, i) => (
                <li key={k} className="pop flex items-start gap-4 text-[16px]" style={{ "--d": `${i * 70}ms` } as CSSProperties}>
                  <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-full bg-lime text-night" aria-hidden="true">
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

          <div
            className="relative aspect-[5/4] overflow-hidden rounded-[40px] bg-accent"
            style={{
              backgroundImage: "linear-gradient(rgb(255 255 255 / 0.07) 1px, transparent 1px), linear-gradient(90deg, rgb(255 255 255 / 0.07) 1px, transparent 1px)",
              backgroundSize: "48px 48px",
            }}
            aria-hidden="true"
          >
            <span className="absolute bottom-0 left-1/2 h-[82%] w-[72%] -translate-x-1/2 rounded-t-[999px] bg-deep" />
            <Person name={current.people[0]} className="absolute bottom-0 left-[14%] h-[66%] w-[40%]" />
            <Person name={current.people[1]} className="absolute right-[12%] bottom-0 h-[62%] w-[38%]" />
            {current.orbit.map((O, i) => (
              <span
                key={i}
                className={cx("float absolute grid size-14 place-items-center rounded-2xl bg-white text-accent shadow-(--shadow-lift)", ORBIT_POS[i])}
                style={{ "--d": `${i * 900}ms` } as CSSProperties}
              >
                <O className="size-7" />
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
    <section id="trust" className="scroll-mt-28 py-14 sm:py-20 lg:py-24">
      <div className={cx(WRAP, "grid grid-cols-[minmax(0,1fr)] gap-16 lg:grid-cols-[0.85fr_1.4fr]")}>
        <Reveal className="flex flex-col gap-6 self-start lg:sticky lg:top-28">
          <SectionTitle>
            <Lines text={t("lp.trust.title")} />
          </SectionTitle>
          <p className="max-w-[26rem] text-[16px] leading-relaxed text-pretty text-muted">{t("lp.trust.sub")}</p>
        </Reveal>
        <ul className="divide-y divide-line-strong/60 border-y border-line-strong/60">
          {TRUST.map(({ n, icon: Icon }, i) => (
            <Reveal as="li" key={n} delay={i * 70}>
              <div className="group grid grid-cols-[minmax(0,1fr)] gap-x-8 gap-y-2 py-8 transition-colors md:grid-cols-[minmax(0,0.9fr)_minmax(0,1.3fr)]">
                <div className="flex items-center gap-4">
                  <span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-white text-accent shadow-(--shadow-soft) transition-colors group-hover:bg-accent group-hover:text-white" aria-hidden="true">
                    <Icon className="size-6" />
                  </span>
                  <h3 className="text-[20px] leading-snug font-bold tracking-tight">{t(`lp.trust.${n}.t` as MessageKey)}</h3>
                </div>
                <p className="text-[15px] leading-relaxed text-pretty text-muted">{t(`lp.trust.${n}.d` as MessageKey)}</p>
              </div>
            </Reveal>
          ))}
        </ul>
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
    <section className="px-[clamp(12px,2vw,32px)] py-24">
      <div className="mx-auto max-w-[1540px]">
        <div className="relative grid grid-cols-[minmax(0,1fr)] overflow-hidden rounded-[32px] bg-lime text-night sm:rounded-[48px] lg:grid-cols-[1.15fr_1fr]">
          <Reveal className="relative z-10 flex flex-col items-start gap-6 p-8 sm:p-12 lg:p-16">
            <SectionTitle className="max-w-[16ch]">{t("lp.final.title")}</SectionTitle>
            <p className="max-w-[34rem] text-[16px] leading-relaxed text-pretty text-night/80 lg:text-[20px]">{t("lp.final.body")}</p>
            <CtaLink>{t("lp.cta.start.free")}</CtaLink>
          </Reveal>
          <div className="relative min-h-[300px] lg:min-h-[360px]" aria-hidden="true">
            <span className="absolute -bottom-[200px] left-1/2 size-[460px] -translate-x-1/2 rounded-full bg-accent lg:-right-[50px] lg:-bottom-[140px] lg:left-auto lg:size-[460px] lg:translate-x-0" />
            <Person name="arjun" className="absolute bottom-0 left-1/2 h-[276px] w-[230px] -translate-x-[105%] lg:right-[230px] lg:left-auto lg:h-[320px] lg:w-[268px] lg:translate-x-0" />
            <Person name="meena" className="absolute bottom-0 left-1/2 h-[276px] w-[230px] -translate-x-[5%] lg:right-[20px] lg:left-auto lg:h-[320px] lg:w-[268px] lg:translate-x-0" />
          </div>
        </div>
      </div>
    </section>
  );
}

export function Footer() {
  const { t, lang, setLang } = useLang();
  const { user } = useSession();
  const links: { href: string; label: MessageKey }[] = [
    { href: "#how", label: "lp.nav.how" },
    { href: "#who", label: "lp.nav.who" },
    { href: "#trust", label: "lp.nav.trust" },
  ];
  return (
    <footer className="px-[clamp(12px,2vw,32px)] pb-6">
      <div className="mx-auto max-w-[1540px] rounded-[26px] bg-night p-7 text-white sm:rounded-[44px] sm:p-12">
        <div className="grid grid-cols-[minmax(0,1fr)] gap-10 md:grid-cols-[1.3fr_1fr_1fr]">
          <div className="flex max-w-md flex-col items-start gap-4">
            <Logo inverse />
            <p className="text-[16px] font-semibold">{t("app.tagline")}</p>
            <p className="text-[15px] text-white/70">{t("app.expansion")}</p>
            <div className="mt-2">
              <CtaLink tone="lime">{user ? t("lp.nav.open") : t("lp.cta.start.free")}</CtaLink>
            </div>
          </div>
          <nav aria-label={t("nav.main")} className="flex flex-col gap-1 text-[17px]">
            {links.map(({ href, label }) => (
              <a key={href} href={href} className="py-1.5 text-white/85 transition-colors hover:text-lime">
                {t(label)}
              </a>
            ))}
            <Link to={entryPath(user)} className="py-1.5 text-white/85 transition-colors hover:text-lime">
              {user ? t("lp.nav.open") : t("lp.nav.signin")}
            </Link>
          </nav>
          <div>
            <p className="mb-3 text-[14px] font-bold tracking-[0.08em] text-white/55 uppercase">{t("lang.label")}</p>
            <ul className="flex flex-col gap-1 text-[17px]">
              {LANGS.map((l) => (
                <li key={l.code}>
                  <button
                    type="button"
                    lang={l.code}
                    aria-pressed={lang === l.code}
                    onClick={() => setLang(l.code)}
                    className={cx("py-1.5 text-left transition-colors hover:text-lime", lang === l.code ? "font-bold text-lime" : "text-white/85")}
                  >
                    {l.label}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>
        <p className="mt-12 border-t border-white/15 pt-6 text-[14px] text-white/60">{t("lp.footer.people")}</p>
      </div>
    </footer>
  );
}
