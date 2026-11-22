import { useEffect, useState, type ReactNode } from "react";
import { ArrowLeft, BookOpen, Check, Clock, ExternalLink, FileText, ListChecks, Loader2, Route, ShieldAlert, ShieldCheck, Wallet, type LucideIcon } from "lucide-react";
import { ListenButton } from "../components/ListenButton";
import { Link } from "../components/Link";
import { Button, Notice, cx } from "../components/ui";
import { getCareer, isApiFailure, selectCareer, type CareerDetail, type Journey, type PathItem, type Resource } from "../lib/api";
import { errorKey } from "../lib/errors";
import { LANGS, useLang, type Lang, type MessageKey } from "../lib/i18n";
import { navigate } from "../lib/router";
import { useSession } from "../lib/session";
import { useJourney, usePaths } from "../lib/usePaths";

function Heading({ title, lead }: { title: string; lead?: string }) {
  return (
    <div className="flex flex-col gap-2">
      <h1 className="text-[30px] leading-[1.1] md:text-[38px] font-bold tracking-tight">{title}</h1>
      {lead && <p className="max-w-3xl text-lg text-muted">{lead}</p>}
    </div>
  );
}

function Waiting({ label }: { label: string }) {
  return (
    <p className="flex items-center gap-3 text-lg text-muted" role="status">
      <Loader2 className="size-5 animate-spin text-accent" aria-hidden="true" />
      {label}
    </p>
  );
}

/** Says plainly when a line was produced by a machine translation, so nobody mistakes it for reviewed text. */
function MachineNote({ show }: { show: boolean }) {
  const { t } = useLang();
  return show ? <span className="text-sm text-muted">{t("paths.machine")}</span> : null;
}

function SafetyNote({ children }: { children: ReactNode }) {
  return (
    <p className="flex gap-3 rounded-xl bg-warn-bg p-4 text-base text-warn" role="note">
      <ShieldAlert className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
      <span>{children}</span>
    </p>
  );
}

// ---------------------------------------------------------------------------
// The list
// ---------------------------------------------------------------------------

function PathCard({ item, picked, onPick, busy, compact = false }: { item: PathItem; picked: boolean; onPick: () => void; busy: boolean; compact?: boolean }) {
  const { t, lang } = useLang();
  const name = item.name[lang];
  const reason = item.reason[lang];
  const first = item.first_income_step[lang];
  const spoken = `${name}. ${reason} ${t("paths.first")} ${first}`;
  const badge = item.tier === "best" ? t("paths.badge.best") : item.tier === "starter" ? t("paths.badge.starter") : null;
  return (
    <li className="flex">
      <article
        className={cx(
          "flex w-full flex-col rounded-2xl border bg-surface shadow-(--shadow-soft)",
          compact ? "gap-3 p-5" : "gap-4 p-6",
          picked ? "border-accent" : "border-line",
        )}
        aria-labelledby={`path-${item.career_id}`}
      >
        <header className="flex flex-col gap-2">
          {badge && (
            <span className="inline-flex self-start rounded-full bg-tint px-3 py-1 text-sm font-semibold text-deep">{badge}</span>
          )}
          <h3 id={`path-${item.career_id}`} className={cx("leading-tight font-bold tracking-tight", compact ? "text-lg" : "text-[22px]")}>
            {name}
          </h3>
          <p className={compact ? "text-[15px] text-muted" : "text-base"}>{reason}</p>
          <MachineNote show={lang !== "en" && item.reason_source[lang] === "ai_translated"} />
        </header>
        {!compact && (
          <div className="rounded-xl bg-tint p-4">
            <p className="text-sm font-semibold tracking-wide text-deep uppercase">{t("paths.first")}</p>
            <p className="mt-1 text-base">{first}</p>
          </div>
        )}
        {item.under18_theory_only && <SafetyNote>{t("paths.safety.card")}</SafetyNote>}
        <div className="mt-auto flex flex-wrap items-center gap-3 pt-1">
          {!compact && <ListenButton text={spoken} />}
          <Link
            to={`/paths/${item.career_id}`}
            className="inline-flex h-12 items-center rounded-xl border-[1.5px] border-line-strong px-5 text-base font-semibold text-ink hover:border-accent hover:text-accent"
          >
            {t("paths.details")}
          </Link>
          {picked ? (
            <span className="inline-flex h-12 items-center gap-2 rounded-xl bg-ok-bg px-5 text-base font-semibold text-ok">
              <Check className="size-5" aria-hidden="true" />
              {t("paths.picked.badge")}
            </span>
          ) : (
            <Button full={false} loading={busy} className="h-12 px-6 text-base" onClick={onPick}>
              {t("paths.pick")}
            </Button>
          )}
        </div>
      </article>
    </li>
  );
}

export function PathsPage() {
  const { t, lang } = useLang();
  const paths = usePaths();
  const { journey, set, loaded } = useJourney();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<MessageKey | null>(null);

  const pick = async (id: string) => {
    setBusy(id);
    setError(null);
    try {
      set(await selectCareer(id));
    } catch (err) {
      setError(errorKey(err));
    } finally {
      setBusy(null);
    }
  };

  if (paths.state === "loading" || !loaded) {
    return (
      <div className="flex max-w-3xl flex-col gap-6 pt-2">
        <Heading title={t("paths.title")} />
        <Waiting label={t("paths.loading")} />
      </div>
    );
  }
  if (paths.state === "no_intake") {
    return (
      <div className="flex max-w-3xl flex-col gap-6 pt-2">
        <Heading title={t("paths.title")} lead={t("paths.needIntake")} />
        <Button full={false} className="self-start" onClick={() => navigate("/skills")}>
          {t("paths.needIntake.cta")}
        </Button>
      </div>
    );
  }
  if (paths.state === "error") {
    return (
      <div className="flex max-w-3xl flex-col gap-6 pt-2">
        <Heading title={t("paths.title")} />
        <Notice>{t("err.network")}</Notice>
        <Button full={false} className="self-start" onClick={() => window.location.reload()}>
          {t("status.retry")}
        </Button>
      </div>
    );
  }

  const items = paths.assessment.paths;
  const starters = items.every((p) => p.tier === "starter");
  const top = items.filter((p) => p.tier !== "also");
  const also = items.filter((p) => p.tier === "also");
  const chosen = journey ? items.find((p) => p.career_id === journey.career.career_id) : undefined;
  const card = (item: PathItem, compact = false) => (
    <PathCard
      key={item.career_id}
      item={item}
      compact={compact}
      picked={journey?.career.career_id === item.career_id}
      busy={busy === item.career_id}
      onPick={() => pick(item.career_id)}
    />
  );
  return (
    <div className="flex flex-col gap-8 pt-2">
      <Heading title={t("paths.title")} lead={starters ? t("paths.lead.starters") : t("paths.lead")} />
      {journey && (
        <Notice tone="info">{t("paths.picked.note", { name: chosen ? chosen.name[lang] : journey.career.name[lang] })}</Notice>
      )}
      {error && <Notice>{t(error)}</Notice>}

      <section className="flex flex-col gap-4" aria-labelledby="paths-best">
        <h2 id="paths-best" className="text-2xl font-bold tracking-tight">
          {t(starters ? "paths.group.starter" : "paths.group.best")}
        </h2>
        <ul className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">{top.map((item) => card(item))}</ul>
      </section>

      {also.length > 0 && (
        <section className="flex flex-col gap-4" aria-labelledby="paths-also">
          <div className="flex flex-col gap-1">
            <h2 id="paths-also" className="text-2xl font-bold tracking-tight">
              {t("paths.group.also")}
            </h2>
            <p className="text-base text-muted">{t("paths.group.also.help")}</p>
          </div>
          <ul className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">{also.map((item) => card(item, true))}</ul>
        </section>
      )}

      <p className="text-base text-muted">
        {t("paths.redo")}{" "}
        <Link to="/skills" className="font-semibold text-accent underline">
          {t("paths.redo.cta")}
        </Link>
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// One career in detail
// ---------------------------------------------------------------------------

function pickLang<T extends { en: string } & Partial<Record<Lang, string>>>(value: T, lang: Lang): { text: string; fallback: boolean } {
  const own = value[lang];
  return own ? { text: own, fallback: false } : { text: value.en, fallback: lang !== "en" };
}

/** A small icon in a tinted square, used to head each block in the side column. */
function SideHeading({ id, icon: Icon, title, help }: { id: string; icon: LucideIcon; title: string; help?: string }) {
  return (
    <div className="flex items-start gap-3">
      <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-tint text-accent" aria-hidden="true">
        <Icon className="size-5" />
      </span>
      <div className="flex min-w-0 flex-col gap-0.5">
        <h2 id={id} className="text-xl leading-tight font-bold tracking-tight">
          {title}
        </h2>
        {help && <p className="text-[15px] text-muted">{help}</p>}
      </div>
    </div>
  );
}

function NeedTile({ icon: Icon, label, value, meter }: { icon: LucideIcon; label: string; value: string; meter?: { level: number; of: number } }) {
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-line bg-surface p-4 shadow-(--shadow-soft)">
      <span className="grid size-9 place-items-center rounded-lg bg-tint text-accent" aria-hidden="true">
        <Icon className="size-[18px]" />
      </span>
      <div className="flex flex-col gap-1">
        <dt className="text-sm font-medium text-muted">{label}</dt>
        <dd className="text-lg leading-snug font-bold">{value}</dd>
      </div>
      {meter && (
        <span className="mt-auto flex gap-1.5" aria-hidden="true">
          {Array.from({ length: meter.of }, (_, i) => (
            <span key={i} className={cx("h-1.5 flex-1 rounded-full", i < meter.level ? "bg-accent" : "bg-line")} />
          ))}
        </span>
      )}
    </div>
  );
}

const COST_LEVEL: Record<string, number> = { none: 0, low: 1, medium: 2 };

function SourceCard({ source }: { source: CareerDetail["sources"][number] }) {
  const { t } = useLang();
  return (
    <li className="flex gap-3 rounded-xl border border-line bg-surface p-4 shadow-(--shadow-soft)">
      <span className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-lg bg-bg text-muted" aria-hidden="true">
        <FileText className="size-[18px]" />
      </span>
      <div className="flex min-w-0 flex-col gap-2">
        <a href={source.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-start gap-2 text-base leading-snug font-semibold text-accent hover:underline">
          <span>{source.title}</span>
          <ExternalLink className="mt-1 size-4 shrink-0" aria-hidden="true" />
        </a>
        <p className="text-[15px] text-muted">{source.note}</p>
        <p className="flex flex-wrap items-center gap-x-3 gap-y-2 text-sm">
          {source.verified_on ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-ok-bg px-3 py-1 font-semibold text-ok">
              <ShieldCheck className="size-4" aria-hidden="true" />
              {t("paths.source.verified", { date: source.verified_on })}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-warn-bg px-3 py-1 font-semibold text-warn">
              <Clock className="size-4" aria-hidden="true" />
              {t("paths.source.awaiting")}
            </span>
          )}
          <span className="text-muted">{t("paths.source.entered", { date: source.entered_on })}</span>
        </p>
      </div>
    </li>
  );
}

// ---------------------------------------------------------------------------
// Where to learn: real courses, linked out
// ---------------------------------------------------------------------------

/** Courses in the learner's language first, then, for a school learner, courses made for school learners. */
function orderResources(items: Resource[], lang: Lang, inSchool: boolean): Resource[] {
  const rank = (r: Resource) => (r.languages.includes(lang) ? 0 : 2) + (inSchool && r.level === "school" ? 0 : 1);
  return [...items].sort((a, b) => rank(a) - rank(b));
}

function ResourceCard({ res }: { res: Resource }) {
  const { t, lang } = useLang();
  const names = res.languages.map((code) => LANGS.find((l) => l.code === code)?.label ?? code).join(", ");
  const facts = [
    t(`paths.learn.kind.${res.kind}` as MessageKey),
    res.level ? t(`paths.learn.level.${res.level}` as MessageKey) : null,
    res.duration_weeks ? t("paths.learn.weeks", { n: res.duration_weeks }) : null,
    res.languages.length > 0 ? t("paths.learn.lang", { language: names }) : t("paths.learn.langUnknown"),
    res.cost ? t(`paths.learn.cost.${res.cost}` as MessageKey) : null,
    res.entry ? t(`paths.learn.entry.${res.entry}` as MessageKey) : null,
  ].filter((x): x is string => Boolean(x));
  return (
    <li className="flex flex-col gap-2 rounded-xl border border-line bg-surface p-4 shadow-(--shadow-soft)">
      <a href={res.url} target="_blank" rel="noopener noreferrer" lang={res.languages.includes("hi") && lang === "hi" ? "hi" : undefined} className="inline-flex items-start gap-2 text-base leading-snug font-semibold text-accent hover:underline">
        <span>{res.title}</span>
        <ExternalLink className="mt-1 size-4 shrink-0" aria-hidden="true" />
      </a>
      <p className="text-base text-muted">{res.provider}</p>
      <ul className="flex flex-wrap gap-2">
        {facts.map((f) => (
          <li key={f} className="rounded-full bg-tint px-3 py-1 text-sm font-medium text-deep">
            {f}
          </li>
        ))}
      </ul>
      <p className="text-sm">
        {res.verified_on ? (
          <span className="font-semibold text-ok">{t("paths.learn.verified", { date: res.verified_on })}</span>
        ) : (
          <span className="text-warn">{t("paths.learn.found", { date: res.found_on })}</span>
        )}
      </p>
    </li>
  );
}

function LearnSection({ career }: { career: CareerDetail }) {
  const { t, lang } = useLang();
  const { profile } = useSession();
  const inSchool = profile?.kind === "student" && profile.data.grade <= 12;
  const items = orderResources(career.learn, lang, inSchool);
  if (items.length === 0 && career.portals.length === 0) return null;
  return (
    <section className="flex flex-col gap-4" aria-labelledby="learn">
      <SideHeading id="learn" icon={BookOpen} title={t("paths.learn")} help={items.length > 0 ? t("paths.learn.help") : undefined} />
      {items.length > 0 && (
        <>
          <ul className="flex flex-col gap-3">
            {items.map((r) => (
              <ResourceCard key={r.id} res={r} />
            ))}
          </ul>
        </>
      )}
      {career.portals.length > 0 && (
        <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-base">
          <span className="text-muted">{t("paths.learn.portals")}:</span>
          {career.portals.map((p) => (
            <a key={p.url} href={p.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 font-semibold text-accent underline">
              {p.title}
              <ExternalLink className="size-4" aria-hidden="true" />
            </a>
          ))}
        </p>
      )}
    </section>
  );
}

export function PathDetailPage({ careerId }: { careerId: string }) {
  const { t, lang } = useLang();
  const { journey, set } = useJourney();
  const [career, setCareer] = useState<CareerDetail | null>(null);
  const [failed, setFailed] = useState<MessageKey | null>(null);
  const [busy, setBusy] = useState(false);
  const [pickError, setPickError] = useState<MessageKey | null>(null);

  useEffect(() => {
    let alive = true;
    setCareer(null);
    setFailed(null);
    getCareer(careerId)
      .then((c) => alive && setCareer(c))
      .catch((err: unknown) => alive && setFailed(isApiFailure(err) && err.status === 404 ? "paths.notFound" : errorKey(err)));
    return () => {
      alive = false;
    };
  }, [careerId]);

  const back = (
    <Link to="/paths" className="inline-flex items-center gap-2 self-start text-base font-semibold text-accent hover:underline">
      <ArrowLeft className="size-5" aria-hidden="true" />
      {t("paths.back")}
    </Link>
  );

  if (failed) {
    return (
      <div className="flex max-w-3xl flex-col gap-6 pt-2">
        {back}
        <Notice>{t(failed)}</Notice>
      </div>
    );
  }
  if (!career) {
    return (
      <div className="flex max-w-3xl flex-col gap-6 pt-2">
        {back}
        <Waiting label={t("paths.loading")} />
      </div>
    );
  }

  const picked = journey?.career.career_id === career.career_id;
  const pick = async () => {
    setBusy(true);
    setPickError(null);
    try {
      set((await selectCareer(career.career_id)) as Journey);
    } catch (err) {
      setPickError(errorKey(err));
    } finally {
      setBusy(false);
    }
  };
  const translatedLadder = lang !== "en" && career.machine_translated.includes(lang);
  const spoken = `${career.name[lang]}. ${career.summary[lang]} ${t("paths.first")} ${career.first_income_step[lang]}`;

  return (
    <div className="flex flex-col gap-8 pt-2">
      {back}
      <Heading title={career.name[lang]} lead={career.summary[lang]} />
      <div className="flex flex-wrap items-center gap-3">
        <ListenButton text={spoken} />
        {picked ? (
          <span className="inline-flex h-12 items-center gap-2 rounded-xl bg-ok-bg px-5 text-base font-semibold text-ok">
            <Check className="size-5" aria-hidden="true" />
            {t("paths.picked.badge")}
          </span>
        ) : (
          <Button full={false} loading={busy} className="h-12 px-6 text-base" onClick={pick}>
            {t("paths.pick")}
          </Button>
        )}
      </div>
      {pickError && <Notice>{t(pickError)}</Notice>}
      {picked && (
        <div className="flex flex-wrap items-center gap-4 rounded-2xl bg-tint p-5">
          <p className="min-w-0 flex-1 text-lg font-medium text-deep">{t("paths.picked.next")}</p>
          <Button full={false} className="h-12 px-6 text-base" onClick={() => navigate("/mentor")}>
            {t("paths.picked.cta")}
          </Button>
        </div>
      )}
      {career.under18_theory_only && <SafetyNote>{pickLang(career.safety.under18_note, lang).text}</SafetyNote>}

      <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="flex flex-col gap-8">
      <section className="rounded-2xl bg-tint p-6" aria-labelledby="first-income">
        <h2 id="first-income" className="text-sm font-semibold tracking-wide text-deep uppercase">
          {t("paths.first")}
        </h2>
        <p className="mt-1 text-xl">{career.first_income_step[lang]}</p>
      </section>

      <section className="flex flex-col gap-4" aria-labelledby="ladder">
        <h2 id="ladder" className="text-2xl font-bold tracking-tight">
          {t("paths.ladder")}
        </h2>
        <ol className="flex flex-col gap-4">
          {career.ladder.map((rung) => {
            const title = pickLang(rung.title, lang);
            const detail = pickLang(rung.detail, lang);
            return (
              <li key={rung.key} className="flex gap-5 rounded-2xl border border-line bg-surface p-5">
                <span className="grid size-11 shrink-0 place-items-center rounded-full bg-accent text-lg font-bold text-white" aria-hidden="true">
                  {rung.rung}
                </span>
                <div className="flex min-w-0 flex-col gap-1">
                  <h3 className="text-sm font-semibold tracking-wide text-deep uppercase">{t(`paths.rung.${rung.key}` as MessageKey)}</h3>
                  <p className="text-xl font-semibold">{title.text}</p>
                  <p className="text-lg text-muted">{detail.text}</p>
                  {title.fallback && <span className="text-sm text-muted">{t("paths.englishOnly")}</span>}
                </div>
              </li>
            );
          })}
        </ol>
        <MachineNote show={translatedLadder} />
      </section>

        </div>
        <div className="flex flex-col gap-8">
      <section className="flex flex-col gap-4" aria-labelledby="needs">
        <SideHeading id="needs" icon={ListChecks} title={t("paths.needs")} />
        <dl className="grid gap-3 sm:grid-cols-3">
          <NeedTile
            icon={Wallet}
            label={t("paths.needs.cost")}
            value={t(`paths.cost.${career.traits.startup_cost}` as MessageKey)}
            meter={{ level: COST_LEVEL[career.traits.startup_cost] ?? 1, of: 3 }}
          />
          <NeedTile icon={Clock} label={t("paths.needs.hours")} value={t("paths.needs.hoursValue", { n: career.traits.min_hours_per_week })} />
          <NeedTile icon={Route} label={t("paths.needs.travel")} value={career.traits.needs_travel ? t("paths.yes") : t("paths.no")} />
        </dl>
      </section>

      <LearnSection career={career} />

      <section className="flex flex-col gap-4" aria-labelledby="sources">
        <SideHeading id="sources" icon={ShieldCheck} title={t("paths.sources")} help={t("paths.sources.help")} />
        <ul className="flex flex-col gap-3">
          {career.sources.map((s) => (
            <SourceCard key={s.url} source={s} />
          ))}
        </ul>
      </section>
        </div>
      </div>
    </div>
  );
}
