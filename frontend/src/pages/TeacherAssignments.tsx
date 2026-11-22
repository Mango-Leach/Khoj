import { useCallback, useEffect, useState, type FormEvent } from "react";
import { CheckCircle2, ClipboardList, FileEdit, Loader2, Plus, Sparkles, Trash2, Users, X } from "lucide-react";
import { Link } from "../components/Link";
import { Button, Notice, cx } from "../components/ui";
import {
  createAssignment,
  draftAssignments,
  getAssignmentDetail,
  getMentees,
  getMilestones,
  patchAssignment,
  type AssignmentDoc,
  type Mentee,
  type Milestone,
  type MilestoneAssignment,
  type MilestoneKey,
  type MilestonesView,
} from "../lib/api";
import { errorKey } from "../lib/errors";
import { LANGS, useLang, type MessageKey } from "../lib/i18n";
import { pickText } from "../lib/text";

interface FormValues {
  title: string;
  instructions: string;
  criteria: string[];
}

const FIELD =
  "w-full rounded-xl border-[1.5px] border-line-strong bg-surface px-4 py-3 text-lg text-ink outline-none focus:border-accent focus:ring-4 focus:ring-tint-strong";

/** Used both to write a new assignment and to edit a draft. The text is saved in the language the mentor is reading the app in. */
function AssignmentForm({ initial, onSave, onCancel }: { initial: FormValues; onSave: (v: FormValues) => Promise<void>; onCancel: () => void }) {
  const { t, lang } = useLang();
  const [values, setValues] = useState<FormValues>(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<MessageKey | null>(null);
  const language = LANGS.find((l) => l.code === lang)?.label ?? lang;

  const setCriterion = (i: number, v: string) => setValues((p) => ({ ...p, criteria: p.criteria.map((c, n) => (n === i ? v : c)) }));
  const valid =
    values.title.trim().length >= 3 && values.instructions.trim().length >= 10 && values.criteria.length >= 3 && values.criteria.every((c) => c.trim().length >= 3);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!valid || busy) return;
    setBusy(true);
    setError(null);
    try {
      await onSave({ title: values.title.trim(), instructions: values.instructions.trim(), criteria: values.criteria.map((c) => c.trim()) });
    } catch (err) {
      setError(errorKey(err));
      setBusy(false);
    }
  };

  return (
    <form onSubmit={(e) => void submit(e)} className="flex flex-col gap-4 rounded-xl border border-accent bg-tint/40 p-5">
      <p className="text-sm font-semibold text-muted">{t("ta.writing", { language })}</p>
      {error && <Notice>{t(error)}</Notice>}
      <label className="flex flex-col gap-1.5">
        <span className="text-base font-semibold">{t("ta.field.title")}</span>
        <input value={values.title} onChange={(e) => setValues((p) => ({ ...p, title: e.target.value }))} maxLength={100} className={cx(FIELD, "h-12 py-0")} />
      </label>
      <label className="flex flex-col gap-1.5">
        <span className="text-base font-semibold">{t("ta.field.instructions")}</span>
        <textarea value={values.instructions} onChange={(e) => setValues((p) => ({ ...p, instructions: e.target.value }))} maxLength={900} rows={4} className={cx(FIELD, "resize-y")} />
      </label>
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1 text-base font-semibold">{t("ta.field.criteria")}</legend>
        {values.criteria.map((c, i) => (
          <div key={i} className="flex items-center gap-2">
            <input value={c} onChange={(e) => setCriterion(i, e.target.value)} maxLength={140} aria-label={`${t("ta.field.criterion")} ${i + 1}`} className={cx(FIELD, "h-11 py-0 text-base")} />
            {values.criteria.length > 3 && (
              <button
                type="button"
                onClick={() => setValues((p) => ({ ...p, criteria: p.criteria.filter((_, n) => n !== i) }))}
                aria-label={t("ta.criteria.remove")}
                title={t("ta.criteria.remove")}
                className="grid size-11 shrink-0 place-items-center rounded-xl text-muted hover:bg-bg hover:text-bad"
              >
                <X className="size-5" aria-hidden="true" />
              </button>
            )}
          </div>
        ))}
        {values.criteria.length < 5 && (
          <button type="button" onClick={() => setValues((p) => ({ ...p, criteria: [...p.criteria, ""] }))} className="inline-flex items-center gap-1.5 self-start text-base font-semibold text-accent hover:underline">
            <Plus className="size-4" aria-hidden="true" />
            {t("ta.criteria.add")}
          </button>
        )}
      </fieldset>
      <div className="flex gap-3">
        <Button type="submit" full={false} className="h-11 px-6 text-base" loading={busy} disabled={!valid}>
          {t("ta.save")}
        </Button>
        <Button type="button" variant="secondary" full={false} className="h-11 px-6 text-base" onClick={onCancel} disabled={busy}>
          {t("ta.cancel")}
        </Button>
      </div>
    </form>
  );
}

function Chip({ tone, children }: { tone: "ok" | "warn" | "idle" | "info"; children: string }) {
  const tones = { ok: "bg-ok-bg text-ok", warn: "bg-warn-bg text-warn", idle: "bg-bg text-muted", info: "bg-tint text-accent" };
  return <span className={cx("inline-flex rounded-full px-3 py-1 text-sm font-semibold", tones[tone])}>{children}</span>;
}

function MilestoneBlock({
  journeyId,
  m,
  onChanged,
  setNote,
}: {
  journeyId: string;
  m: Milestone;
  onChanged: () => Promise<void>;
  setNote: (n: { tone: "error" | "info"; key: MessageKey } | null) => void;
}) {
  const { t, lang } = useLang();
  const [busy, setBusy] = useState<string | null>(null);
  const [form, setForm] = useState<string | "new" | null>(null); // an assignment id being edited, or a new one
  const [docs, setDocs] = useState<Record<string, AssignmentDoc>>({});

  const run = async (key: string, fn: () => Promise<void>) => {
    setBusy(key);
    setNote(null);
    try {
      await fn();
      await onChanged();
    } catch (err) {
      setNote({ tone: "error", key: errorKey(err) });
    } finally {
      setBusy(null);
    }
  };

  // The full text of an assignment is needed to edit it; the milestone list carries titles only.
  const openEdit = async (a: MilestoneAssignment) => {
    setBusy(`edit-${a.id}`);
    try {
      const d = await getAssignmentDetail(a.id);
      setDocs((p) => ({ ...p, [a.id]: d.assignment }));
      setForm(a.id);
    } catch (err) {
      setNote({ tone: "error", key: errorKey(err) });
    } finally {
      setBusy(null);
    }
  };

  const retire = (a: MilestoneAssignment) => {
    if (!window.confirm(t("ta.retire.confirm"))) return;
    void run(`retire-${a.id}`, async () => void (await patchAssignment(a.id, { status: "retired" })));
  };

  const live = m.assignments.length;

  return (
    <section className="flex flex-col gap-4 rounded-2xl border border-line bg-surface p-6 shadow-(--shadow-soft)">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-0.5">
          <h2 className="text-xl font-bold">{pickText(m.title, lang)}</h2>
          <p className="text-[15px] font-semibold text-muted">{t("work.ms.progress", { done: m.done, total: m.total })}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            full={false}
            variant="secondary"
            className="h-11 px-4 text-base"
            icon={<Sparkles className="size-5" />}
            loading={busy === "ai"}
            disabled={busy !== null || live >= 6}
            onClick={() => void run("ai", async () => void (await draftAssignments(journeyId, m.key)))}
          >
            {t("ta.draftAi")}
          </Button>
          <Button full={false} variant="secondary" className="h-11 px-4 text-base" icon={<Plus className="size-5" />} disabled={busy !== null || live >= 6} onClick={() => setForm("new")}>
            {t("ta.write")}
          </Button>
        </div>
      </div>

      <ul className="flex flex-col gap-3">
        {m.assignments.map((a) => {
          const doc = docs[a.id];
          return (
            <li key={a.id} className="flex flex-col gap-3 rounded-xl border border-line px-4 py-3.5">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                <p className="min-w-0 flex-1 text-lg leading-snug font-semibold">{pickText(a.title, lang)}</p>
                <Chip tone={a.status === "draft" ? "warn" : "ok"}>{t(a.status === "draft" ? "ta.status.draft" : "ta.status.approved")}</Chip>
                <Chip tone="idle">{t(`ta.source.${a.source}` as MessageKey)}</Chip>
              </div>
              {a.status === "draft" && <p className="text-sm text-muted">{t("ta.draft.help")}</p>}
              {form === a.id && doc && (
                <AssignmentForm
                  initial={{ title: pickText(doc.title, lang), instructions: pickText(doc.instructions, lang), criteria: doc.criteria.map((c) => pickText(c.text, lang)) }}
                  onCancel={() => setForm(null)}
                  onSave={async (v) => {
                    await patchAssignment(a.id, { lang, ...v });
                    setForm(null);
                    await onChanged();
                  }}
                />
              )}
              {form !== a.id && (
                <div className="flex flex-wrap gap-2">
                  {a.status === "draft" && (
                    <>
                      <Button full={false} variant="secondary" className="h-10 px-4 text-[15px]" icon={<FileEdit className="size-4" />} loading={busy === `edit-${a.id}`} disabled={busy !== null} onClick={() => void openEdit(a)}>
                        {t("ta.edit")}
                      </Button>
                      <Button full={false} className="h-10 px-4 text-[15px]" icon={<CheckCircle2 className="size-4" />} loading={busy === `approve-${a.id}`} disabled={busy !== null} onClick={() => void run(`approve-${a.id}`, async () => void (await patchAssignment(a.id, { status: "approved" })))}>
                        {t("ta.approve")}
                      </Button>
                    </>
                  )}
                  <Button full={false} variant="secondary" className="h-10 px-4 text-[15px]" icon={<Trash2 className="size-4" />} loading={busy === `retire-${a.id}`} disabled={busy !== null} onClick={() => retire(a)}>
                    {a.status === "draft" ? t("ta.discard") : t("ta.retire")}
                  </Button>
                </div>
              )}
            </li>
          );
        })}
      </ul>

      {form === "new" && (
        <AssignmentForm
          initial={{ title: "", instructions: "", criteria: ["", "", ""] }}
          onCancel={() => setForm(null)}
          onSave={async (v) => {
            await createAssignment(journeyId, m.key as MilestoneKey, { lang, ...v });
            setForm(null);
            await onChanged();
          }}
        />
      )}
    </section>
  );
}

export function TeacherAssignmentsPage() {
  const { t, lang } = useLang();
  const [mentees, setMentees] = useState<Mentee[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [view, setView] = useState<MilestonesView | null>(null);
  const [failed, setFailed] = useState(false);
  const [note, setNote] = useState<{ tone: "error" | "info"; key: MessageKey } | null>(null);

  useEffect(() => {
    let alive = true;
    getMentees()
      .then((r) => {
        if (!alive) return;
        setMentees(r.students);
        setSelected((cur) => cur ?? r.students[0]?.journey_id ?? null);
      })
      .catch(() => alive && setFailed(true));
    return () => {
      alive = false;
    };
  }, []);

  const load = useCallback(async () => {
    if (!selected) return;
    try {
      setView(await getMilestones(selected));
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, [selected]);
  useEffect(() => {
    setView(null);
    void load();
  }, [load]);

  return (
    <div className="flex flex-col gap-6 pt-2 lg:-mb-10 lg:h-[calc(100dvh-92px)] lg:gap-5">
      <div className="flex flex-col gap-2">
        <h1 className="text-[30px] leading-[1.1] font-bold tracking-tight md:text-[38px]">{t("ta.title")}</h1>
        <p className="max-w-3xl text-lg text-muted">{t("ta.lead")}</p>
      </div>
      {failed && <Notice>{t("err.network")}</Notice>}
      {!mentees && !failed && (
        <div className="flex items-center gap-3 text-lg text-muted" role="status">
          <Loader2 className="size-6 animate-spin text-accent" aria-hidden="true" />
          {t("req.loading")}
        </div>
      )}
      {mentees && mentees.length === 0 && (
        <section className="flex max-w-3xl gap-4 rounded-2xl border border-line bg-surface p-7 shadow-(--shadow-soft)">
          <Users className="mt-1 size-7 shrink-0 text-accent" aria-hidden="true" />
          <p className="text-lg text-muted">{t("ta.empty")}</p>
        </section>
      )}
      {mentees && mentees.length > 0 && (
        <div className="grid items-start gap-6 lg:min-h-0 lg:flex-1 lg:grid-cols-[300px_minmax(0,1fr)] lg:grid-rows-1 lg:items-stretch">
          <nav aria-label={t("ta.pick")} className="lg:relative lg:-mx-1 lg:min-h-0 lg:overflow-y-auto lg:px-1 lg:pb-2">
            <h2 className="mb-2 text-sm font-semibold tracking-wide text-muted uppercase">{t("ta.pick")}</h2>
            <ul className="flex flex-col gap-2">
              {mentees.map((m) => {
                const on = m.journey_id === selected;
                return (
                  <li key={m.journey_id}>
                    <button
                      type="button"
                      onClick={() => setSelected(m.journey_id)}
                      aria-current={on ? "true" : undefined}
                      className={cx("flex w-full flex-col gap-0.5 rounded-xl border px-4 py-3 text-left transition-colors", on ? "border-accent bg-tint" : "border-line bg-surface hover:border-accent")}
                    >
                      <span className="text-lg font-semibold">{m.student.name}</span>
                      <span className="text-[15px] text-muted">{pickText(m.student.career.name, lang)}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </nav>
          <div className="flex flex-col gap-5 lg:relative lg:-mx-1 lg:min-h-0 lg:overflow-y-auto lg:px-1 lg:pb-2">
            {note && <Notice tone={note.tone}>{t(note.key)}</Notice>}
            {view && view.waiting > 0 && (
              <p className="flex flex-wrap items-center gap-3 rounded-xl bg-tint px-5 py-3 text-base font-semibold text-deep">
                <ClipboardList className="size-5 shrink-0 text-accent" aria-hidden="true" />
                {t("ta.waiting", { n: view.waiting })}
                <Link to="/t/review" className="text-accent underline">
                  {t("ta.waiting.cta")}
                </Link>
              </p>
            )}
            {!view && !failed && <Loader2 className="size-6 animate-spin text-accent" aria-label={t("req.loading")} />}
            {view && selected && view.milestones.map((m) => <MilestoneBlock key={m.key} journeyId={selected} m={m} onChanged={load} setNote={setNote} />)}
          </div>
        </div>
      )}
    </div>
  );
}
