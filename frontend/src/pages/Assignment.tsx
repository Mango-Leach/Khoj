import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { PageBanner } from "../components/PageBanner";
import { ArrowLeft, Camera, CheckCircle2, Hourglass, Loader2, Mic, PhoneCall, RotateCcw, Send, ShieldAlert, Sparkles, Square } from "lucide-react";
import { WorkPhoto } from "../components/WorkPhoto";
import { Button, Notice, cx } from "../components/ui";
import { StatusChip } from "./Assignments";
import {
  ackWork,
  deleteWorkPhoto,
  getAssignmentDetail,
  saveWork,
  sendWork,
  uploadWorkPhoto,
  type AssignmentDetail,
  type AssignmentDoc,
  type Submission,
} from "../lib/api";
import { errorKey } from "../lib/errors";
import { useLang, type MessageKey } from "../lib/i18n";
import { shrinkImage } from "../lib/image";
import { navigate } from "../lib/router";
import { PROBLEM_TEXT, useListener } from "../lib/speech";
import { notInLang, pickText } from "../lib/text";
import { Link } from "../components/Link";

const MAX_PHOTOS = 3;

/** A score from 1 to 4 as four small blocks, with the words next to it. */
export function ScoreMeter({ score }: { score: number }) {
  const { t } = useLang();
  return (
    <span className="inline-flex items-center gap-2" role="img" aria-label={`${score} / 4`}>
      <span className="flex gap-1" aria-hidden="true">
        {[1, 2, 3, 4].map((n) => (
          <span key={n} className={cx("h-2.5 w-6 rounded-full", n <= score ? (score >= 2 ? "bg-ok" : "bg-warn") : "bg-line")} />
        ))}
      </span>
      <span className="text-sm font-semibold text-muted">{t(`scale.${score}` as MessageKey)}</span>
    </span>
  );
}

function Panel({ title, children, tone = "plain" }: { title?: string; children: ReactNode; tone?: "plain" | "ok" | "warn" }) {
  return (
    <section className={cx("flex flex-col gap-4 rounded-2xl p-6 md:p-7", tone === "plain" && "border border-line bg-surface shadow-(--shadow-soft)", tone === "ok" && "bg-ok-bg", tone === "warn" && "bg-warn-bg")}>
      {title && <h2 className="text-2xl font-bold tracking-tight">{title}</h2>}
      {children}
    </section>
  );
}

// ---------------------------------------------------------------------------
// What the mentor said
// ---------------------------------------------------------------------------

function FeedbackCard({ sub, assignment, hasMentor, onChanged }: { sub: Submission; assignment: AssignmentDoc; hasMentor: boolean; onChanged: () => Promise<void> }) {
  const { t, lang } = useLang();
  const review = sub.review;
  const [busy, setBusy] = useState(false);
  if (!review) return null;
  const byAi = review.by_ai;
  const approved = review.decision === "approve" || review.decision === "pass";
  const ack = async (answer: "yes" | "no") => {
    setBusy(true);
    try {
      await ackWork(sub.id, answer);
      await onChanged();
    } finally {
      setBusy(false);
    }
  };
  return (
    <Panel tone={approved ? "ok" : "warn"}>
      <div className={cx("flex items-start gap-3", approved ? "text-ok" : "text-warn")}>
        {approved ? <CheckCircle2 className="mt-0.5 size-7 shrink-0" aria-hidden="true" /> : <RotateCcw className="mt-0.5 size-7 shrink-0" aria-hidden="true" />}
        <div className="flex flex-col gap-0.5">
          <h2 className="text-xl font-bold">
            {byAi ? t(review.decision === "pass" ? "work.ai.passed.title" : review.decision === "feedback" ? "work.ai.tips.title" : "work.ai.returned.title") : approved ? t("work.approved.title") : t("work.returned.title")}
          </h2>
          <p className="text-base">{t("work.attempt", { n: sub.attempt })}</p>
          {byAi && (
            <span className="mt-1 inline-flex items-center gap-1.5 self-start rounded-full bg-tint px-3 py-1 text-sm font-semibold text-accent">
              <Sparkles className="size-4" aria-hidden="true" />
              {t("work.ai.badge")}
            </span>
          )}
        </div>
      </div>
      {review.feedback && (
        <div className="flex flex-col gap-1 rounded-xl bg-surface p-4">
          <h3 className="text-sm font-semibold tracking-wide text-muted uppercase">{t(byAi ? "work.feedback.ai" : "work.feedback")}</h3>
          <p className="text-lg whitespace-pre-line text-ink">{review.feedback}</p>
        </div>
      )}
      <ul className="flex flex-col gap-2.5 rounded-xl bg-surface p-4">
        {assignment.criteria.map((c) => (
          <li key={c.id} className="grid grid-cols-1 items-center gap-x-4 gap-y-1 sm:grid-cols-[minmax(0,1fr)_auto]">
            <span className="text-base text-ink">{pickText(c.text, lang)}</span>
            {review.scores[c.id] == null ? <span className="text-sm font-semibold text-muted">{t("work.ai.notjudged")}</span> : <ScoreMeter score={review.scores[c.id] as number} />}
          </li>
        ))}
      </ul>
      {byAi && (
        <div className="flex flex-col gap-2 rounded-xl bg-tint p-4">
          <p className="text-base text-deep">{t("work.ai.note")}</p>
          {!hasMentor && (
            <Link to="/mentor" className="self-start text-base font-semibold text-accent underline">
              {t("work.ai.connect")}
            </Link>
          )}
        </div>
      )}
      {review.call_needed && (
        <p className="flex items-center gap-2.5 rounded-xl bg-surface p-4 text-lg font-semibold text-deep">
          <PhoneCall className="size-6 shrink-0 text-accent" aria-hidden="true" />
          {t("work.call")}
        </p>
      )}
      {byAi ? null : sub.ack === null ? (
        <div className="flex flex-col gap-2.5 rounded-xl bg-surface p-4">
          <p className="text-lg font-semibold">{t("work.ack.q")}</p>
          <div className="flex gap-3">
            <Button full={false} variant="secondary" className="h-12 px-6 text-base" disabled={busy} onClick={() => void ack("yes")}>
              {t("work.ack.yes")}
            </Button>
            <Button full={false} variant="secondary" className="h-12 px-6 text-base" disabled={busy} onClick={() => void ack("no")}>
              {t("work.ack.no")}
            </Button>
          </div>
        </div>
      ) : (
        <p className="text-base font-semibold text-muted">{t("work.ack.thanks")}</p>
      )}
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// The learner's work
// ---------------------------------------------------------------------------

function Editor({ detail, seed, onChanged }: { detail: AssignmentDetail; seed: Submission | null; onChanged: () => Promise<void> }) {
  const { t, lang } = useLang();
  const latest = detail.submissions.at(-1) ?? null;
  const draft = latest?.status === "draft" ? latest : null;
  const [text, setText] = useState(draft?.text ?? seed?.text ?? "");
  const [via, setVia] = useState<"typed" | "voice">(draft?.via ?? "typed");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<MessageKey | null>(null);
  const [savedNote, setSavedNote] = useState(false);
  const textRef = useRef(text);
  textRef.current = text;

  const listener = useListener(lang, (heard) => {
    setText((prev) => (prev.trim() ? `${prev.trim()} ${heard}` : heard));
    setVia("voice");
  });

  const run = async (key: string, fn: () => Promise<void>) => {
    setBusy(key);
    setError(null);
    setSavedNote(false);
    try {
      await fn();
    } catch (err) {
      setError(errorKey(err));
    } finally {
      setBusy(null);
    }
  };

  const persist = (): Promise<Submission> => saveWork(detail.assignment.id, textRef.current, via);

  const onSave = () =>
    run("save", async () => {
      await persist();
      await onChanged();
      setSavedNote(true);
    });
  const onPhoto = (files: FileList | null) => {
    const file = files?.[0];
    if (!file) return;
    void run("photo", async () => {
      const sub = await persist(); // a photo needs a saved piece of work to belong to
      await uploadWorkPhoto(sub.id, await shrinkImage(file));
      await onChanged();
    });
  };
  const onRemove = (photoId: string) =>
    run(`rm-${photoId}`, async () => {
      if (!draft) return;
      await deleteWorkPhoto(draft.id, photoId);
      await onChanged();
    });
  const onSend = () =>
    run("send", async () => {
      const sub = await persist();
      await sendWork(sub.id);
      await onChanged();
    });

  const photos = draft?.photos ?? [];
  const empty = !text.trim() && photos.length === 0;

  return (
    <Panel title={t("work.yours")}>
      {error && <Notice>{t(error)}</Notice>}
      <label className="flex flex-col gap-2">
        <span className="text-base font-semibold text-ink">{t("work.text.label")}</span>
        <textarea
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            setVia("typed");
          }}
          maxLength={2000}
          rows={6}
          className="w-full resize-y rounded-xl border-[1.5px] border-line-strong bg-surface px-4 py-3 text-lg text-ink outline-none focus:border-accent focus:ring-4 focus:ring-tint-strong"
        />
        <span className="text-sm text-muted">{t("work.text.help")}</span>
      </label>

      {listener.supported && (
        <div className="flex flex-wrap items-center gap-3">
          <Button
            full={false}
            variant="secondary"
            className="h-12 px-5 text-base"
            icon={listener.listening ? <Square className="size-5" /> : <Mic className="size-5" />}
            disabled={listener.busy}
            onClick={listener.listening ? listener.stop : listener.start}
          >
            {listener.listening ? t("intake.mic.stop") : t("work.speak")}
          </Button>
          {listener.listening && <span className="text-base font-semibold text-accent">{listener.heard || t("intake.mic.listening")}</span>}
          {listener.busy && (
            <span className="flex items-center gap-2 text-base text-muted" role="status">
              <Loader2 className="size-5 animate-spin" aria-hidden="true" />
              {t("intake.mic.processing")}
            </span>
          )}
          {listener.problem && (
            <div className="w-full">
              <Notice tone={listener.problem === "nothing" ? "info" : "error"}>{t(PROBLEM_TEXT[listener.problem])}</Notice>
            </div>
          )}
        </div>
      )}

      <div className="flex flex-col gap-2">
        <h3 className="text-base font-semibold text-ink">{t("work.photos")}</h3>
        <ul className="flex flex-wrap items-start gap-3">
          {photos.map((pid) => draft && <WorkPhoto key={pid} submissionId={draft.id} photoId={pid} onRemove={() => void onRemove(pid)} />)}
          {photos.length < MAX_PHOTOS && (
            <li>
              <label
                className={cx(
                  "flex h-[99px] w-[132px] cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border-[1.5px] border-dashed border-line-strong bg-surface text-center text-sm font-semibold text-accent hover:border-accent",
                  busy === "photo" && "pointer-events-none opacity-60",
                )}
              >
                {busy === "photo" ? <Loader2 className="size-6 animate-spin" aria-hidden="true" /> : <Camera className="size-6" aria-hidden="true" />}
                {busy === "photo" ? t("assess.photo.uploading") : t("assess.photo.add")}
                <input
                  type="file"
                  accept="image/jpeg,image/png"
                  capture="environment"
                  className="sr-only"
                  onChange={(e) => {
                    onPhoto(e.target.files);
                    e.target.value = "";
                  }}
                />
              </label>
            </li>
          )}
        </ul>
        <p className="text-sm text-muted">{t("work.photos.help", { n: MAX_PHOTOS })}</p>
      </div>

      <div className="flex flex-wrap items-center gap-3 border-t border-line pt-5">
        <Button full={false} variant="secondary" className="h-12 px-6 text-base" loading={busy === "save"} disabled={busy !== null || empty} onClick={() => void onSave()}>
          {t("work.save")}
        </Button>
        <Button full={false} className="h-12 px-6 text-base" icon={<Send className="size-5" />} loading={busy === "send"} disabled={busy !== null || empty} onClick={() => void onSend()}>
          {t(detail.has_mentor ? "work.send" : "work.send.ai")}
        </Button>
        {savedNote && <span className="text-base font-semibold text-ok">{t("work.saved")}</span>}
      </div>
      {busy === "send" && !detail.has_mentor && (
        <p className="flex items-center gap-2 text-base text-muted" role="status">
          <Loader2 className="size-5 animate-spin" aria-hidden="true" />
          {t("work.ai.wait")}
        </p>
      )}
      {!detail.has_mentor && (
        <div className="flex flex-col gap-2 rounded-xl bg-tint p-4">
          <p className="text-base text-deep">{t("work.send.nomentor")}</p>
          <Link to="/mentor" className="self-start text-base font-semibold text-accent underline">
            {t("home.path.cta.mentorFind")}
          </Link>
        </div>
      )}
    </Panel>
  );
}

function SentCard({ sub }: { sub: Submission }) {
  const { t } = useLang();
  return (
    <Panel tone="warn">
      <div className="flex items-start gap-3 text-warn">
        <Hourglass className="mt-0.5 size-7 shrink-0" aria-hidden="true" />
        <div className="flex flex-col gap-0.5">
          <h2 className="text-xl font-bold">{t("work.sent.title")}</h2>
          <p className="text-base">{t("work.sent.help")}</p>
        </div>
      </div>
      <div className="flex flex-col gap-3 rounded-xl bg-surface p-4">
        {sub.text && <p className="text-lg whitespace-pre-line text-ink">{sub.text}</p>}
        {sub.photos.length > 0 && (
          <ul className="flex flex-wrap gap-3">
            {sub.photos.map((pid) => (
              <WorkPhoto key={pid} submissionId={sub.id} photoId={pid} />
            ))}
          </ul>
        )}
      </div>
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function AssignmentPage({ assignmentId }: { assignmentId: string }) {
  const { t, lang } = useLang();
  const [detail, setDetail] = useState<AssignmentDetail | null>(null);
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    try {
      setDetail(await getAssignmentDetail(assignmentId));
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, [assignmentId]);
  useEffect(() => {
    void load();
  }, [load]);

  const back = (
    <button type="button" onClick={() => navigate("/assignments")} className="inline-flex items-center gap-2 self-start text-base font-semibold text-accent hover:underline">
      <ArrowLeft className="size-5" aria-hidden="true" />
      {t("work.back")}
    </button>
  );

  if (!detail) {
    return (
      <div className="flex flex-col gap-4 pt-2">
        {back}
        {failed ? <Notice>{t("err.network")}</Notice> : <Loader2 className="size-6 animate-spin text-accent" aria-label={t("req.loading")} />}
      </div>
    );
  }

  const a = detail.assignment;
  const subs = detail.submissions;
  const latest = subs.at(-1) ?? null;
  const lastReviewed = [...subs].reverse().find((s) => s.review) ?? null;
  const earlier = subs.filter((s) => s.review && s !== lastReviewed);
  const hazardous = detail.career.safety_class === "high";

  return (
    <div className="flex flex-col gap-5 pt-2">
      {back}
      <PageBanner title={pickText(a.title, lang)} aside={<StatusChip status={latest?.status ?? "none"} />} />
      {notInLang(a.title, lang) && <p className="text-sm text-muted">{t("work.writtenIn")}</p>}

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
        <div className="flex flex-col gap-5">
          <Panel title={t("work.task")}>
            <p className="text-lg whitespace-pre-line text-ink">{pickText(a.instructions, lang)}</p>
            {hazardous && (
              <p className="flex items-start gap-2.5 rounded-xl bg-warn-bg p-4 text-base font-semibold text-warn">
                <ShieldAlert className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
                {t("work.safety")}
              </p>
            )}
          </Panel>
          <Panel title={t("work.looks")}>
            <ul className="flex flex-col gap-2.5">
              {a.criteria.map((c) => (
                <li key={c.id} className="flex items-start gap-2.5 text-lg">
                  <CheckCircle2 className="mt-1 size-5 shrink-0 text-accent" aria-hidden="true" />
                  {pickText(c.text, lang)}
                </li>
              ))}
            </ul>
          </Panel>
        </div>

        <div className="flex flex-col gap-5">
          {lastReviewed && <FeedbackCard key={lastReviewed.id + String(lastReviewed.ack)} sub={lastReviewed} assignment={a} hasMentor={detail.has_mentor} onChanged={load} />}
          {latest?.status === "submitted" && <SentCard sub={latest} />}
          {detail.can_work && <Editor key={latest?.id ?? "new"} detail={detail} seed={latest?.status === "returned" || latest?.status === "ai_returned" ? latest : null} onChanged={load} />}
          {earlier.length > 0 && (
            <details className="rounded-[28px] border border-line bg-surface p-5">
              <summary className="cursor-pointer text-lg font-semibold">{t("work.history")}</summary>
              <ul className="mt-3 flex flex-col gap-3">
                {earlier.map((s) => (
                  <li key={s.id} className="flex flex-col gap-1 rounded-xl bg-bg p-4">
                    <p className="text-base font-semibold">{t("work.attempt", { n: s.attempt })}</p>
                    <p className="text-base text-muted">{s.review?.feedback}</p>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      </div>
    </div>
  );
}
