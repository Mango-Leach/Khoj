import type { CSSProperties } from "react";
import { BadgeCheck, Calculator, Check, Landmark, Mic, Milk, Pencil, Scissors, Smartphone, Store, Users, Wrench } from "lucide-react";
import { cx } from "../../components/ui";
import { useLang, type MessageKey } from "../../lib/i18n";
import { useTypewriter } from "./hooks";

/**
 * Small, honest sketches of the real KHOJ screens. They show how the product works; they
 * carry no figures, names or results, because nothing on this page is data.
 */

const BAR_HEIGHTS = [38, 62, 46, 84, 56, 100, 42, 76, 52, 92, 40, 68, 58, 88, 44, 72, 50, 96, 46, 64, 54, 80, 42, 70];

export function Waveform({ className, tone = "accent", count = BAR_HEIGHTS.length }: { className?: string; tone?: "accent" | "white"; count?: number }) {
  return (
    <div className={cx("flex items-center justify-center gap-[5px]", className)} aria-hidden="true">
      {BAR_HEIGHTS.slice(0, count).map((h, i) => (
        <span
          key={i}
          className={cx("wave-bar w-[5px] rounded-full", tone === "accent" ? "bg-accent" : "bg-white/85")}
          style={{ height: `${h}%`, "--d": `${(i * 83) % 1100}ms` } as CSSProperties}
        />
      ))}
    </div>
  );
}

function Chip({ tone, children }: { tone: "ok" | "warn" | "tint"; children: React.ReactNode }) {
  return (
    <span
      className={cx(
        "inline-flex items-center rounded-full px-3 py-1 text-sm font-semibold whitespace-nowrap",
        tone === "ok" && "bg-ok-bg text-ok",
        tone === "warn" && "bg-warn-bg text-warn",
        tone === "tint" && "bg-tint text-deep",
      )}
    >
      {children}
    </span>
  );
}

// ---------------------------------------------------------------------------
// 1. Speak
// ---------------------------------------------------------------------------

export function SpeakScreen() {
  const { t } = useLang();
  const text = t("lp.mock.said");
  const { shown, done } = useTypewriter(text, true, 46);
  return (
    <div className="grid h-full grid-cols-[auto_minmax(0,1fr)] items-center gap-10 px-10 py-8">
      <div className="relative grid size-36 shrink-0 place-items-center" aria-hidden="true">
        {[0, 800, 1600].map((d) => (
          <span key={d} className="ring absolute inset-3 rounded-full bg-accent/25" style={{ "--d": `${d}ms` } as CSSProperties} />
        ))}
        <span className="relative grid size-24 place-items-center rounded-full bg-accent text-white shadow-(--shadow-lift)">
          <Mic className="size-10" />
        </span>
      </div>
      <div className="flex min-w-0 flex-col gap-4">
        <p className="text-base font-semibold text-muted">{t("lp.mock.ask")}</p>
        <Waveform className="h-12" count={20} />
        <p className="min-h-[4.5rem] text-[28px] leading-snug font-semibold text-ink">
          “{shown}
          {!done && <span className="ml-0.5 inline-block h-7 w-[3px] translate-y-1 animate-pulse bg-accent" />}”
        </p>
        <div className="flex h-12 items-center gap-3">
          {done && (
            <>
              <span className="pop text-base font-medium text-muted">{t("lp.mock.right")}</span>
              <span className="pop inline-flex h-11 items-center rounded-xl bg-accent px-6 text-base font-semibold text-white" style={{ "--d": "120ms" } as CSSProperties}>
                {t("lp.mock.yes")}
              </span>
              <span className="pop inline-flex h-11 items-center gap-2 rounded-xl border-[1.5px] border-line-strong px-5 text-base font-semibold" style={{ "--d": "220ms" } as CSSProperties}>
                <Pencil className="size-4" aria-hidden="true" />
                {t("lp.mock.edit")}
              </span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 2. Paths and the five-rung ladder
// ---------------------------------------------------------------------------

const PATH_ROWS: { key: MessageKey; icon: typeof Scissors; demand: 1 | 2 | 3 }[] = [
  { key: "lp.career.tailoring", icon: Scissors, demand: 3 },
  { key: "lp.career.accounting", icon: Calculator, demand: 2 },
  { key: "lp.career.mobile", icon: Smartphone, demand: 3 },
  { key: "lp.career.dairy", icon: Milk, demand: 2 },
];
const RUNGS: MessageKey[] = ["lp.rung1", "lp.rung2", "lp.rung3", "lp.rung4", "lp.rung5"];

function Meter({ level }: { level: 1 | 2 | 3 }) {
  return (
    <span className="inline-flex items-center gap-[3px]" aria-hidden="true">
      {[1, 2, 3].map((i) => (
        <i key={i} className={cx("h-4 w-2 rounded-[2px]", i <= level ? "bg-deep" : "border-[1.5px] border-line-strong bg-white")} />
      ))}
    </span>
  );
}

export function PathsScreen() {
  const { t } = useLang();
  return (
    <div className="grid h-full grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)] gap-5 p-7">
      <div className="flex min-w-0 flex-col gap-2.5">
        <p className="text-base font-semibold text-muted">{t("lp.mock.pathsTitle")}</p>
        {PATH_ROWS.map(({ key, icon: Icon, demand }, i) => (
          <div
            key={key}
            className={cx(
              "pop flex items-center gap-3.5 rounded-2xl border-[1.5px] px-4 py-3",
              i === 0 ? "border-accent bg-tint" : "border-line bg-white",
            )}
            style={{ "--d": `${i * 130}ms` } as CSSProperties}
          >
            <span className={cx("grid size-11 shrink-0 place-items-center rounded-xl", i === 0 ? "bg-accent text-white" : "bg-tint text-accent")} aria-hidden="true">
              <Icon className="size-5" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-base leading-snug font-semibold">{t(key)}</span>
              {i === 0 && (
                <span className="mt-0.5 block text-sm leading-snug text-muted">
                  {t("lp.mock.firstIncome")}: {t("lp.mock.tailoringFirst")}
                </span>
              )}
            </span>
            <Meter level={demand} />
          </div>
        ))}
      </div>
      <div className="relative flex flex-col justify-center gap-3 rounded-2xl bg-bg px-6 py-4">
        <span className="absolute top-9 bottom-9 left-[38px] w-[3px] rounded-full bg-line-strong" aria-hidden="true" />
        {RUNGS.map((key, i) => (
          <div key={key} className="pop relative flex items-center gap-4" style={{ "--d": `${450 + i * 200}ms` } as CSSProperties}>
            <span
              className={cx(
                "relative z-10 grid size-8 place-items-center rounded-full border-[3px] text-sm font-bold",
                i === 0 ? "border-accent bg-accent text-white" : "border-line-strong bg-white text-muted",
              )}
            >
              {i + 1}
            </span>
            <span className={cx("text-base", i === 0 ? "font-semibold text-ink" : "font-medium text-muted")}>{t(key)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 3. Mentor
// ---------------------------------------------------------------------------

const MENTORS: { role: MessageKey; chosen: boolean }[] = [
  { role: "teacherRole.mentor", chosen: false },
  { role: "teacherRole.expert", chosen: true },
  { role: "teacherRole.teacher", chosen: false },
];

export function MentorScreen() {
  const { t } = useLang();
  return (
    <div className="flex h-full flex-col gap-3 p-7">
      <p className="text-base font-semibold text-muted">{t("lp.mock.mentorTitle")}</p>
      {MENTORS.map(({ role, chosen }, i) => (
        <div
          key={role}
          className={cx("pop flex items-center gap-4 rounded-2xl border-[1.5px] px-5 py-3.5", chosen ? "border-accent bg-tint" : "border-line bg-white")}
          style={{ "--d": `${i * 160}ms` } as CSSProperties}
        >
          <span className={cx("grid size-12 shrink-0 place-items-center rounded-full", chosen ? "bg-accent text-white" : "bg-tint text-accent")} aria-hidden="true">
            <Users className="size-6" />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block text-lg font-semibold">{t(role)}</span>
            <span className="mt-1.5 flex flex-wrap gap-2">
              <Chip tone="ok">
                <BadgeCheck className="mr-1.5 size-4" aria-hidden="true" />
                {t("lp.mock.verified")}
              </Chip>
              <Chip tone="tint">{chosen ? t("lp.mock.sameBlock") : t("lp.mock.sameLang")}</Chip>
            </span>
          </span>
          {chosen && (
            <span className="pop inline-flex h-11 items-center rounded-xl bg-accent px-5 text-base font-semibold text-white" style={{ "--d": "700ms" } as CSSProperties}>
              {t("lp.mock.request")}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// 4. Review: a photo of practical work, a rubric, a mentor's decision
// ---------------------------------------------------------------------------

export function ReviewScreen() {
  const { t } = useLang();
  const criteria: MessageKey[] = ["lp.mock.c1", "lp.mock.c2", "lp.mock.c3"];
  return (
    <div className="grid h-full grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] gap-6 p-7">
      <figure className="flex min-w-0 flex-col gap-2.5">
        <div className="relative grow overflow-hidden rounded-2xl bg-tint-strong">
          <svg viewBox="0 0 320 220" className="size-full" role="img" aria-label={t("lp.mock.assignment")}>
            <defs>
              <pattern id="weave" width="8" height="8" patternUnits="userSpaceOnUse">
                <path d="M0 4h8M4 0v8" stroke="#1d4ed8" strokeOpacity="0.1" strokeWidth="1" />
              </pattern>
            </defs>
            <rect width="320" height="220" fill="#dce6ff" />
            <path d="M30 40 L290 28 L296 112 L24 118 Z" fill="#ffffff" />
            <path d="M30 40 L290 28 L296 112 L24 118 Z" fill="url(#weave)" />
            <path d="M24 118 L296 112 L292 196 L34 204 Z" fill="#c9d8ff" />
            <path d="M24 118 L296 112 L292 196 L34 204 Z" fill="url(#weave)" />
            <path className="stitch" d="M24 116 L296 110" stroke="#0b2a6f" strokeWidth="3" strokeLinecap="round" fill="none" />
          </svg>
        </div>
        <figcaption className="text-base font-semibold">{t("lp.mock.assignment")}</figcaption>
      </figure>
      <div className="flex min-w-0 flex-col justify-center gap-3">
        {criteria.map((key, i) => (
          <div key={key} className="pop flex items-center gap-3.5 rounded-2xl border border-line bg-white px-4 py-3.5" style={{ "--d": `${500 + i * 650}ms` } as CSSProperties}>
            <span className="grid size-8 shrink-0 place-items-center rounded-full bg-ok text-white" aria-hidden="true">
              <Check className="size-[18px]" strokeWidth={3} />
            </span>
            <span className="text-base font-semibold">{t(key)}</span>
          </div>
        ))}
        <div className="pop flex items-center gap-3 rounded-2xl bg-ok-bg px-4 py-3.5 text-ok" style={{ "--d": "2700ms" } as CSSProperties}>
          <BadgeCheck className="size-6 shrink-0" aria-hidden="true" />
          <span className="text-base font-semibold">{t("lp.mock.approved")}</span>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 5. Opportunities with rule checks
// ---------------------------------------------------------------------------

const JOBS: { key: MessageKey; icon: typeof Wrench; ok: boolean }[] = [
  { key: "lp.mock.apprentice", icon: Wrench, ok: true },
  { key: "lp.mock.training", icon: Landmark, ok: true },
  { key: "lp.mock.local", icon: Store, ok: false },
];

export function JobsScreen() {
  const { t } = useLang();
  return (
    <div className="flex h-full flex-col gap-3 p-7">
      <p className="text-base font-semibold text-muted">{t("lp.mock.jobsTitle")}</p>
      {JOBS.map(({ key, icon: Icon, ok }, i) => (
        <div key={key} className="pop flex items-center gap-4 rounded-2xl border border-line bg-white px-5 py-4" style={{ "--d": `${i * 170}ms` } as CSSProperties}>
          <span className="grid size-12 shrink-0 place-items-center rounded-xl bg-tint text-accent" aria-hidden="true">
            <Icon className="size-6" />
          </span>
          <span className="min-w-0 flex-1 text-lg font-semibold">{t(key)}</span>
          <Chip tone={ok ? "ok" : "warn"}>{ok ? t("lp.mock.eligible") : t("lp.mock.checkOffice")}</Chip>
        </div>
      ))}
    </div>
  );
}

