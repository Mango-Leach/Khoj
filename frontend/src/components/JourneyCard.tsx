import { ArrowRight, Briefcase, Check, Compass, GraduationCap, UserCheck, type LucideIcon } from "lucide-react";
import type { Journey, JourneyState } from "../lib/api";
import { useLang, type MessageKey } from "../lib/i18n";
import { navigate } from "../lib/router";
import { Button, cx } from "./ui";

type StepState = "done" | "current" | "todo";

/**
 * Where each step stands. The path is chosen from the start. Learning is open to everyone from the start, with or
 * without a mentor, so it is never waiting on one. The mentor step is optional: it is done once a mentor accepts and
 * otherwise just stays open, never blocking the steps around it.
 */
function stepStates(state: JourneyState, hasMentor: boolean): StepState[] {
  const mentor: StepState = hasMentor ? "done" : "todo";
  switch (state) {
    case "completed":
    case "opportunities_open":
      return ["done", "done", mentor, "current"];
    case "enrolled":
    case "abandoned":
      return ["done", "done", mentor, "done"];
    default:
      return ["done", "current", mentor, "todo"];
  }
}

const STEPS: { key: "path" | "learn" | "mentor" | "opps"; icon: LucideIcon }[] = [
  { key: "path", icon: Compass },
  { key: "learn", icon: GraduationCap },
  { key: "mentor", icon: UserCheck },
  { key: "opps", icon: Briefcase },
];

/** The learner's chosen career on the home page: what it is, how far along they are, and the next action. */
export function JourneyCard({ journey }: { journey: Journey }) {
  const { t, lang } = useLang();
  const mentor = journey.mentor;
  const steps = stepStates(journey.state, Boolean(mentor) && journey.state !== "mentor_pending" && journey.state !== "path_selected");
  const name = mentor?.name ?? "";
  const status: MessageKey =
    journey.state === "mentor_pending" ? "home.path.status.mentor_pending" : mentor && journey.state !== "path_selected" ? "home.path.status.in_progress" : "home.path.status.path_selected";
  const mentorButton: MessageKey =
    journey.state === "mentor_pending" ? "home.path.cta.mentorPending" : status === "home.path.status.in_progress" ? "home.path.cta.mentorOpen" : "home.path.cta.mentorFind";
  const learnPath = `/paths/${journey.career.career_id}`; // the courses and learning links are on the path page
  const finished = journey.state === "completed" || journey.state === "opportunities_open" || journey.state === "enrolled";
  const finishedStatus: MessageKey = journey.state === "enrolled" ? "home.path.status.enrolled" : "home.path.status.opportunities_open";

  return (
    <section
      className="grid gap-8 rounded-2xl border border-line bg-surface p-6 shadow-(--shadow-lift) md:p-8 xl:col-span-2 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]"
      aria-labelledby="your-path"
    >
      <div className="flex min-w-0 flex-col gap-5">
        <div className="flex flex-col gap-2">
          <p className="text-sm font-semibold tracking-wide text-deep uppercase">{t("home.path.eyebrow")}</p>
          <h2 id="your-path" className="text-[28px] leading-tight font-bold tracking-tight md:text-[34px]">
            {journey.career.name?.[lang] ?? journey.career.career_id}
          </h2>
          {journey.career.summary && <p className="max-w-2xl text-lg text-muted">{journey.career.summary[lang]}</p>}
        </div>
        {journey.career.first_income_step && (
          <div className="rounded-xl bg-tint p-5">
            <p className="text-sm font-semibold tracking-wide text-deep uppercase">{t("paths.first")}</p>
            <p className="mt-1 text-lg">{journey.career.first_income_step[lang]}</p>
          </div>
        )}
        <ol className="grid grid-cols-2 gap-x-2 gap-y-3 sm:grid-cols-4 sm:gap-2" aria-label={t("home.path.progress")}>
          {STEPS.map(({ key, icon: Icon }, i) => {
            const s = steps[i];
            return (
              <li key={key} className="flex min-w-0 items-center gap-2 sm:flex-col sm:gap-2 sm:text-center" aria-current={s === "current" ? "step" : undefined}>
                <span
                  className={cx(
                    "grid size-10 shrink-0 place-items-center rounded-full border-2 sm:size-11",
                    s === "done" && "border-ok bg-ok text-white",
                    s === "current" && "border-accent bg-tint text-accent",
                    s === "todo" && "border-line-strong bg-surface text-muted",
                  )}
                  aria-hidden="true"
                >
                  {s === "done" ? <Check className="size-5" /> : <Icon className="size-5" />}
                </span>
                <span className={cx("min-w-0 text-[14px] leading-tight font-semibold sm:text-[15px]", s === "todo" ? "text-muted" : "text-ink")}>
                  {t(`home.path.step.${key}` as MessageKey)}
                </span>
              </li>
            );
          })}
        </ol>
      </div>

      <div className="flex flex-col justify-center gap-4 rounded-2xl bg-bg p-6">
        <h3 className="text-xl font-bold">{t(finished ? finishedStatus : status, { name })}</h3>
        <p className="text-base text-muted">{t(`${finished ? finishedStatus : status}.help` as MessageKey, { name })}</p>
        {finished ? (
          <>
            <Button className="h-12 text-base" icon={<ArrowRight className="size-5" />} onClick={() => navigate("/opportunities")}>
              {t("home.path.cta.opps")}
            </Button>
            <Button variant="secondary" className="h-12 text-base" onClick={() => navigate(`/pack/${journey.career.career_id}`)}>
              {t("home.path.cta.pack")}
            </Button>
          </>
        ) : (
          <>
            <Button className="h-12 text-base" icon={<ArrowRight className="size-5" />} onClick={() => navigate(learnPath)}>
              {t("home.path.cta.learn")}
            </Button>
            <Button variant="secondary" className="h-12 text-base" onClick={() => navigate("/mentor")}>
              {t(mentorButton)}
            </Button>
          </>
        )}
        <button type="button" className="min-h-11 self-start text-base font-semibold text-accent hover:underline" onClick={() => navigate("/paths")}>
          {t("home.path.change")}
        </button>
      </div>
    </section>
  );
}
