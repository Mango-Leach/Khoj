import { useEffect, useState, type ReactNode } from "react";
import { PageBanner } from "../components/PageBanner";
import { Check, Loader2, Plus, X } from "lucide-react";
import { Button, Notice, cx } from "../components/ui";
import { acceptIntake, getCategories, getLatestIntake, getSkills, isApiFailure, type Category, type Extracted, type IntakeSession, type SkillInfo } from "../lib/api";
import { errorKey } from "../lib/errors";
import { useLang, type Lang, type MessageKey } from "../lib/i18n";
import { navigate } from "../lib/router";
import { useSkillNames } from "../lib/useIntake";

function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3" aria-label={title}>
      <h2 className="text-xl font-semibold">{title}</h2>
      <ul className="flex flex-wrap gap-2.5">{children}</ul>
    </section>
  );
}

function Chip({ label, onRemove }: { label: string; onRemove: () => void }) {
  const { t } = useLang();
  return (
    <li>
      <button
        type="button"
        onClick={onRemove}
        aria-label={t("review.remove", { item: label })}
        className="inline-flex min-h-12 items-center gap-2.5 rounded-full border-[1.5px] border-line-strong bg-tint py-2 pr-3 pl-5 text-lg font-semibold text-ink transition-colors hover:border-bad hover:bg-bad-bg hover:text-bad"
      >
        {label}
        <X className="size-5" aria-hidden="true" />
      </button>
    </li>
  );
}

const MAX_SKILLS = 8;

/** The whole skill list, by family, for adding what we missed. Only the learner's own choice goes in. */
function SkillPicker({ selected, onToggle, onClose }: { selected: string[]; onToggle: (id: string) => void; onClose: () => void }) {
  const { t, lang } = useLang();
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [families, setFamilies] = useState<Category[]>([]);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    Promise.all([getSkills(), getCategories()])
      .then(([s, c]) => {
        setSkills(s.skills);
        setFamilies(c.categories);
      })
      .catch(() => setFailed(true));
  }, []);

  const full = selected.length >= MAX_SKILLS;
  const groups: { id: string; name: string; items: SkillInfo[] }[] = [
    ...families.map((f) => ({ id: f.id, name: f.name[lang as Lang], items: skills.filter((s) => s.family === f.id) })),
    { id: "general", name: t("review.family.general"), items: skills.filter((s) => s.family === "general") },
  ].filter((g) => g.items.length > 0);

  return (
    <section className="flex flex-col gap-5 rounded-[28px] border border-line bg-tint p-6" aria-label={t("review.add.title")}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h2 className="text-xl font-semibold">{t("review.add.title")}</h2>
          <p className="text-base text-muted">{t("review.add.help")}</p>
        </div>
        <Button full={false} variant="secondary" onClick={onClose}>
          {t("review.add.done")}
        </Button>
      </div>
      {failed && <Notice>{t("err.generic")}</Notice>}
      {full && <Notice tone="info">{t("review.add.max", { n: MAX_SKILLS })}</Notice>}
      {groups.map((g) => (
        <div key={g.id} className="flex flex-col gap-2.5" role="group" aria-label={g.name}>
          <h3 className="text-base font-semibold text-muted">{g.name}</h3>
          <div className="flex flex-wrap gap-2">
            {g.items.map((s) => {
              const on = selected.includes(s.id);
              return (
                <button
                  key={s.id}
                  type="button"
                  role="checkbox"
                  aria-checked={on}
                  data-skill={s.id}
                  disabled={!on && full}
                  onClick={() => onToggle(s.id)}
                  className={cx(
                    "inline-flex min-h-12 items-center gap-2 rounded-full border-[1.5px] px-4 text-base font-semibold transition-colors disabled:opacity-45",
                    on ? "border-accent bg-accent text-white" : "border-line-strong bg-surface text-ink hover:border-accent",
                  )}
                >
                  {on && <Check className="size-4" strokeWidth={3} aria-hidden="true" />}
                  {s.name[lang as Lang]}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </section>
  );
}

function constraintLines(c: Extracted["constraints"], t: (k: MessageKey, v?: Record<string, string | number>) => string): string[] {
  const lines: string[] = [];
  if (c.hours_per_week !== null) lines.push(t("review.hours", { n: c.hours_per_week }));
  lines.push(t(`review.move.${c.can_move_away}` as MessageKey));
  lines.push(t(`review.budget.${c.budget}` as MessageKey));
  if (c.earned_before !== "unknown") lines.push(t(`review.earned.${c.earned_before}` as MessageKey));
  if (c.priority !== "unknown") lines.push(t(`review.priority.${c.priority}` as MessageKey));
  return lines;
}

export function IntakeReviewPage() {
  const { t } = useLang();
  const skillName = useSkillNames();
  const [session, setSession] = useState<IntakeSession | null>(null);
  const [skills, setSkills] = useState<string[]>([]);
  const [other, setOther] = useState<string[]>([]);
  const [interests, setInterests] = useState<string[]>([]);
  const [goal, setGoal] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [picking, setPicking] = useState(false);

  useEffect(() => {
    let alive = true;
    getLatestIntake()
      .then((s) => {
        if (!alive) return;
        if (s.status === "in_progress") return navigate("/intake", { replace: true });
        if (s.status !== "review" || !s.extracted) return navigate("/home", { replace: true });
        setSession(s);
        setSkills(s.extracted.skills);
        setOther(s.extracted.other_skills);
        setInterests(s.extracted.interests);
        setGoal(s.extracted.goal);
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

  const accept = async () => {
    if (!session) return;
    setSaving(true);
    setError(null);
    try {
      await acceptIntake(session.id, { skills, other_skills: other, interests, goal });
      navigate("/home");
    } catch (err) {
      setError(t(errorKey(err)));
      setSaving(false);
    }
  };

  if (!session?.extracted) {
    return (
      <div className="flex max-w-xl flex-col gap-4 pt-10" role={error ? undefined : "status"}>
        {error ? (
          <>
            <Notice>{error}</Notice>
            <Button full={false} variant="secondary" onClick={() => navigate("/home")}>
              {t("notReady.home")}
            </Button>
          </>
        ) : (
          <Loader2 className="size-8 animate-spin text-accent" aria-hidden="true" />
        )}
      </div>
    );
  }

  const hasAnything = skills.length + other.length + interests.length > 0 || goal !== null;
  const hasEnglish = other.length + interests.length > 0 || goal !== null;

  return (
    <div className="flex flex-col gap-6 pt-2">
      <PageBanner title={t("review.title")} lead={t("review.lead")} />

      {session.extraction_source === "fallback" && <Notice tone="info">{t("review.fallbackNote")}</Notice>}
      {!hasAnything && <Notice tone="info">{t("review.none")}</Notice>}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] lg:items-start">
        <div className="flex flex-col gap-7 rounded-[28px] border border-line bg-surface p-7 shadow-(--shadow-soft) md:p-8">
          <Group title={t("review.skills")}>
            {skills.map((s) => (
              <Chip key={s} label={skillName(s)} onRemove={() => setSkills((cur) => cur.filter((x) => x !== s))} />
            ))}
            {!picking && (
              <li>
                <button
                  type="button"
                  onClick={() => setPicking(true)}
                  className="inline-flex min-h-12 items-center gap-2 rounded-full border-[1.5px] border-dashed border-accent px-5 py-2 text-lg font-semibold text-accent transition-colors hover:bg-tint"
                >
                  <Plus className="size-5" aria-hidden="true" />
                  {t("review.add")}
                </button>
              </li>
            )}
          </Group>
          {picking && (
            <SkillPicker
              selected={skills}
              onToggle={(id) =>
                setSkills((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : cur.length < MAX_SKILLS ? [...cur, id] : cur))
              }
              onClose={() => setPicking(false)}
            />
          )}
          {other.length > 0 && (
            <Group title={t("review.other")}>
              {other.map((s) => (
                <Chip key={s} label={s} onRemove={() => setOther((cur) => cur.filter((x) => x !== s))} />
              ))}
            </Group>
          )}
          {interests.length > 0 && (
            <Group title={t("review.interests")}>
              {interests.map((s) => (
                <Chip key={s} label={s} onRemove={() => setInterests((cur) => cur.filter((x) => x !== s))} />
              ))}
            </Group>
          )}
          {goal && (
            <Group title={t("review.goal")}>
              <Chip label={goal} onRemove={() => setGoal(null)} />
            </Group>
          )}
          {hasEnglish && <p className="text-[15px] text-muted">{t("review.englishNote")}</p>}
        </div>

        <aside className="flex flex-col gap-6 rounded-[28px] border border-line bg-surface p-7 shadow-(--shadow-soft) md:p-8 lg:sticky lg:top-4" aria-label={t("review.constraints")}>
          <section className="flex flex-col gap-3">
            <h2 className="text-xl font-semibold">{t("review.constraints")}</h2>
            <ul className="flex flex-col gap-2 text-lg text-muted">
              {constraintLines(session.extracted.constraints, t).map((line) => (
                <li key={line} className="flex items-start gap-3">
                  <span className="mt-2.5 size-2 shrink-0 rounded-full bg-accent" aria-hidden="true" />
                  {line}
                </li>
              ))}
            </ul>
          </section>

          {error && <Notice>{error}</Notice>}

          <div className="flex flex-col gap-3 border-t border-line pt-6">
            <Button loading={saving} disabled={!hasAnything} onClick={accept}>
              {t("review.accept")}
            </Button>
            <Button variant="secondary" disabled={saving} onClick={() => navigate("/skills")}>
              {t("review.again")}
            </Button>
          </div>
        </aside>
      </div>
    </div>
  );
}
