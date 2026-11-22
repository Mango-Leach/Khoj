import { useEffect, useState } from "react";
import { HandHelping, Loader2, Users } from "lucide-react";
import { LearnerCardView } from "../components/LearnerCard";
import { pick } from "../components/Eligibility";
import { Button, Notice } from "../components/ui";
import { assistApplication, getMentees, getTeacherApplications, type Mentee, type TeacherApplication } from "../lib/api";
import { errorKey } from "../lib/errors";
import { useLang, type MessageKey } from "../lib/i18n";

/** Learners who finished their path and want help with an application. The mentor only marks that they helped. */
function ApplyHelp({ items, onHelped }: { items: TeacherApplication[]; onHelped: (id: string) => void }) {
  const { t, lang } = useLang();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<MessageKey | null>(null);
  if (items.length === 0) return null;

  const help = async (id: string) => {
    setBusy(id);
    setError(null);
    try {
      await assistApplication(id);
      onHelped(id);
    } catch (err) {
      setError(errorKey(err));
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="flex flex-col gap-4" aria-labelledby="apply-help">
      <div className="flex flex-col gap-1">
        <h2 id="apply-help" className="flex items-center gap-3 text-2xl font-bold tracking-tight">
          <HandHelping className="size-6 text-accent" aria-hidden="true" />
          {t("stu.apply.title")}
        </h2>
        <p className="max-w-3xl text-base text-muted">{t("stu.apply.help")}</p>
      </div>
      {error && <Notice>{t(error)}</Notice>}
      <ul className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
        {items.map((a) => (
          <li key={a.id} className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-5 shadow-(--shadow-soft)">
            <p className="text-lg font-bold">{a.student.name}</p>
            <p className="text-base">{a.title ? pick(a.title, lang).text : a.opportunity_id}</p>
            <p className="text-sm font-semibold text-muted">{t(`stu.apply.status.${a.status}` as MessageKey)}</p>
            {a.status === "interested" && (
              <Button full={false} className="mt-auto h-11 text-base" loading={busy === a.id} onClick={() => void help(a.id)}>
                {t("stu.apply.done")}
              </Button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

export function TeacherStudentsPage() {
  const { t, lang } = useLang();
  const [students, setStudents] = useState<Mentee[] | null>(null);
  const [applications, setApplications] = useState<TeacherApplication[]>([]);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    getMentees()
      .then((r) => alive && setStudents(r.students))
      .catch(() => alive && setFailed(true));
    getTeacherApplications()
      .then((r) => alive && setApplications(r.applications))
      .catch(() => undefined); // the list of learners still works without it
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div className="flex flex-col gap-8 pt-2">
      <div className="flex flex-col gap-2">
        <h1 className="text-[30px] leading-[1.1] font-bold tracking-tight md:text-[38px]">{t("stu.title")}</h1>
        <p className="max-w-3xl text-lg text-muted">{t("stu.lead")}</p>
      </div>
      {failed && <Notice>{t("err.network")}</Notice>}
      <ApplyHelp items={applications} onHelped={(id) => setApplications((list) => list.map((a) => (a.id === id ? { ...a, status: "mentor_assisted" } : a)))} />
      {!students && !failed && (
        <div className="flex items-center gap-3 text-lg text-muted" role="status">
          <Loader2 className="size-6 animate-spin text-accent" aria-hidden="true" />
          {t("req.loading")}
        </div>
      )}
      {students && students.length === 0 && (
        <section className="flex max-w-3xl gap-4 rounded-2xl border border-line bg-surface p-7 shadow-(--shadow-soft)">
          <Users className="mt-1 size-7 shrink-0 text-accent" aria-hidden="true" />
          <p className="text-lg text-muted">{t("stu.empty")}</p>
        </section>
      )}
      {students && students.length > 0 && (
        <ul className="grid gap-5 md:grid-cols-2 2xl:grid-cols-3">
          {students.map((s) => (
            <li key={s.journey_id} className="flex flex-col gap-4 rounded-2xl border border-line bg-surface p-6 shadow-(--shadow-soft)">
              <LearnerCardView card={s.student} />
              {s.since && <p className="mt-auto text-[15px] text-muted">{t("stu.since", { date: new Date(s.since).toLocaleDateString(lang === "en" ? "en-IN" : lang, { day: "numeric", month: "short", year: "numeric" }) })}</p>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
