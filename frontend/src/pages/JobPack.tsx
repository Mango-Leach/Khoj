import { useEffect, useState } from "react";
import { PageBanner } from "../components/PageBanner";
import { ExternalLink, FileCheck2, GraduationCap, Loader2, MessageSquare, ShieldAlert, Route } from "lucide-react";
import { pick } from "../components/Eligibility";
import { ListenButton } from "../components/ListenButton";
import { Button, Notice } from "../components/ui";
import { getJobPack, isApiFailure, type JobPack } from "../lib/api";
import { errorKey } from "../lib/errors";
import { useLang, type MessageKey } from "../lib/i18n";
import { navigate } from "../lib/router";
import { useJourney } from "../lib/usePaths";

function Section({ icon, title, children, id }: { icon: React.ReactNode; title: string; children: React.ReactNode; id: string }) {
  return (
    <section className="flex flex-col gap-4 rounded-[28px] border border-line bg-surface p-6 shadow-(--shadow-soft)" aria-labelledby={id}>
      <h2 id={id} className="flex items-center gap-3 text-xl font-bold tracking-tight">
        <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-tint text-accent" aria-hidden="true">
          {icon}
        </span>
        {title}
      </h2>
      {children}
    </section>
  );
}

/** What a learner who finished the path needs for the next step. Built only from sources KHOJ has already cited. */
export function JobPackPage({ careerId: fixed }: { careerId?: string }) {
  const { t, lang } = useLang();
  const { journey, loaded } = useJourney();
  const [pack, setPack] = useState<JobPack | null>(null);
  const [locked, setLocked] = useState(false);
  const [error, setError] = useState<MessageKey | null>(null);

  const careerId = fixed ?? journey?.career.career_id;
  useEffect(() => {
    if (!careerId) return;
    let alive = true;
    getJobPack(careerId)
      .then((p) => alive && setPack(p))
      .catch((err) => {
        if (!alive) return;
        if (isApiFailure(err) && err.code === "pack_locked") setLocked(true);
        else setError(errorKey(err));
      });
    return () => {
      alive = false;
    };
  }, [careerId]);

  const heading = (
    <PageBanner title={t("pack.title")} lead={t("pack.lead")} />
  );

  if ((loaded && !journey && !fixed) || locked) {
    return (
      <div className="flex max-w-2xl flex-col items-start gap-4 pt-2">
        {heading}
        <p className="text-lg text-muted">{t("pack.locked")}</p>
        <Button full={false} onClick={() => navigate("/assignments")}>
          {t("opp.locked.cta")}
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8 pt-2">
      {heading}
      {error && <Notice>{t(error)}</Notice>}
      {!pack && !error && (
        <div className="flex items-center gap-3 text-lg text-muted" role="status">
          <Loader2 className="size-6 animate-spin text-accent" aria-hidden="true" />
          {t("req.loading")}
        </div>
      )}
      {pack && (
        <>
          {pack.safety.in_person_check_needed && (
            <section className="flex gap-4 rounded-[28px] border border-warn/40 bg-warn-bg p-5" role="note">
              <ShieldAlert className="mt-0.5 size-7 shrink-0 text-warn" aria-hidden="true" />
              <div className="flex flex-col gap-1">
                <h2 className="text-lg font-bold">{t("opp.person.title")}</h2>
                <p className="text-base">{t("opp.person.help")}</p>
              </div>
            </section>
          )}

          <div className="grid items-start gap-6 lg:grid-cols-2">
            <Section id="pack-docs" icon={<FileCheck2 className="size-5" />} title={t("pack.docs")}>
              {pack.documents.asked.length > 0 && (
                <div className="flex flex-col gap-1.5">
                  <p className="text-sm font-semibold tracking-wide text-deep uppercase">{t("pack.docs.asked")}</p>
                  <ul className="list-disc pl-6 text-base">
                    {pack.documents.asked.map((d) => (
                      <li key={d}>{t(`schemes.doc.${d}` as MessageKey)}</li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="flex flex-col gap-1.5">
                <p className="text-sm font-semibold tracking-wide text-deep uppercase">{t("pack.docs.usual")}</p>
                <ul className="list-disc pl-6 text-base">
                  {pack.documents.usual.map((d) => (
                    <li key={d}>{t(`schemes.doc.${d}` as MessageKey)}</li>
                  ))}
                </ul>
                <p className="text-sm text-muted">{t("pack.docs.usual.help")}</p>
              </div>
            </Section>

            <Section id="pack-pitch" icon={<MessageSquare className="size-5" />} title={t("pack.pitch")}>
              <p className="text-base text-muted">{t("pack.pitch.help")}</p>
              <ol className="flex list-decimal flex-col gap-2 pl-6 text-lg">
                {pack.pitch.map((q) => (
                  <li key={q}>{t(`pack.pitch.${q}` as MessageKey)}</li>
                ))}
              </ol>
            </Section>

            <Section id="pack-steps" icon={<Route className="size-5" />} title={t("pack.steps")}>
              <ul className="flex flex-col gap-4">
                {pack.steps.map((s) => {
                  const title = pick(s.title, lang);
                  const how = pick(s.how, lang);
                  return (
                    <li key={s.opportunity_id} className="flex flex-col gap-1.5 border-b border-line pb-4 last:border-0 last:pb-0">
                      <h3 className="text-lg font-bold">{title.text}</h3>
                      <p className="text-base">{how.text}</p>
                      <div className="flex flex-wrap items-center gap-x-5 gap-y-1">
                        <a href={s.apply_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 text-base font-semibold text-accent underline">
                          {t("opp.visit")}
                          <ExternalLink className="size-4" aria-hidden="true" />
                        </a>
                        <a href={s.source.url} target="_blank" rel="noopener noreferrer" className="text-sm text-muted underline">
                          {t("pack.source")}
                        </a>
                        {!s.source.verified_on && <span className="text-sm font-semibold text-warn">{t("paths.source.awaiting")}</span>}
                      </div>
                    </li>
                  );
                })}
              </ul>
              {lang !== "en" && pack.machine_translated.includes(lang) && <span className="text-sm text-muted">{t("paths.machine")}</span>}
            </Section>

            {(pack.courses.length > 0 || pack.learn_links.length > 0) && (
              <Section id="pack-next" icon={<GraduationCap className="size-5" />} title={t("pack.next")}>
                <ul className="flex flex-col gap-3">
                  {pack.courses.map((c) => (
                    <li key={c.id}>
                      <a href={c.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-start gap-2 text-base font-semibold text-accent underline">
                        <span>
                          {c.title} <span className="font-normal text-muted">({c.provider})</span>
                        </span>
                        <ExternalLink className="mt-1 size-4 shrink-0" aria-hidden="true" />
                      </a>
                    </li>
                  ))}
                  {pack.learn_links.map((c) => (
                    <li key={c.url}>
                      <a href={c.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-start gap-2 text-base font-semibold text-accent underline">
                        <span>
                          {c.title} <span className="font-normal text-muted">({c.provider})</span>
                        </span>
                        <ExternalLink className="mt-1 size-4 shrink-0" aria-hidden="true" />
                      </a>
                    </li>
                  ))}
                </ul>
              </Section>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-4">
            <ListenButton text={[t("pack.title"), ...pack.pitch.map((q) => t(`pack.pitch.${q}` as MessageKey))].join(". ")} />
            <p className="max-w-3xl text-sm text-muted">{t("pack.note")}</p>
          </div>
        </>
      )}
    </div>
  );
}
