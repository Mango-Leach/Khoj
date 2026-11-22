import type { CSSProperties } from "react";
import { ArrowUpRight, Check, Loader2, Square, Volume2 } from "lucide-react";
import { Avatar, Person } from "../../components/People";
import { Link } from "../../components/Link";
import { translate, useLang } from "../../lib/i18n";
import { entryPath } from "../../lib/routes";
import { useSession } from "../../lib/session";
import { useSpeaker } from "../../lib/speech";
import { Waveform } from "./mocks";

/** Splits "Speak your skill. Find your first income." so the promise can carry the colour. */
function splitTagline(text: string): [string, string] {
  const m = text.match(/^(.+?[.,।])\s+(.+)$/);
  return m ? [m[1], m[2]] : [text, ""];
}

/** Named schemes and portals the product links out to. They are proper names, so they are not translated. */
const ROUTES = ["NATS", "PM Vishwakarma", "RSETI", "DDU-GKY", "SWAYAM", "NPTEL"];

const GRID = "linear-gradient(rgb(255 255 255 / 0.07) 1px, transparent 1px), linear-gradient(90deg, rgb(255 255 255 / 0.07) 1px, transparent 1px)";

/** Small line drawings that sit on the blue around the phone. Decorative only. */
function Doodles() {
  const common = { fill: "none", stroke: "currentColor", strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": true } as const;
  return (
    <div className="pointer-events-none absolute inset-0 hidden text-white/85 lg:block" aria-hidden="true">
      <svg {...common} className="absolute top-10 left-[6%]" width="48" height="48" viewBox="0 0 48 48" strokeWidth="2">
        <path d="M24 6a12 12 0 0 0-6 22.4V34h12v-5.6A12 12 0 0 0 24 6ZM19 40h10M21 44h6M24 0v2M6 12l2 1M42 12l-2 1" />
      </svg>
      <svg {...common} className="absolute top-[84px] right-[4%]" width="52" height="52" viewBox="0 0 48 48" strokeWidth="2">
        <circle cx="24" cy="24" r="18" />
        <circle cx="24" cy="24" r="11" />
        <circle cx="24" cy="24" r="4" />
        <path d="m24 24 14-14" />
      </svg>
      <svg {...common} className="absolute top-[190px] left-0" width="70" height="70" viewBox="0 0 64 64" strokeWidth="2">
        <path d="M8 52C8 30 24 14 50 12M50 12l-10-4M50 12l-4 11" />
      </svg>
      <svg {...common} className="absolute top-[230px] right-0" width="46" height="46" viewBox="0 0 48 48" strokeWidth="2">
        <circle cx="24" cy="24" r="6" />
        <path d="M24 4v6M24 38v6M4 24h6M38 24h6M10 10l4 4M34 34l4 4M38 10l-4 4M14 34l-4 4" />
      </svg>
    </div>
  );
}

/** The product in one screen: a learner speaks and confirms what was heard. A sketch, not data. */
function Phone() {
  const { t, lang } = useLang();
  // The question is shown a second time in another language, to say "any of these will do".
  const other = lang === "en" ? "hi" : "en";
  return (
    <div
      role="img"
      aria-label={t("lp.mock.ask")}
      className="relative h-[410px] w-[262px] shrink-0 origin-bottom overflow-hidden rounded-t-[38px] border-[9px] border-b-0 border-night bg-white text-ink shadow-[0_30px_60px_-20px_rgb(0_0_0/0.55)] sm:h-[480px] lg:scale-[1.1]"
    >
      <div className="flex items-center justify-between px-4 pt-3.5 pb-1.5 text-[12px] font-bold text-muted">
        <span>{t("step.of", { current: 2, total: 8 })}</span>
        <span className="inline-flex items-center gap-1 text-accent">
          <Volume2 className="size-3.5" aria-hidden="true" />
          {t("common.listen")}
        </span>
      </div>
      <p className="px-4 pt-1.5 text-[17px] leading-tight font-bold">{t("lp.phone.q")}</p>
      <p lang={other} className="px-4 pt-1 text-[14px] leading-snug font-medium text-muted">
        {translate(other, "lp.phone.q")}
      </p>
      <div className="relative mx-auto mt-4 grid size-[84px] place-items-center rounded-full bg-accent shadow-[0_0_0_9px_rgb(36_51_166/0.12),0_0_0_20px_rgb(36_51_166/0.06)]">
        <span className="ring absolute inset-0 rounded-full bg-accent/30" />
        <svg className="relative" width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <rect x="9" y="3" width="6" height="12" rx="3" />
          <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
        </svg>
      </div>
      <Waveform className="mt-4 h-[26px]" count={11} />
      <div className="mx-3.5 mt-2 rounded-2xl bg-[#f1f3fb] px-3 py-2.5">
        <p className="mb-0.5 text-[11px] font-semibold text-muted">{t("lp.phone.heard")}</p>
        <p className="text-[14px] leading-snug font-bold">{t("lp.mock.said")}</p>
        <div className="mt-2 flex gap-2 text-[13px] font-bold">
          <span className="flex-1 rounded-full bg-lime py-1.5 text-center">{t("lp.mock.yes")}</span>
          <span className="flex-1 rounded-full border-[1.5px] border-line-strong bg-white py-1.5 text-center">{t("lp.mock.edit")}</span>
        </div>
      </div>
    </div>
  );
}

export function Hero() {
  const { t, lang } = useLang();
  const [first, second] = splitTagline(t("app.tagline"));
  const { user } = useSession();
  const speech = useSpeaker(lang, !user);

  return (
    <section id="top" className="relative overflow-hidden rounded-b-[30px] bg-accent text-white sm:rounded-b-[48px]" style={{ backgroundImage: GRID, backgroundSize: "64px 64px" }}>
      <div className="mx-auto w-full max-w-[1560px] px-[clamp(20px,3vw,56px)] pt-[96px] lg:pt-[116px]">
        <div className="grid items-end gap-x-7 xl:grid-cols-[minmax(0,1fr)_minmax(0,560px)_minmax(0,1fr)]">
          <div className="text-center xl:col-span-3">
            <span className="pop inline-flex items-center gap-2.5 rounded-full border border-white/30 bg-white/10 px-5 py-2 text-[14px] font-semibold tracking-[0.02em] sm:text-[14px]">
              <i className="size-2.5 shrink-0 rounded-full bg-lime" aria-hidden="true" />
              {t("lp.hero.note")}
            </span>
            <h1 className="pop mx-auto mt-6 max-w-[1180px] text-[clamp(34px,5.2vw,84px)] leading-[1.04] font-bold tracking-[-0.03em] text-balance" style={{ "--d": "80ms" } as CSSProperties}>
              <span className="block">{first}</span>
              {second && <span className="block text-lime">{second}</span>}
            </h1>
            <p className="pop mx-auto mt-6 max-w-[44rem] text-[clamp(16px,1.4vw,20px)] leading-relaxed text-pretty text-white/80" style={{ "--d": "160ms" } as CSSProperties}>
              {t("lp.hero.sub")}
            </p>

            <div className="pop mt-9 flex flex-col items-stretch justify-center gap-3.5 sm:flex-row sm:items-center" style={{ "--d": "240ms" } as CSSProperties}>
              <Link
                to={entryPath(user)}
                className="group inline-flex h-14 items-center justify-between gap-3 rounded-full bg-lime py-2 pr-2 pl-7 text-[14px] font-bold text-night transition-colors hover:bg-[#e8ff5a] sm:h-16 sm:text-[17px]"
              >
                {user ? t("lp.nav.open") : t("lp.cta.start.free")}
                <span className="grid size-10 place-items-center rounded-full bg-night text-lime transition-transform group-hover:translate-x-0.5 sm:size-12" aria-hidden="true">
                  <ArrowUpRight className="size-5 sm:size-6" />
                </span>
              </Link>
              <a
                href="#how"
                className="inline-flex h-14 items-center justify-center rounded-full border-2 border-white/40 px-7 text-[14px] font-semibold transition-colors hover:border-white hover:bg-white/10 sm:h-16 sm:px-8 sm:text-[17px]"
              >
                {t("lp.cta.how")}
              </a>
              {speech.available && (
                <button
                  type="button"
                  onClick={() => speech.toggle(`${t("app.tagline")} ${t("lp.hero.sub")}`)}
                  aria-pressed={speech.speaking}
                  aria-busy={speech.loading || undefined}
                  className="inline-flex h-14 items-center justify-center gap-2.5 rounded-full px-5 text-[14px] font-semibold text-white transition-colors hover:bg-white/10 sm:h-16"
                >
                  {speech.loading ? (
                    <Loader2 className="size-5 animate-spin" aria-hidden="true" />
                  ) : speech.speaking ? (
                    <Square className="size-5 fill-current" aria-hidden="true" />
                  ) : (
                    <Volume2 className="size-6" aria-hidden="true" />
                  )}
                  {speech.speaking || speech.loading ? t("lp.listen.stop") : t("lp.listen")}
                </button>
              )}
            </div>

            <div className="pop mt-9 flex flex-col items-center justify-center gap-3 text-[14px] text-white/85 sm:flex-row sm:gap-4 sm:text-[15px]" style={{ "--d": "320ms" } as CSSProperties}>
              <span className="flex" aria-hidden="true">
                {(["asha", "arjun", "ravi", "kiran"] as const).map((n, i) => (
                  <Avatar key={n} name={n} className={`block size-11 overflow-hidden rounded-full border-[3px] border-accent sm:size-[50px] ${i ? "-ml-4" : ""}`} />
                ))}
              </span>
              <span>{t("lp.hero.proof")}</span>
            </div>
          </div>

          <div className="hidden items-center self-center pb-14 xl:flex xl:flex-col xl:items-start xl:gap-8">
            <p className="max-w-[22rem] text-[16px] leading-relaxed text-white/90">“{t("lp.hero.quote")}”</p>
            <div>
              <p className="text-[61px] leading-none font-extrabold tracking-[-0.03em]">5</p>
              <p className="mt-2 max-w-[18rem] text-[15px] leading-snug font-medium text-white/75">{t("lp.hero.rungs")}</p>
            </div>
          </div>

          <div className="relative mt-12 flex h-[430px] items-end justify-center sm:h-[480px] lg:h-[560px] xl:mt-12">
            <div className="absolute bottom-0 left-1/2 h-[380px] w-[480px] max-w-full -translate-x-1/2 rounded-t-[240px] bg-deep lg:h-[490px] lg:w-[620px] lg:rounded-t-[310px]" aria-hidden="true" />
            <Doodles />
            <Person name="asha" className="absolute bottom-0 left-1/2 -ml-[350px] hidden h-[310px] w-[260px] xl:block" />
            <Person name="arjun" className="absolute bottom-0 left-1/2 ml-[90px] hidden h-[290px] w-[242px] xl:block" />
            <Phone />
          </div>

          <div className="hidden items-center justify-end self-center pb-14 xl:flex">
            <div className="max-w-[380px] rounded-[26px] bg-white p-6 text-ink shadow-[0_18px_40px_-18px_rgb(5_10_80/0.7)]">
              <p className="text-[14px] font-bold tracking-[0.06em] text-accent uppercase">{t("lp.hero.best")}</p>
              <p className="mt-2 text-[23px] leading-tight font-bold">{t("lp.career.tailoring")}</p>
              <p className="mt-1.5 text-[15px] leading-snug text-muted">
                {t("lp.mock.firstIncome")}: {t("lp.mock.tailoringFirst")}
              </p>
              <div className="mt-4 flex gap-1.5" aria-hidden="true">
                {[0, 1, 2, 3, 4].map((i) => (
                  <span key={i} className={`h-2 flex-1 rounded-full ${i < 3 ? "bg-accent" : "bg-line"}`} />
                ))}
              </div>
              <p className="mt-3.5 inline-flex items-center gap-1.5 rounded-full bg-ok-bg px-3.5 py-1.5 text-[14px] font-semibold text-ok">
                <Check className="size-4" strokeWidth={3} aria-hidden="true" />
                {t("lp.hero.source")}
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="relative z-[3] flex flex-wrap items-center justify-center gap-x-9 gap-y-3 bg-white px-6 py-6 text-[15px] text-muted sm:text-[17px]">
        <b className="font-bold text-ink">{t("lp.routes.label")}</b>
        {ROUTES.map((name) => (
          <span key={name} className="text-[16px] font-bold tracking-[0.01em] text-[#7d8298] sm:text-[20px]">
            {name}
          </span>
        ))}
      </div>
    </section>
  );
}
