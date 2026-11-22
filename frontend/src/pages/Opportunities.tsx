import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Award, Briefcase, CheckCircle2, ChevronDown, Clock, ExternalLink, FileText, GraduationCap, Hammer, Loader2, Lock, ShieldAlert, Store, Wallet, type LucideIcon } from "lucide-react";
import { Reasons, StatusChip, opensText, pick } from "../components/Eligibility";
import { Link } from "../components/Link";
import { ListenButton } from "../components/ListenButton";
import { SchemeFilter } from "../components/SchemeFilter";
import { Button, Notice, cx } from "../components/ui";
import {
  applyTo,
  checkOpportunities,
  getOpportunities,
  isApiFailure,
  setApplicationStatus,
  type Application,
  type OpportunityCard,
  type OpportunityKind,
  type OpportunityList,
  type SchemeFactKey,
  type SchemeFacts,
} from "../lib/api";
import { errorKey } from "../lib/errors";
import { useLang, type MessageKey } from "../lib/i18n";
import { navigate } from "../lib/router";

/** As many cards per row as fit at a readable width, so two cards are never squeezed into a third of the row. */
const CARD_GRID = "grid grid-cols-[repeat(auto-fill,minmax(min(100%,21rem),1fr))] gap-5";

const KIND_ICON: Record<OpportunityKind, LucideIcon> = {
  apprenticeship: Hammer,
  training: GraduationCap,
  enterprise: Store,
  exam: Award,
  portal: Briefcase,
  internship: Wallet,
};

/** How many listed programmes still wait on each answer. */
function usedByQuestion(list: OpportunityList): Record<string, number> {
  const count: Record<string, number> = {};
  [...list.top, ...list.more].forEach((c) => {
    if (c.eligibility.status === "check_with_office") c.needs.forEach((n) => (count[n] = (count[n] ?? 0) + 1));
  });
  return count;
}

/** Puts a changed application into whichever list holds its card, without asking the server for the whole list again. */
function withApplication(list: OpportunityList, app: Application): OpportunityList {
  const set = (cards: OpportunityCard[]) => cards.map((c) => (c.id === app.opportunity_id ? { ...c, application: { id: app.id, status: app.status } } : c));
  return { ...list, top: set(list.top), more: set(list.more), not_yet: set(list.not_yet) };
}

function ApplyBar({ card, onChanged }: { card: OpportunityCard; onChanged: (a: Application) => void }) {
  const { t } = useLang();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<MessageKey | null>(null);
  const app = card.application;
  const status = app?.status ?? "withdrawn";

  const run = async (call: () => Promise<{ application: Application }>) => {
    setBusy(true);
    setError(null);
    try {
      onChanged((await call()).application);
    } catch (err) {
      setError(errorKey(err));
    } finally {
      setBusy(false);
    }
  };
  const move = (next: "applied" | "confirmed" | "withdrawn") => app && run(() => setApplicationStatus(app.id, next));

  if (card.eligibility.status === "not_eligible") return null;
  return (
    <div className="flex flex-col gap-3">
      {app && status !== "withdrawn" && (
        <p className="flex items-start gap-2.5 rounded-xl bg-tint px-4 py-3 text-[15px] leading-snug font-semibold text-deep">
          <CheckCircle2 className="mt-px size-5 shrink-0 text-accent" aria-hidden="true" />
          {t(`opp.status.${status}` as MessageKey)}
        </p>
      )}
      {(!app || status === "withdrawn") && (
        <Button className="h-12 text-base" loading={busy} onClick={() => void run(() => applyTo(card.id))}>
          {t("opp.interested")}
        </Button>
      )}
      {app && (status === "interested" || status === "mentor_assisted") && (
        <Button className="h-12 text-base" loading={busy} onClick={() => void move("applied")}>
          {t("opp.applied")}
        </Button>
      )}
      {app && status === "applied" && (
        <>
          <Button className="h-12 text-base" loading={busy} onClick={() => void move("confirmed")}>
            {t("opp.confirm")}
          </Button>
          <p className="text-sm text-muted">{t("opp.confirm.help")}</p>
        </>
      )}
      {app && status !== "confirmed" && status !== "withdrawn" && (
        <button type="button" disabled={busy} onClick={() => void move("withdrawn")} className="min-h-11 self-start text-base font-semibold text-muted hover:text-ink hover:underline">
          {t("opp.withdraw")}
        </button>
      )}
      {error && <Notice>{t(error)}</Notice>}
    </div>
  );
}

function OpportunityItem({ card, onChanged }: { card: OpportunityCard; onChanged: (a: Application) => void }) {
  const { t, lang } = useLang();
  const title = pick(card.title, lang);
  const summary = pick(card.summary, lang);
  const how = pick(card.how, lang);
  const e = card.eligibility;
  const Icon = KIND_ICON[card.kind];
  const opens = opensText(e.opens_at, t);
  const translated = lang !== "en" && card.machine_translated.includes(lang);
  const spoken = [title.text, summary.text, how.text, ...opens].join(". ");
  const hasRules = e.passed.length + e.failed.length + e.missing.length + e.unresolved.length > 0;
  // These two say what the status chip already says, so they are not repeated as tags.
  const reasons = card.reasons.filter((r) => r !== "check_office" && r !== "eligible");

  return (
    <li className="flex">
      <article className="flex w-full flex-col gap-5 rounded-2xl border border-line bg-surface p-5 shadow-(--shadow-soft) sm:p-6" aria-labelledby={`opp-${card.id}`}>
        <header className="flex flex-col gap-3.5">
          <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
            <span className="inline-flex items-center gap-2 text-sm font-semibold text-muted">
              <span className="grid size-8 place-items-center rounded-lg bg-tint text-accent" aria-hidden="true">
                <Icon className="size-[18px]" />
              </span>
              {t(`opp.kind.${card.kind}` as MessageKey)}
            </span>
            <StatusChip status={e.status} compact />
          </div>
          <div className="flex flex-col gap-2">
            <h3 id={`opp-${card.id}`} className="text-xl leading-snug font-bold tracking-tight text-balance">
              {title.text}
            </h3>
            <p className="text-base text-muted">{summary.text}</p>
            {(title.fallback || summary.fallback) && <span className="text-sm text-muted">{t("paths.englishOnly")}</span>}
            {translated && <span className="text-sm text-muted">{t("paths.machine")}</span>}
          </div>
          {reasons.length > 0 && (
            <ul className="flex flex-wrap gap-1.5" aria-label={t("opp.why")}>
              {reasons.map((r) => (
                <li key={r} className="rounded-md bg-bg px-2.5 py-1 text-[13px] leading-tight font-medium text-muted ring-1 ring-line ring-inset">
                  {t(`opp.reason.${r}` as MessageKey)}
                </li>
              ))}
            </ul>
          )}
        </header>

        {opens.length > 0 && (
          <p className="flex items-start gap-2.5 rounded-xl bg-tint px-4 py-3 text-[15px] leading-snug font-semibold text-deep" role="note">
            <Clock className="mt-px size-5 shrink-0 text-accent" aria-hidden="true" />
            {opens.join(" ")}
          </p>
        )}
        {e.status !== "not_eligible" && (e.stale || e.expired) && <Notice tone="info">{t("schemes.stale")}</Notice>}

        {how.text && e.status !== "not_eligible" && (
          <div className="flex flex-col gap-1">
            <p className="text-sm font-semibold text-deep">{t("opp.how")}</p>
            <p className="text-base">{how.text}</p>
          </div>
        )}

        {hasRules && (
          <details className="group rounded-xl border border-line px-4" open={e.status === "not_eligible"}>
            <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 text-[15px] font-semibold text-accent [&::-webkit-details-marker]:hidden">
              {t("opp.rules")}
              <ChevronDown className="size-5 shrink-0 transition-transform group-open:rotate-180" aria-hidden="true" />
            </summary>
            <div className="flex flex-col gap-4 pb-4">
              <Reasons title="schemes.reasons.passed" items={e.passed} tone="ok" />
              <Reasons title="schemes.reasons.failed" items={e.failed} tone="bad" />
              <Reasons title="schemes.reasons.missing" items={e.missing} tone="ask" />
              <Reasons title="schemes.reasons.unresolved" items={e.unresolved} tone="ask" />
            </div>
          </details>
        )}

        {card.docs.length > 0 && e.status !== "not_eligible" && (
          <div className="flex flex-col gap-1.5">
            <p className="text-sm font-semibold text-deep">{t("opp.docs")}</p>
            <ul className="list-disc pl-5 text-base marker:text-line-strong">
              {card.docs.map((d) => (
                <li key={d}>{t(`schemes.doc.${d}` as MessageKey)}</li>
              ))}
            </ul>
          </div>
        )}

        <footer className="mt-auto flex flex-col gap-4 border-t border-line pt-5">
          <ApplyBar card={card} onChanged={onChanged} />
          <div className="flex flex-wrap gap-2.5">
            <ListenButton text={spoken} className="flex-1 justify-center sm:flex-none" />
            {e.status !== "not_eligible" && (
              <a
                href={card.apply_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex h-12 min-w-44 flex-[2_1_0%] items-center justify-center gap-2 rounded-xl border-[1.5px] border-line-strong px-4 text-base font-semibold whitespace-nowrap text-ink transition-colors hover:border-accent hover:text-accent"
              >
                {t("opp.visit")}
                <ExternalLink className="size-4 shrink-0" aria-hidden="true" />
              </a>
            )}
          </div>
          <div className="flex flex-col gap-1 rounded-xl bg-bg px-3.5 py-3">
            <a href={card.source.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-start gap-1.5 text-sm leading-snug font-semibold text-accent hover:underline">
              <span className="line-clamp-2">{card.source.title}</span>
              <ExternalLink className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
            </a>
            <p className="flex flex-wrap gap-x-3 gap-y-0.5 text-[13px] leading-snug">
              <span className="text-muted">{t("paths.source.entered", { date: card.source.entered_on })}</span>
              {card.source.verified_on ? (
                <span className="font-semibold text-ok">{t("paths.source.verified", { date: card.source.verified_on })}</span>
              ) : (
                <span className="font-semibold text-warn">{t("paths.source.awaiting")}</span>
              )}
            </p>
          </div>
        </footer>
      </article>
    </li>
  );
}

/** Shown only when the learner has not picked a path yet. */
function NoPath() {
  const { t } = useLang();
  return (
    <section className="flex max-w-2xl flex-col items-start gap-4 rounded-2xl border border-line bg-surface p-7 shadow-(--shadow-soft)">
      <Briefcase className="size-8 text-accent" aria-hidden="true" />
      <h2 className="text-2xl font-bold tracking-tight">{t("opp.locked.title")}</h2>
      <p className="text-lg text-muted">{t("opp.locked.help")}</p>
      <Button full={false} onClick={() => navigate("/paths")}>
        {t("opp.locked.cta")}
      </Button>
    </section>
  );
}

/** Before the path is finished: what opens next, and that only a mentor's approval opens it. */
function UnlockNotice({ unlock }: { unlock: OpportunityList["unlock"] }) {
  const { t } = useLang();
  if (unlock.finished) return null;
  const left = unlock.total - unlock.approved;
  const progress = t("opp.unlock.progress", { done: unlock.approved, total: unlock.total });
  return (
    <section
      className="flex flex-col gap-5 rounded-2xl border border-tint-strong bg-tint p-5 sm:p-6 md:flex-row md:items-center md:gap-8"
      aria-labelledby="opp-unlock"
      data-testid="unlock-notice"
    >
      <div className="flex min-w-0 flex-1 items-start gap-4">
        <span className="grid size-12 shrink-0 place-items-center rounded-xl bg-surface text-accent shadow-(--shadow-soft)" aria-hidden="true">
          <Lock className="size-6" />
        </span>
        <div className="flex min-w-0 flex-1 flex-col gap-1.5">
          <h2 id="opp-unlock" className="text-xl leading-snug font-bold text-deep">
            {t("opp.unlock.title")}
          </h2>
          <p className="max-w-2xl text-base text-deep">{left > 0 ? t("opp.unlock.more", { n: left }) : t("opp.unlock.finish")}</p>
          {left > 0 && !unlock.has_mentor && <p className="max-w-2xl text-[15px] text-muted">{t("opp.unlock.mentor")}</p>}
        </div>
      </div>

      <div className="flex shrink-0 flex-col gap-3 md:w-72">
        {unlock.total > 0 && (
          <div className="flex flex-col gap-1.5">
            <div className="flex gap-1.5" role="img" aria-label={progress}>
              {Array.from({ length: unlock.total }, (_, i) => (
                <span key={i} className={cx("h-2 flex-1 rounded-full", i < unlock.approved ? "bg-accent" : "bg-tint-strong")} />
              ))}
            </div>
            <p className="flex flex-wrap items-baseline justify-between gap-x-3 text-sm font-semibold text-deep">
              <span>{progress}</span>
              {unlock.locked > 0 && <span className="font-medium text-muted">{t("opp.unlock.waiting", { count: unlock.locked })}</span>}
            </p>
          </div>
        )}
        <Link
          to={unlock.has_mentor || left === 0 ? "/assignments" : "/mentor"}
          className="inline-flex h-12 items-center justify-center rounded-xl bg-accent px-6 text-base font-semibold text-white transition-colors hover:bg-deep"
        >
          {t("opp.unlock.cta")}
        </Link>
      </div>
    </section>
  );
}

export function OpportunitiesPage() {
  const { t } = useLang();
  const [facts, setFacts] = useState<SchemeFacts>({});
  const [data, setData] = useState<OpportunityList | null>(null);
  const [locked, setLocked] = useState(false);
  const [error, setError] = useState<MessageKey | null>(null);
  const [busy, setBusy] = useState(false);
  // Every question shown so far, with how many programmes use it. A question stays once shown, even after it is answered,
  // so the panel never vanishes or reshuffles under the learner and every answer can still be changed or cleared.
  const [seen, setSeen] = useState<Record<string, number>>({});
  const latest = useRef(0); // only the newest request may update the screen

  const run = useCallback(async (given: SchemeFacts) => {
    const mine = ++latest.current;
    setBusy(true);
    setError(null);
    try {
      const empty = Object.keys(given).length === 0;
      const result = empty ? await getOpportunities() : await checkOpportunities(given);
      if (mine === latest.current) {
        setData(result);
        const used = usedByQuestion(result);
        const asked = result.ask.filter((q) => used[q]);
        if (asked.length) setSeen((prev) => Object.fromEntries([...Object.entries(prev), ...asked.map((q) => [q, Math.max(prev[q] ?? 0, used[q])])]));
      }
    } catch (err) {
      if (mine !== latest.current) return;
      if (isApiFailure(err) && err.code === "no_path") setLocked(true);
      else setError(errorKey(err));
    } finally {
      if (mine === latest.current) setBusy(false);
    }
  }, []);

  // The first load is at once. After that, answers change the list a moment after the learner stops tapping or typing.
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      void run(facts);
      return;
    }
    const id = window.setTimeout(() => void run(facts), 450);
    return () => window.clearTimeout(id);
  }, [facts, run]);

  const wanted = useMemo(() => Object.keys(seen) as SchemeFactKey[], [seen]);

  const onChanged = (app: Application) => setData((d) => (d ? withApplication(d, app) : d));

  return (
    <div className="flex flex-col gap-8 pt-2">
      <div className="flex flex-col gap-2">
        <h1 className="text-[30px] leading-[1.1] font-bold tracking-tight md:text-[38px]">{t("opp.title")}</h1>
        <p className="max-w-3xl text-lg text-muted">{t("opp.lead")}</p>
      </div>

      {error && <Notice>{t(error)}</Notice>}
      {locked && <NoPath />}
      {!data && !error && !locked && (
        <p className="flex items-center gap-3 text-lg text-muted" role="status">
          <Loader2 className="size-5 animate-spin text-accent" aria-hidden="true" />
          {t("opp.loading")}
        </p>
      )}

      {data && data.in_person_check_needed && (
        <section className="flex gap-4 rounded-2xl border border-warn/40 bg-warn-bg p-5" role="note" aria-labelledby="person-check">
          <ShieldAlert className="mt-0.5 size-7 shrink-0 text-warn" aria-hidden="true" />
          <div className="flex flex-col gap-1">
            <h2 id="person-check" className="text-lg font-bold">
              {t("opp.person.title")}
            </h2>
            <p className="text-base">{t("opp.person.help")}</p>
          </div>
        </section>
      )}

      {data && <UnlockNotice unlock={data.unlock} />}

      {data && (
        <div className={cx("grid grid-cols-[minmax(0,1fr)] items-start gap-8", wanted.length > 0 && "lg:grid-cols-[minmax(300px,360px)_minmax(0,1fr)]")}>
          {wanted.length > 0 && <SchemeFilter wanted={wanted} usedBy={seen} facts={facts} onChange={setFacts} busy={busy} />}

          <div className={cx("flex min-w-0 flex-col gap-10 transition-opacity", busy && "opacity-60")} aria-busy={busy}>
            <section className="flex flex-col gap-5" aria-labelledby="opp-top">
              <div className="flex flex-col gap-1">
                <h2 id="opp-top" className="text-2xl font-bold tracking-tight">
                  {t(data.unlock.finished ? "opp.top" : "opp.top.preview")}
                </h2>
                <p className="max-w-3xl text-base text-muted">{t("opp.top.help")}</p>
              </div>
              {data.top.length === 0 ? (
                <p className="text-lg text-muted">{t("opp.none")}</p>
              ) : (
                <ul className={CARD_GRID}>
                  {data.top.map((c) => (
                    <OpportunityItem key={c.id} card={c} onChanged={onChanged} />
                  ))}
                </ul>
              )}
            </section>

            {data.more.length > 0 && (
              <section className="flex flex-col gap-5" aria-labelledby="opp-more">
                <h2 id="opp-more" className="text-2xl font-bold tracking-tight">
                  {t("opp.more")}
                </h2>
                <ul className={CARD_GRID}>
                  {data.more.map((c) => (
                    <OpportunityItem key={c.id} card={c} onChanged={onChanged} />
                  ))}
                </ul>
              </section>
            )}

            {data.not_yet.length > 0 && (
              <section className="flex flex-col gap-5" aria-labelledby="opp-notyet">
                <div className="flex flex-col gap-1">
                  <h2 id="opp-notyet" className="text-2xl font-bold tracking-tight">
                    {t("opp.notyet")}
                  </h2>
                  <p className="max-w-3xl text-base text-muted">{t("opp.notyet.help")}</p>
                </div>
                <ul className={CARD_GRID}>
                  {data.not_yet.map((c) => (
                    <OpportunityItem key={c.id} card={c} onChanged={onChanged} />
                  ))}
                </ul>
              </section>
            )}

            {data.unlock.finished && (
              <section className="flex flex-col items-start gap-4 rounded-2xl border border-tint-strong bg-tint p-5 sm:flex-row sm:items-center sm:gap-5 sm:p-6" aria-labelledby="opp-pack">
                <span className="grid size-12 shrink-0 place-items-center rounded-xl bg-surface text-accent shadow-(--shadow-soft)" aria-hidden="true">
                  <FileText className="size-6" />
                </span>
                <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <h2 id="opp-pack" className="text-xl font-bold text-deep">
                    {t("opp.pack.title")}
                  </h2>
                  <p className="text-base text-deep">{t("opp.pack.help")}</p>
                </div>
                <Link to={`/pack/${data.journey.career_id}`} className="inline-flex h-12 shrink-0 items-center rounded-xl bg-accent px-6 text-base font-semibold text-white transition-colors hover:bg-deep">
                  {t("opp.pack.cta")}
                </Link>
              </section>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
