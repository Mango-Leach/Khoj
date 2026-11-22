import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { PageBanner } from "../components/PageBanner";
import { ExternalLink, Loader2 } from "lucide-react";
import { Reasons, StatusChip, opensText, pick } from "../components/Eligibility";
import { ListenButton } from "../components/ListenButton";
import { SchemeFilter } from "../components/SchemeFilter";
import { Notice, cx } from "../components/ui";
import { checkSchemes, type PartialLocalised, type SchemeCheck, type SchemeFactKey, type SchemeFacts, type SchemeResult, type SchemeStatus } from "../lib/api";
import { errorKey } from "../lib/errors";
import { useLang, type MessageKey } from "../lib/i18n";

const GROUPS: SchemeStatus[] = ["eligible", "check_with_office", "not_eligible"];

function SchemeCard({ r }: { r: SchemeResult }) {
  const { t, lang } = useLang();
  const name = pick(r.name, lang);
  const summary = pick(r.summary, lang);
  const note = pick(r.note as PartialLocalised, lang);
  const translated = lang !== "en" && r.machine_translated.includes(lang);
  const opens = opensText(r.opens_at, t);
  const spoken = [name.text, summary.text, ...opens].join(". ");
  return (
    <li className="flex">
      <article className="flex w-full flex-col gap-4 rounded-[28px] border border-line bg-surface p-6 shadow-(--shadow-soft)" aria-labelledby={`scheme-${r.id}`}>
        <header className="flex flex-col gap-2">
          <StatusChip status={r.status} />
          <h3 id={`scheme-${r.id}`} className="text-[21px] leading-tight font-bold tracking-tight">
            {name.text}
          </h3>
          <p className="text-base">{summary.text}</p>
          {(name.fallback || summary.fallback) && <span className="text-sm text-muted">{t("paths.englishOnly")}</span>}
          {translated && <span className="text-sm text-muted">{t("paths.machine")}</span>}
        </header>

        {opens.length > 0 && (
          <p className="rounded-xl bg-tint p-4 text-lg" role="note">
            {opens.join(" ")}
          </p>
        )}
        {r.status !== "not_eligible" && (r.stale || r.expired) && <Notice tone="info">{t("schemes.stale")}</Notice>}

        <div className="flex flex-col gap-4">
          <Reasons title="schemes.reasons.passed" items={r.passed} tone="ok" />
          <Reasons title="schemes.reasons.failed" items={r.failed} tone="bad" />
          <Reasons title="schemes.reasons.missing" items={r.missing} tone="ask" />
          <Reasons title="schemes.reasons.unresolved" items={r.unresolved} tone="ask" />
        </div>

        {note.text && <p className="text-base text-muted">{note.text}</p>}

        {r.docs.length > 0 && r.status !== "not_eligible" && (
          <div className="flex flex-col gap-1.5">
            <p className="text-sm font-semibold tracking-wide text-deep uppercase">{t("schemes.docs")}</p>
            <ul className="list-disc pl-6 text-base">
              {r.docs.map((d) => (
                <li key={d}>{t(`schemes.doc.${d}` as MessageKey)}</li>
              ))}
            </ul>
          </div>
        )}

        <footer className="mt-auto flex flex-col gap-3 border-t border-line pt-4">
          <a href={r.source.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-start gap-2 text-base font-semibold text-accent underline">
            <span>{r.source.title}</span>
            <ExternalLink className="mt-1 size-4 shrink-0" aria-hidden="true" />
          </a>
          <p className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
            <span className="text-muted">{t("paths.source.entered", { date: r.source.entered_on })}</span>
            {r.source.verified_on ? (
              <span className="font-semibold text-ok">{t("paths.source.verified", { date: r.source.verified_on })}</span>
            ) : (
              <span className="font-semibold text-warn">{t("paths.source.awaiting")}</span>
            )}
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <ListenButton text={spoken} />
            {r.apply_url && r.status !== "not_eligible" && (
              <a
                href={r.apply_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex h-12 items-center gap-2 rounded-full border-[1.5px] border-line-strong px-5 text-base font-semibold text-ink hover:border-accent hover:text-accent"
              >
                {t("schemes.apply")}
                <ExternalLink className="size-4" aria-hidden="true" />
              </a>
            )}
          </div>
        </footer>
      </article>
    </li>
  );
}

export function ScholarshipsPage() {
  const { t } = useLang();
  const [facts, setFacts] = useState<SchemeFacts>({});
  const [data, setData] = useState<SchemeCheck | null>(null);
  const [error, setError] = useState<MessageKey | null>(null);
  const [busy, setBusy] = useState(false);
  const latest = useRef(0); // only the newest request may update the screen

  const run = useCallback(async (given: SchemeFacts) => {
    const mine = ++latest.current;
    setBusy(true);
    setError(null);
    try {
      const result = await checkSchemes(given);
      if (mine === latest.current) setData(result);
    } catch (err) {
      if (mine === latest.current) setError(errorKey(err));
    } finally {
      if (mine === latest.current) setBusy(false);
    }
  }, []);

  // The first check runs at once. After that, answers change the results a moment after the learner stops tapping or typing.
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

  // Only ask what some scheme actually uses, and say how many schemes use each answer.
  const { wanted, usedBy } = useMemo(() => {
    const count: Record<string, number> = {};
    data?.results.forEach((r) => r.needs.forEach((n) => (count[n] = (count[n] ?? 0) + 1)));
    const order: SchemeFactKey[] = ["social_category", "annual_income_inr", "govt_service_in_family", "school_type", "in_professional_course", "qualification", "works_in_listed_trade", "took_similar_loan_5y"];
    return { wanted: order.filter((q) => count[q]), usedBy: count };
  }, [data]);

  return (
    <div className="flex flex-col gap-8 pt-2">
      <PageBanner title={t("schemes.title")} lead={t("schemes.lead")} />

      {error && <Notice>{t(error)}</Notice>}

      {!data && !error && (
        <p className="flex items-center gap-3 text-lg text-muted" role="status">
          <Loader2 className="size-5 animate-spin text-accent" aria-hidden="true" />
          {t("schemes.loading")}
        </p>
      )}

      {data && (
        <div className={cx("grid grid-cols-[minmax(0,1fr)] items-start gap-8", wanted.length > 0 && "lg:grid-cols-[minmax(300px,380px)_minmax(0,1fr)]")}>
          {wanted.length > 0 && <SchemeFilter wanted={wanted} usedBy={usedBy} facts={facts} onChange={setFacts} busy={busy} />}

          <div className={cx("flex min-w-0 flex-col gap-8 transition-opacity", busy && "opacity-60")} aria-busy={busy}>
          <p className="text-base text-muted" role="status">
            {t("schemes.counts", {
              eligible: data.counts.eligible,
              check: data.counts.check_with_office,
              not: data.counts.not_eligible,
            })}
          </p>

          {GROUPS.map((status) => {
            const items = data.results.filter((r) => r.status === status);
            if (items.length === 0) return null;
            return (
              <section key={status} className="flex flex-col gap-5" aria-labelledby={`group-${status}`}>
                <h2 id={`group-${status}`} className="text-2xl font-bold tracking-tight">
                  {t(`schemes.group.${status}` as MessageKey)}
                </h2>
                <ul className="grid gap-5 xl:grid-cols-2">
                  {items.map((r) => (
                    <SchemeCard key={r.id} r={r} />
                  ))}
                </ul>
              </section>
            );
          })}

          <p className="text-base text-muted">{t("schemes.nothing")}</p>
          </div>
        </div>
      )}
    </div>
  );
}
