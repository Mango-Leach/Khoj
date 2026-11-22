import { useCallback, useEffect, useState } from "react";
import { Keyboard, Loader2, Mic, Square } from "lucide-react";
import { ListenButton } from "../components/ListenButton";
import { Button, Notice, cx } from "../components/ui";
import {
  completeIntake,
  confirmAnswer,
  getIntakeQuestions,
  getLatestIntake,
  isApiFailure,
  type AnswerSource,
  type IntakeQuestion,
  type IntakeSession,
} from "../lib/api";
import { errorKey } from "../lib/errors";
import { useLang, type Lang } from "../lib/i18n";
import { navigate } from "../lib/router";
import { PROBLEM_TEXT, useListener } from "../lib/speech";

interface Draft {
  text: string;
  heard: string; // what the recogniser returned, to tell whether the learner edited it
  source: AnswerSource;
  lang: Lang;
}

function Progress({ n, total }: { n: number; total: number }) {
  const { t } = useLang();
  return (
    <div className="flex flex-col gap-2">
      <p className="text-base font-semibold text-muted">{t("intake.step", { n, total })}</p>
      <div
        className="h-2 overflow-hidden rounded-full bg-tint-strong"
        role="progressbar"
        aria-valuemin={1}
        aria-valuemax={total}
        aria-valuenow={n}
        aria-label={t("intake.step", { n, total })}
      >
        <div className="h-full rounded-full bg-accent transition-[width] duration-300" style={{ width: `${(n / total) * 100}%` }} />
      </div>
    </div>
  );
}

const BAR_SHAPE = [0.55, 0.8, 1, 0.7, 0.9, 0.6, 0.75];

/** Moving bars. With a real loudness (server recording) they follow the voice; otherwise they just pulse. */
function Wave({ level }: { level?: number }) {
  return (
    <span className="flex h-10 items-center gap-1" aria-hidden="true">
      {BAR_SHAPE.map((shape, i) =>
        level === undefined ? (
          <span key={i} className="wave-bar block h-full w-1.5 rounded-full bg-accent" style={{ ["--d" as string]: `${i * 90}ms` }} />
        ) : (
          <span
            key={i}
            className="block h-full w-1.5 rounded-full bg-accent transition-transform duration-100"
            style={{ transform: `scaleY(${Math.max(0.15, Math.min(1, 0.15 + level * shape))})` }}
          />
        ),
      )}
    </span>
  );
}

/** One spoken or typed answer: ask, then confirm back, then send. */
function OpenAnswer({ question, onConfirm, busy }: { question: IntakeQuestion; onConfirm: (d: Draft) => void; busy: boolean }) {
  const { t, lang } = useLang();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [typed, setTyped] = useState("");
  const listener = useListener(lang, (text, via) => setDraft({ text, heard: text, source: via === "server" ? "gnani" : "browser_asr", lang }));

  const useTyped = () => {
    const text = typed.trim();
    if (text) setDraft({ text, heard: "", source: "typed", lang });
  };

  if (draft) {
    const edited = draft.text.trim() !== draft.heard.trim();
    const final: Draft = { ...draft, text: draft.text.trim(), source: (draft.source === "browser_asr" || draft.source === "gnani") && edited ? "typed" : draft.source };
    return (
      <section className="flex flex-col gap-5 rounded-2xl border border-line bg-surface p-8 shadow-(--shadow-lift)" aria-labelledby="confirm-title">
        <div className="flex items-start justify-between gap-4">
          <div className="flex flex-col gap-1.5">
            <h2 id="confirm-title" className="text-2xl font-bold tracking-tight">
              {t("intake.confirm.title")}
            </h2>
            <p className="text-base text-muted">{t("intake.confirm.help")}</p>
          </div>
          <ListenButton text={draft.text} />
        </div>
        <textarea
          value={draft.text}
          onChange={(e) => setDraft({ ...draft, text: e.target.value })}
          rows={4}
          maxLength={2000}
          lang={draft.lang}
          aria-label={t("intake.confirm.title")}
          className="w-full resize-none rounded-xl border-[1.5px] bg-surface p-4 text-xl leading-relaxed text-ink outline-none focus:border-accent focus:ring-4 focus:ring-tint-strong"
        />
        <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
          <Button loading={busy} disabled={!final.text} onClick={() => onConfirm(final)}>
            {t("intake.confirm.yes")}
          </Button>
          <Button
            variant="secondary"
            full={false}
            disabled={busy}
            onClick={() => {
              setDraft(null);
              setTyped("");
            }}
          >
            {t("intake.confirm.again")}
          </Button>
        </div>
      </section>
    );
  }

  const { supported, listening, busy: transcribing, heard, level, problem, mode } = listener;
  return (
    <section className="flex flex-col gap-6 rounded-2xl border border-line bg-surface p-8 shadow-(--shadow-lift)" aria-label={question.text[lang]}>
      {supported ? (
        <div className="flex flex-col items-center gap-4">
          <div className="relative grid size-28 place-items-center">
            {listening && <span className="ring absolute inset-0 rounded-full bg-accent/25" aria-hidden="true" />}
            <button
              type="button"
              onClick={listening ? listener.stop : listener.start}
              disabled={transcribing}
              aria-label={transcribing ? t("intake.mic.processing") : listening ? t("intake.mic.stop") : t("intake.mic.start")}
              className="relative grid size-24 place-items-center rounded-full bg-accent text-white shadow-(--shadow-lift) transition-colors hover:bg-accent-hover active:bg-deep disabled:opacity-70"
            >
              {transcribing ? (
                <Loader2 className="size-10 animate-spin" aria-hidden="true" />
              ) : listening ? (
                <Square className="size-9 fill-current" aria-hidden="true" />
              ) : (
                <Mic className="size-10" aria-hidden="true" />
              )}
            </button>
          </div>
          <p className="text-lg font-semibold" aria-live="polite">
            {transcribing ? t("intake.mic.processing") : listening ? t("intake.mic.listening") : t("intake.mic.start")}
          </p>
          {listening && <Wave level={mode === "server" ? level : undefined} />}
          {listening && heard && (
            <p className="max-w-md text-center text-xl leading-relaxed text-ink" lang={lang}>
              {heard}
            </p>
          )}
          {listening && <p className="text-[15px] text-muted">{t("intake.mic.stop")}</p>}
        </div>
      ) : (
        <Notice tone="info">{t("intake.typeOnly")}</Notice>
      )}

      {problem && <Notice tone={problem === "nothing" ? "info" : "error"}>{t(PROBLEM_TEXT[problem])}</Notice>}

      {!listening && !transcribing && (
        <div className={cx("flex flex-col gap-3", supported && "border-t border-line pt-6")}>
          <label htmlFor="typed-answer" className="flex items-center gap-2 text-base font-semibold">
            <Keyboard className="size-5 text-accent" aria-hidden="true" />
            {t("intake.type.label")}
          </label>
          <textarea
            id="typed-answer"
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            rows={3}
            maxLength={2000}
            lang={lang}
            placeholder={t("intake.type.placeholder")}
            className="w-full resize-none rounded-xl border-[1.5px] bg-surface p-4 text-xl leading-relaxed text-ink outline-none placeholder:text-[#6b7690] focus:border-accent focus:ring-4 focus:ring-tint-strong"
          />
          <Button variant="secondary" full={false} className="self-start" disabled={!typed.trim()} onClick={useTyped}>
            {t("intake.type.send")}
          </Button>
        </div>
      )}
    </section>
  );
}

function ChoiceAnswer({ question, onPick, busy }: { question: IntakeQuestion; onPick: (choiceId: string) => void; busy: boolean }) {
  const { lang } = useLang();
  return (
    <div role="radiogroup" aria-label={question.text[lang]} className="flex flex-col gap-3">
      {(question.choices ?? []).map((c) => (
        <button
          key={c.id}
          type="button"
          disabled={busy}
          onClick={() => onPick(c.id)}
          className="min-h-[72px] rounded-2xl border-[1.5px] border-line bg-surface px-6 py-3.5 text-left text-xl font-semibold transition-colors hover:border-accent hover:bg-tint disabled:opacity-60"
        >
          {c.label[lang]}
        </button>
      ))}
    </div>
  );
}

export function IntakePage() {
  const { t, lang } = useLang();
  const [questions, setQuestions] = useState<IntakeQuestion[] | null>(null);
  const [session, setSession] = useState<IntakeSession | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [finishing, setFinishing] = useState(false);

  // Load the questions and the learner's live session; send them elsewhere if there is none to continue.
  useEffect(() => {
    let alive = true;
    Promise.all([getIntakeQuestions(), getLatestIntake()])
      .then(([q, s]) => {
        if (!alive) return;
        if (s.status === "review") return navigate("/intake/review", { replace: true });
        if (s.status !== "in_progress") return navigate("/skills", { replace: true });
        setQuestions(q.questions);
        setSession(s);
      })
      .catch((err: unknown) => {
        if (!alive) return;
        if (isApiFailure(err) && err.status === 404) return navigate("/skills", { replace: true });
        setError(t(errorKey(err)));
      });
    return () => {
      alive = false;
    };
    // run once on entry
  }, []);

  const finish = useCallback(
    async (id: string) => {
      setFinishing(true);
      setError(null);
      try {
        await completeIntake(id);
        navigate("/intake/review", { replace: true });
      } catch (err) {
        setError(t(errorKey(err)));
        setFinishing(false);
      }
    },
    [t],
  );

  // Once every question has an answer, read them.
  const allAnswered = session !== null && session.next_question_id === null;
  useEffect(() => {
    if (allAnswered && session && !finishing && !error) void finish(session.id);
  }, [allAnswered, session, finishing, error, finish]);

  const send = async (body: { question_id: string; transcript?: string; choice_id?: string; source: AnswerSource; language: Lang }) => {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      setSession(await confirmAnswer(session.id, body));
    } catch (err) {
      setError(t(errorKey(err)));
    } finally {
      setBusy(false);
    }
  };

  if (error && !session) {
    return (
      <div className="flex max-w-xl flex-col gap-4 pt-10">
        <Notice>{error}</Notice>
        <Button full={false} variant="secondary" onClick={() => navigate("/skills")}>
          {t("skills.startNew")}
        </Button>
      </div>
    );
  }

  if (!session || !questions || finishing || allAnswered) {
    return (
      <div className="flex max-w-xl flex-col items-start gap-4 pt-10" role="status">
        <Loader2 className="size-8 animate-spin text-accent" aria-hidden="true" />
        {(finishing || allAnswered) && (
          <>
            <h1 className="text-[30px] leading-tight font-bold tracking-tight">{t("intake.reading.title")}</h1>
            <p className="text-lg text-muted">{t("intake.reading.help")}</p>
          </>
        )}
        {error && (
          <>
            <Notice>{error}</Notice>
            <Button full={false} onClick={() => session && void finish(session.id)}>
              {t("status.retry")}
            </Button>
          </>
        )}
      </div>
    );
  }

  const question = questions.find((q) => q.id === session.next_question_id);
  if (!question) return null;
  const n = session.answers.length + 1;

  return (
    <div className="flex max-w-2xl flex-col gap-7 pt-2">
      <Progress n={n} total={session.total_questions} />
      <div className="flex items-start justify-between gap-5">
        <h1 className="text-[34px] leading-[1.2] font-bold tracking-tight" lang={lang}>
          {question.text[lang]}
        </h1>
        <ListenButton text={question.text[lang]} />
      </div>

      {question.example && (
        <p className="-mt-3 text-lg text-muted" lang={lang}>
          {question.example[lang]}
        </p>
      )}

      {error && <Notice>{error}</Notice>}

      {question.kind === "choice" ? (
        <ChoiceAnswer
          key={question.id}
          question={question}
          busy={busy}
          onPick={(choiceId) => void send({ question_id: question.id, choice_id: choiceId, source: "tap", language: lang })}
        />
      ) : (
        <OpenAnswer
          key={question.id}
          question={question}
          busy={busy}
          onConfirm={(d) => void send({ question_id: question.id, transcript: d.text, source: d.source, language: d.lang })}
        />
      )}

      <div className="flex flex-col gap-2 pt-2">
        <Button variant="ghost" full={false} className="-ml-4 self-start" onClick={() => navigate("/home")}>
          {t("intake.leave")}
        </Button>
        <p className="text-[15px] text-muted">{t("intake.saved")}</p>
      </div>
    </div>
  );
}
