import { useEffect, useState } from "react";
import { PageBanner } from "../components/PageBanner";
import { Briefcase, CheckCircle2, ChevronRight, Circle, GraduationCap, Hourglass, Loader2, Lock, PencilLine, PhoneCall, RotateCcw, Send, Sparkles } from "lucide-react";
import { Link } from "../components/Link";
import { Button, Notice, cx } from "../components/ui";
import { completeJourney, getMilestones, getOpportunities, type MilestoneAssignment, type MilestonesView, type SubmissionStatus } from "../lib/api";
import { errorKey } from "../lib/errors";
import { useLang, type MessageKey } from "../lib/i18n";
import { navigate } from "../lib/router";
import { pickText } from "../lib/text";
import { useJourney } from "../lib/usePaths";

export function statusOf(a: MilestoneAssignment): SubmissionStatus | "none" {
  return a.submission?.status ?? "none";
}

const STATUS_STYLE: Record<SubmissionStatus | "none", { icon: typeof Circle; tone: string }> = {
  none: { icon: Circle, tone: "bg-bg text-muted" },
  draft: { icon: PencilLine, tone: "bg-tint text-accent" },
  submitted: { icon: Send, tone: "bg-warn-bg text-warn" },
  approved: { icon: CheckCircle2, tone: "bg-ok-bg text-ok" },
  returned: { icon: RotateCcw, tone: "bg-warn-bg text-warn" },
  ai_passed: { icon: Sparkles, tone: "bg-tint text-accent" },
  ai_returned: { icon: RotateCcw, tone: "bg-warn-bg text-warn" },
};

export function StatusChip({ status }: { status: SubmissionStatus | "none" }) {
  const { t } = useLang();
  const { icon: Icon, tone } = STATUS_STYLE[status];
  return (
    <span className={cx("inline-flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1 text-sm font-semibold", tone)}>
      <Icon className="size-4" aria-hidden="true" />
      {t(`work.status.${status}` as MessageKey)}
    </span>
  );
}

function Banner({ view }: { view: MilestonesView }) {
  const { t } = useLang();
  if (view.has_mentor) return null;
  const pending = view.journey_state === "mentor_pending";
  return (
    <section className="flex flex-col gap-3 rounded-[28px] bg-tint px-6 py-5 text-deep sm:flex-row sm:items-center sm:gap-4" aria-labelledby="mentor-banner">
      {pending ? <Hourglass className="size-7 shrink-0 text-accent" aria-hidden="true" /> : <GraduationCap className="size-7 shrink-0 text-accent" aria-hidden="true" />}
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <h2 id="mentor-banner" className="text-lg font-bold text-deep">
          {pending ? t("work.banner.pending.title") : t("work.banner.title")}
        </h2>
        <p className="text-base text-deep">{pending ? t("work.banner.pending.help") : t("work.banner.help")}</p>
      </div>
      <Button full={false} className="h-11 text-base" onClick={() => navigate("/mentor")}>
        {pending ? t("work.banner.pending.cta") : t("home.path.cta.mentorFind")}
      </Button>
    </section>
  );
}

const FINISHED = ["completed", "opportunities_open", "enrolled"];

/** Once every step is approved the learner finishes the path, which opens opportunities. Finishing again changes nothing. */
function FinishCard({ view, onDone }: { view: MilestonesView; onDone: (state: MilestonesView["journey_state"]) => void }) {
  const { t } = useLang();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<MessageKey | null>(null);
  const finished = FINISHED.includes(view.journey_state);
  const allDone = view.milestones.length > 0 && view.milestones.every((m) => m.state === "done");
  if (!finished && !(allDone && view.has_mentor)) return null;

  const finish = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await completeJourney(view.journey_id);
      onDone(r.state);
      navigate("/opportunities");
    } catch (err) {
      setError(errorKey(err));
      setBusy(false);
    }
  };

  return (
    <section className="flex flex-col gap-3 rounded-[28px] bg-tint px-6 py-5 text-deep sm:flex-row sm:items-center sm:gap-4" aria-labelledby="finish-card">
      {finished ? <Briefcase className="size-7 shrink-0 text-accent" aria-hidden="true" /> : <CheckCircle2 className="size-7 shrink-0 text-accent" aria-hidden="true" />}
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <h2 id="finish-card" className="text-lg font-bold text-deep">
          {finished ? t("fin.done.title") : t("fin.title")}
        </h2>
        <p className="text-base text-deep">{finished ? t("fin.done.help") : t("fin.help")}</p>
        {error && <p className="text-base font-semibold text-bad">{t(error)}</p>}
      </div>
      {finished ? (
        <Button full={false} className="h-11 text-base" onClick={() => navigate("/opportunities")}>
          {t("fin.done.cta")}
        </Button>
      ) : (
        <Button full={false} className="h-11 text-base" loading={busy} onClick={() => void finish()}>
          {t("fin.cta")}
        </Button>
      )}
    </section>
  );
}

/** Tells the learner that more opportunities open as their mentor approves steps. It says nothing if it cannot load. */
function OpportunitiesTeaser({ journeyId, state }: { journeyId: string; state: MilestonesView["journey_state"] }) {
  const { t } = useLang();
  const [locked, setLocked] = useState(0);
  useEffect(() => {
    if (FINISHED.includes(state)) return;
    let alive = true;
    getOpportunities()
      .then((d) => alive && setLocked(d.unlock.finished ? 0 : d.unlock.locked))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [journeyId, state]);
  if (locked === 0 || FINISHED.includes(state)) return null;
  return (
    <section className="flex flex-col gap-3 rounded-[28px] bg-tint px-6 py-5 text-deep sm:flex-row sm:items-center sm:gap-4" aria-labelledby="teaser-card">
      <Lock className="size-7 shrink-0 text-accent" aria-hidden="true" />
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <h2 id="teaser-card" className="text-lg font-bold text-deep">
          {t("assign.unlock.title")}
        </h2>
        <p className="text-base text-deep">{t("assign.unlock.help", { count: locked })}</p>
      </div>
      <Button full={false} className="h-11 text-base" onClick={() => navigate("/opportunities")}>
        {t("assign.unlock.cta")}
      </Button>
    </section>
  );
}

export function AssignmentsPage() {
  const { t, lang } = useLang();
  const { journey, loaded } = useJourney();
  const [view, setView] = useState<MilestonesView | null>(null);
  const [failed, setFailed] = useState(false);

  const jid = journey?.id;
  useEffect(() => {
    if (!jid) return;
    let alive = true;
    getMilestones(jid)
      .then((v) => alive && setView(v))
      .catch(() => alive && setFailed(true));
    return () => {
      alive = false;
    };
  }, [jid]);

  if (loaded && !journey) {
    return (
      <div className="flex flex-col items-start gap-6 pt-2">
        <div className="w-full">
          <PageBanner title={t("work.title")} lead={t("work.nopath.help")} />
        </div>
        <Button full={false} onClick={() => navigate("/paths")}>
          {t("mentor.none.cta")}
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 pt-2">
      <PageBanner title={t("work.title")} lead={journey ? t("work.lead", { career: pickText(journey.career.name, lang) }) : undefined} />
      {failed && <Notice>{t("err.network")}</Notice>}
      {!view && !failed && (
        <div className="flex items-center gap-3 text-lg text-muted" role="status">
          <Loader2 className="size-6 animate-spin text-accent" aria-hidden="true" />
          {t("req.loading")}
        </div>
      )}
      {view && (
        <>
          <Banner view={view} />
          <FinishCard view={view} onDone={(state) => setView((v) => (v ? { ...v, journey_state: state } : v))} />
          <OpportunitiesTeaser journeyId={view.journey_id} state={view.journey_state} />
          <ol className="grid gap-5 lg:grid-cols-3">
            {view.milestones.map((m, i) => (
              <li key={m.key} className="flex flex-col gap-4 rounded-[28px] border border-line bg-surface p-6 shadow-(--shadow-soft)">
                <div className="flex items-start gap-3.5">
                  <span className={cx("grid size-11 shrink-0 place-items-center rounded-xl text-lg font-bold", m.state === "done" ? "bg-ok-bg text-ok" : "bg-tint text-accent")} aria-hidden="true">
                    {m.state === "done" ? <CheckCircle2 className="size-6" /> : i + 1}
                  </span>
                  <div className="flex min-w-0 flex-col gap-0.5">
                    <h2 className="text-xl leading-tight font-bold">{pickText(m.title, lang)}</h2>
                    <p className="text-[15px] font-semibold text-muted">{t("work.ms.progress", { done: m.done, total: m.total })}</p>
                  </div>
                </div>
                <p className="text-base text-muted">{pickText(m.detail, lang)}</p>
                <ul className="mt-auto flex flex-col gap-2.5">
                  {m.assignments.map((a) => (
                    <li key={a.id}>
                      <Link
                        to={`/assignments/${a.id}`}
                        className="flex items-center gap-3 rounded-xl border border-line px-4 py-3 transition-colors hover:border-accent hover:bg-tint"
                      >
                        <div className="flex min-w-0 flex-1 flex-col gap-1.5">
                          <span className="text-lg leading-snug font-semibold">{pickText(a.title, lang)}</span>
                          <span className="flex flex-wrap items-center gap-2">
                            <StatusChip status={statusOf(a)} />
                            {a.submission?.call_needed && (
                              <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-warn">
                                <PhoneCall className="size-4" aria-hidden="true" />
                                {t("work.call.short")}
                              </span>
                            )}
                          </span>
                        </div>
                        <ChevronRight className="size-5 shrink-0 text-muted" aria-hidden="true" />
                      </Link>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ol>
        </>
      )}
    </div>
  );
}
