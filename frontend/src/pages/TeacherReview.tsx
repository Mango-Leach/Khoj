import { useCallback, useEffect, useState } from "react";
import { PageBanner } from "../components/PageBanner";
import { CheckCircle2, ClipboardCheck, Inbox, Loader2, Sparkles, ShieldAlert } from "lucide-react";
import { WorkPhoto } from "../components/WorkPhoto";
import { Button, Notice, cx } from "../components/ui";
import { aiScoreDraft, getReviewQueue, getSubmissionDetail, reviewWork, type AiScoreDraft, type QueueItem, type SubmissionDetail } from "../lib/api";
import { errorKey } from "../lib/errors";
import { useLang, type MessageKey } from "../lib/i18n";
import { pickText, waited } from "../lib/text";

const SCORES = [1, 2, 3, 4] as const;
const PASS = 2;

function Waited({ iso }: { iso: string }) {
  const { t } = useLang();
  const w = waited(iso);
  return <>{w.days >= 1 ? t("rv.waited.days", { n: w.days }) : w.hours >= 1 ? t("rv.waited.hours", { n: w.hours }) : t("rv.waited.new")}</>;
}

function Detail({ item, onDone }: { item: QueueItem; onDone: (approved: boolean) => void }) {
  const { t, lang } = useLang();
  const [detail, setDetail] = useState<SubmissionDetail | null>(null);
  const [failed, setFailed] = useState(false);
  const [scores, setScores] = useState<Record<string, number>>({});
  const [feedback, setFeedback] = useState("");
  const [ai, setAi] = useState<AiScoreDraft | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<MessageKey | null>(null);

  useEffect(() => {
    let alive = true;
    setDetail(null);
    setScores({});
    setFeedback("");
    setAi(null);
    setError(null);
    getSubmissionDetail(item.id)
      .then((d) => {
        if (!alive) return;
        setDetail(d);
        setAi(d.submission.ai_draft ?? null);
      })
      .catch(() => alive && setFailed(true));
    return () => {
      alive = false;
    };
  }, [item.id]);

  if (!detail) {
    return failed ? <Notice>{t("err.network")}</Notice> : <Loader2 className="size-6 animate-spin text-accent" aria-label={t("req.loading")} />;
  }

  const { submission: sub, assignment, career } = detail;
  const criteria = assignment.criteria;
  const allScored = criteria.every((c) => scores[c.id] !== undefined);
  const canApprove = allScored && criteria.every((c) => (scores[c.id] ?? 0) >= PASS);
  const canReturn = allScored && feedback.trim().length >= 3;
  const hazardous = career.safety_class === "high";

  const askAi = async () => {
    setBusy("ai");
    setError(null);
    try {
      setAi(await aiScoreDraft(sub.id));
    } catch (err) {
      setError(errorKey(err));
    } finally {
      setBusy(null);
    }
  };

  const decide = async (decision: "approve" | "return") => {
    setBusy(decision);
    setError(null);
    try {
      await reviewWork(sub.id, { decision, scores, feedback: feedback.trim() });
      onDone(decision === "approve");
    } catch (err) {
      setError(errorKey(err));
      setBusy(null);
    }
  };

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-1">
        <h2 className="text-2xl leading-tight font-bold tracking-tight">{pickText(assignment.title, lang)}</h2>
        <p className="text-base text-muted">
          {t("rv.from", { name: item.student.name })} · {t("work.attempt", { n: sub.attempt })} · <Waited iso={item.sent_at} />
        </p>
      </div>
      {error && <Notice>{t(error)}</Notice>}
      {hazardous && (
        <p className="flex items-start gap-2.5 rounded-xl bg-warn-bg p-4 text-base font-semibold text-warn">
          <ShieldAlert className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
          {t("rv.safety")}
        </p>
      )}

      <section className="flex flex-col gap-3 rounded-[28px] border border-line bg-surface p-5">
        <h3 className="text-lg font-bold">{t("rv.answer")}</h3>
        {sub.text ? <p className="text-lg whitespace-pre-line text-ink">{sub.text}</p> : <p className="text-base text-muted">{t("rv.noanswer")}</p>}
        {sub.via === "voice" && <p className="text-sm font-semibold text-muted">{t("rv.voice")}</p>}
        {sub.photos.length > 0 && (
          <ul className="flex flex-wrap gap-3">
            {sub.photos.map((pid) => (
              <WorkPhoto key={pid} submissionId={sub.id} photoId={pid} size="large" />
            ))}
          </ul>
        )}
      </section>

      <section className="flex flex-col gap-4 rounded-[28px] border border-line bg-surface p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-lg font-bold">{t("rv.score")}</h3>
          {sub.audit_sample ? (
            <p className="text-sm font-semibold text-muted">{t("rv.ai.hidden")}</p>
          ) : (
            <Button full={false} variant="secondary" className="h-10 px-4 text-[15px]" icon={<Sparkles className="size-4" />} loading={busy === "ai"} disabled={busy !== null} onClick={() => void askAi()}>
              {ai ? t("rv.ai.again") : t("rv.ai.ask")}
            </Button>
          )}
        </div>
        {ai && <p className="text-sm text-muted">{t("rv.ai.note")}</p>}
        <ul className="flex flex-col gap-4">
          {criteria.map((c) => {
            const suggested = ai?.scores[c.id];
            return (
              <li key={c.id} className="flex flex-col gap-2">
                <p className="text-lg font-semibold">{pickText(c.text, lang)}</p>
                <div className="flex flex-wrap items-center gap-3">
                  <div role="radiogroup" aria-label={pickText(c.text, lang)} className="flex gap-2">
                    {SCORES.map((n) => {
                      const on = scores[c.id] === n;
                      return (
                        <button
                          key={n}
                          type="button"
                          role="radio"
                          aria-checked={on}
                          onClick={() => setScores((prev) => ({ ...prev, [c.id]: n }))}
                          className={cx(
                            "flex min-w-[76px] flex-col items-center rounded-xl border-[1.5px] px-3 py-1.5 transition-colors",
                            on ? (n >= PASS ? "border-ok bg-ok-bg text-ok" : "border-warn bg-warn-bg text-warn") : "border-line-strong bg-surface hover:border-accent",
                          )}
                        >
                          <span className="text-lg leading-tight font-bold">{n}</span>
                          <span className="text-xs font-semibold">{t(`scale.${n}` as MessageKey)}</span>
                        </button>
                      );
                    })}
                  </div>
                  {ai && (
                    <span className="flex items-center gap-2 text-sm text-muted">
                      {typeof suggested === "number" ? (
                        <>
                          {t("rv.ai.suggests", { n: suggested })}
                          <button type="button" onClick={() => setScores((prev) => ({ ...prev, [c.id]: suggested }))} className="font-semibold text-accent underline">
                            {t("rv.agree")}
                          </button>
                        </>
                      ) : (
                        t("rv.ai.unjudged")
                      )}
                    </span>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      </section>

      <section className="flex flex-col gap-3 rounded-[28px] border border-line bg-surface p-5">
        <label className="flex flex-col gap-1.5">
          <span className="text-lg font-bold">{t("rv.feedback")}</span>
          <span className="text-sm text-muted">{t("rv.feedback.help")}</span>
          <textarea
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            maxLength={1200}
            rows={4}
            className="w-full resize-y rounded-xl border-[1.5px] border-line-strong bg-surface px-4 py-3 text-lg text-ink outline-none focus:border-accent focus:ring-4 focus:ring-tint-strong"
          />
        </label>
        {ai?.feedback && (
          <button type="button" onClick={() => setFeedback(ai.feedback)} className="self-start text-sm font-semibold text-accent underline">
            {t("rv.ai.useFeedback")}
          </button>
        )}
        <div className="flex flex-wrap items-center gap-3 border-t border-line pt-4">
          <Button full={false} className="h-12 px-6 text-base" icon={<CheckCircle2 className="size-5" />} loading={busy === "approve"} disabled={!canApprove || busy !== null} onClick={() => void decide("approve")}>
            {t("rv.approve")}
          </Button>
          <Button full={false} variant="secondary" className="h-12 px-6 text-base" loading={busy === "return"} disabled={!canReturn || busy !== null} onClick={() => void decide("return")}>
            {t("rv.return")}
          </Button>
        </div>
        <p className="text-sm text-muted" role="status">
          {!allScored ? t("rv.needAll") : !canApprove ? t("rv.cantApprove") : !canReturn ? t("rv.needFeedback") : ""}
        </p>
      </section>
    </div>
  );
}

export function TeacherReviewPage() {
  const { t, lang } = useLang();
  const [items, setItems] = useState<QueueItem[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [done, setDone] = useState<MessageKey | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await getReviewQueue();
      setItems(r.items);
      setSelected((cur) => (cur && r.items.some((i) => i.id === cur) ? cur : (r.items[0]?.id ?? null)));
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  const item = items?.find((i) => i.id === selected) ?? null;

  return (
    <div className="flex flex-col gap-6 pt-2 lg:-mb-10 lg:h-[calc(100dvh-92px)] lg:gap-5">
      <PageBanner title={t("rv.title")} lead={t("rv.lead")} />
      {failed && <Notice>{t("err.network")}</Notice>}
      {done && <Notice tone="info">{t(done)}</Notice>}
      {!items && !failed && (
        <div className="flex items-center gap-3 text-lg text-muted" role="status">
          <Loader2 className="size-6 animate-spin text-accent" aria-hidden="true" />
          {t("req.loading")}
        </div>
      )}
      {items && items.length === 0 && (
        <section className="flex max-w-3xl gap-4 rounded-[28px] border border-line bg-surface p-7 shadow-(--shadow-soft)">
          <Inbox className="mt-1 size-7 shrink-0 text-accent" aria-hidden="true" />
          <p className="text-lg text-muted">{t("rv.empty")}</p>
        </section>
      )}
      {items && items.length > 0 && (
        <div className="grid items-start gap-6 lg:min-h-0 lg:flex-1 lg:grid-cols-[320px_minmax(0,1fr)] lg:grid-rows-1 lg:items-stretch">
          <nav aria-label={t("rv.queue")} className="lg:relative lg:-mx-1 lg:min-h-0 lg:overflow-y-auto lg:px-1 lg:pb-2">
            <h2 className="mb-2 text-sm font-semibold tracking-wide text-muted uppercase">{t("rv.queue")}</h2>
            <ul className="flex flex-col gap-2">
              {items.map((i) => {
                const on = i.id === selected;
                return (
                  <li key={i.id}>
                    <button
                      type="button"
                      onClick={() => {
                        setSelected(i.id);
                        setDone(null);
                      }}
                      aria-current={on ? "true" : undefined}
                      className={cx("flex w-full flex-col gap-0.5 rounded-xl border px-4 py-3 text-left transition-colors", on ? "border-accent bg-tint" : "border-line bg-surface hover:border-accent")}
                    >
                      <span className="flex items-center gap-2 text-lg leading-snug font-semibold">
                        <ClipboardCheck className="size-5 shrink-0 text-accent" aria-hidden="true" />
                        {pickText(i.assignment.title, lang)}
                      </span>
                      <span className="text-[15px] text-muted">
                        {i.student.name} · {t("work.attempt", { n: i.attempt })}
                      </span>
                      <span className="text-sm font-semibold text-warn">
                        <Waited iso={i.sent_at} />
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </nav>
          <div className="lg:relative lg:-mx-1 lg:min-h-0 lg:overflow-y-auto lg:px-1 lg:pb-2">
            {item ? (
              <Detail
                key={item.id}
                item={item}
                onDone={(approved) => {
                  setDone(approved ? "rv.done.approved" : "rv.done.returned");
                  void load();
                }}
              />
            ) : (
              <p className="text-lg text-muted">{t("rv.pick")}</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
