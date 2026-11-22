import type { CSSProperties } from "react";
import { ArrowRight, Mic, Square, Volume2 } from "lucide-react";
import { Link } from "../../components/Link";
import { LANGS, useLang } from "../../lib/i18n";
import { entryPath } from "../../lib/routes";
import { useSession } from "../../lib/session";
import { useReadAloud } from "./hooks";
import { Tour } from "./Tour";

/** Splits "Speak your skill. Find your first income." so the promise can carry the colour. */
function splitTagline(text: string): [string, string] {
  const m = text.match(/^(.+?[.,।])\s+(.+)$/);
  return m ? [m[1], m[2]] : [text, ""];
}

const BUBBLES = [
  { lang: LANGS[1], pos: "top-[168px] left-[3%] xl:left-[6%]", delay: 0 },
  { lang: LANGS[2], pos: "top-[300px] right-[2%] xl:right-[5%]", delay: 1400 },
  { lang: LANGS[0], pos: "top-[470px] left-[1%] xl:left-[3%]", delay: 2600 },
];

export function Hero() {
  const { t, lang } = useLang();
  const [first, second] = splitTagline(t("app.tagline"));
  const speech = useReadAloud(lang);
  const { user } = useSession();

  return (
    <section className="relative overflow-hidden pt-[150px] pb-24">
      <div aria-hidden="true" className="absolute inset-0 -z-10">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_55%_at_50%_0%,#dce6ff_0%,transparent_70%)]" />
        <div className="drift absolute -top-24 left-[8%] size-[420px] rounded-full bg-accent/12 blur-3xl" />
        <div className="drift absolute top-40 right-[6%] size-[360px] rounded-full bg-deep/10 blur-3xl" style={{ animationDelay: "-9s" }} />
        <div
          className="absolute inset-0 opacity-60"
          style={{
            backgroundImage: "radial-gradient(rgb(29 78 216 / 0.14) 1px, transparent 1px)",
            backgroundSize: "28px 28px",
            maskImage: "radial-gradient(ellipse 70% 55% at 50% 30%, #000 20%, transparent 75%)",
          }}
        />
      </div>

      {BUBBLES.map(({ lang: l, pos, delay }) => (
        <span
          key={l.code}
          lang={l.code}
          aria-hidden="true"
          className={`float absolute ${pos} hidden items-center gap-2.5 rounded-2xl border border-line bg-white px-4 py-2.5 text-lg font-semibold shadow-(--shadow-lift) lg:inline-flex`}
          style={{ "--d": `${delay}ms` } as CSSProperties}
        >
          <span className="grid size-8 place-items-center rounded-full bg-accent text-white">
            <Mic className="size-4" />
          </span>
          {l.label}
        </span>
      ))}

      <div className="mx-auto w-full max-w-[1240px] px-8 text-center">
        <h1 className="pop mx-auto text-[clamp(44px,6.6vw,92px)] leading-[1.06] font-bold tracking-[-0.035em] text-ink">
          <span className="block">{first}</span>
          {second && <span className="block text-accent">{second}</span>}
        </h1>
        <p className="pop mx-auto mt-7 max-w-[40rem] text-xl leading-relaxed text-pretty text-muted md:text-[22px]" style={{ "--d": "120ms" } as CSSProperties}>
          {t("lp.hero.sub")}
        </p>

        <div className="pop mt-10 flex flex-wrap items-center justify-center gap-4" style={{ "--d": "240ms" } as CSSProperties}>
          <Link
            to={entryPath(user)}
            className="group inline-flex h-16 items-center gap-3 rounded-2xl bg-accent px-9 text-xl font-semibold text-white shadow-[0_14px_34px_-10px_rgb(29_78_216/0.7)] transition-all hover:bg-accent-hover hover:shadow-[0_18px_40px_-10px_rgb(29_78_216/0.8)]"
          >
            {user ? t("lp.nav.open") : t("lp.cta.start.free")}
            <ArrowRight className="size-6 transition-transform group-hover:translate-x-1" aria-hidden="true" />
          </Link>
          <a
            href="#how"
            className="inline-flex h-16 items-center rounded-2xl border-[1.5px] border-line-strong bg-white px-8 text-xl font-semibold text-ink transition-colors hover:border-accent hover:text-accent"
          >
            {t("lp.cta.how")}
          </a>
          {speech.available && (
            <button
              type="button"
              onClick={speech.toggle}
              aria-pressed={speech.speaking}
              className="inline-flex h-16 items-center gap-2.5 rounded-2xl px-6 text-lg font-semibold text-accent transition-colors hover:bg-tint"
            >
              {speech.speaking ? <Square className="size-5 fill-current" aria-hidden="true" /> : <Volume2 className="size-6" aria-hidden="true" />}
              {speech.speaking ? t("lp.listen.stop") : t("lp.listen")}
            </button>
          )}
        </div>
        <p className="pop mt-6 text-base font-medium text-muted" style={{ "--d": "320ms" } as CSSProperties}>
          {t("lp.hero.note")}
        </p>

        <div className="pop mx-auto mt-16 max-w-[1040px] text-left" style={{ "--d": "420ms" } as CSSProperties}>
          <Tour />
        </div>
      </div>
    </section>
  );
}
