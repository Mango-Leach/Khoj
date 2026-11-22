import { useEffect, useState, type ReactNode } from "react";
import { CheckCircle2, ClipboardCheck, Hourglass, Mic } from "lucide-react";
import { JourneyCard } from "../components/JourneyCard";
import { Link } from "../components/Link";
import { Button } from "../components/ui";
import { getReviewQueue, getTeacherRequests } from "../lib/api";
import { useLang, type MessageKey } from "../lib/i18n";
import { navigate } from "../lib/router";
import { useDistrictName } from "../lib/useDistrictName";
import { useSession } from "../lib/session";
import { useLatestIntake, useSkillNames } from "../lib/useIntake";
import { useJourney } from "../lib/usePaths";

function Page({ title, lead, aside, children }: { title: string; lead: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-8 pt-2">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between md:gap-8">
        <div className="flex min-w-0 flex-col gap-2">
          <h1 className="text-[30px] leading-[1.1] md:text-[38px] font-bold tracking-tight">{title}</h1>
          <p className="text-lg text-muted">{lead}</p>
        </div>
        {aside}
      </div>
      <div className="grid items-start gap-7 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">{children}</div>
    </div>
  );
}

/** The learner's class and place. `compact` is the small version that sits beside the greeting. */
function Details({ title, rows, compact = false }: { title: string; rows: { label: string; value: string }[]; compact?: boolean }) {
  return (
    <section
      className={
        compact
          ? "w-full rounded-2xl border border-line bg-surface px-5 py-3 shadow-(--shadow-soft) md:w-[320px] md:shrink-0"
          : "rounded-2xl border border-line bg-surface p-6 shadow-(--shadow-soft)"
      }
      aria-label={title}
    >
      <h2 className={compact ? "mb-1 text-base font-semibold" : "mb-3 text-xl font-semibold"}>{title}</h2>
      <dl className="divide-y divide-line">
        {rows.map((r) => (
          <div key={r.label} className={compact ? "flex items-baseline justify-between gap-6 py-1.5" : "flex items-baseline justify-between gap-6 py-3"}>
            <dt className={compact ? "text-[15px] text-muted" : "text-base text-muted"}>{r.label}</dt>
            <dd className={compact ? "text-right text-base font-semibold" : "text-right text-lg font-semibold"}>{r.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function NextStep({ icon, tone = "tint", title, help, cta, to, children }: {
  icon: ReactNode;
  tone?: "tint" | "ok";
  title: string;
  help: string;
  cta?: string;
  to?: string;
  children?: ReactNode;
}) {
  return (
    <section className="flex gap-6 rounded-2xl border border-line bg-surface p-8 shadow-(--shadow-lift)" aria-labelledby="next-title">
      <span
        className={`grid size-16 shrink-0 place-items-center rounded-2xl ${tone === "ok" ? "bg-ok-bg text-ok" : "bg-tint text-accent"}`}
        aria-hidden="true"
      >
        {icon}
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-5">
        <div className="flex flex-col gap-1.5">
          <h2 id="next-title" className="text-[26px] leading-tight font-bold tracking-tight">
            {title}
          </h2>
          <p className="text-lg text-muted">{help}</p>
        </div>
        {children}
        {cta && to && (
          <Button full={false} className="self-start" onClick={() => navigate(to)}>
            {cta}
          </Button>
        )}
      </div>
    </section>
  );
}

function IntakeCard() {
  const { t } = useLang();
  const latest = useLatestIntake();
  const skillName = useSkillNames();
  const mic = <Mic className="size-8" />;

  if (latest.state === "loading") return <NextStep icon={mic} title={t("home.next.student")} help={t("home.next.student.help")} />;
  if (latest.state === "ready") {
    const s = latest.session;
    if (s.status === "in_progress" && s.answers.length > 0) {
      return (
        <NextStep
          icon={mic}
          title={t("home.intake.continue.title")}
          help={t("home.intake.continue.help", { n: s.answers.length, total: s.total_questions })}
          cta={t("home.intake.continue.cta")}
          to="/intake"
        />
      );
    }
    if (s.status === "review") {
      return (
        <NextStep
          icon={<ClipboardCheck className="size-8" />}
          title={t("home.intake.review.title")}
          help={t("home.intake.review.help")}
          cta={t("home.intake.review.cta")}
          to="/intake/review"
        />
      );
    }
    if (s.status === "done" && s.extracted) {
      const items = [...s.extracted.skills.map(skillName), ...s.extracted.other_skills];
      return (
        <NextStep
          icon={<CheckCircle2 className="size-8" />}
          tone="ok"
          title={t("home.paths.title")}
          help={t("home.paths.help")}
          cta={t("home.paths.cta")}
          to="/paths"
        >
          {items.length > 0 && (
            <ul className="flex flex-wrap gap-2">
              {items.map((i) => (
                <li key={i} className="rounded-full bg-tint px-4 py-1.5 text-base font-semibold text-deep">
                  {i}
                </li>
              ))}
            </ul>
          )}
        </NextStep>
      );
    }
  }
  return <NextStep icon={mic} title={t("home.next.student")} help={t("home.next.student.help")} cta={t("home.next.cta")} to="/skills" />;
}

export function StudentHome() {
  const { t } = useLang();
  const { profile } = useSession();
  const districtName = useDistrictName();
  const { journey, loaded } = useJourney();
  if (profile?.kind !== "student") return null;
  const p = profile.data;
  const rows = [
    { label: t("home.details.class"), value: t(`grade.${p.grade}` as MessageKey) },
    { label: t("home.details.place"), value: `${p.block}, ${districtName(p.district)}` },
  ];
  // With a path chosen the home page is one big card, so the details shrink and sit beside the greeting.
  return (
    <Page
      title={t("home.hello", { name: p.name })}
      lead={t(journey ? "home.student.leadPath" : "home.student.lead")}
      aside={journey && <Details compact title={t("home.details.title")} rows={rows} />}
    >
      {journey ? <JourneyCard journey={journey} /> : loaded && <IntakeCard />}
      {!journey && <Details title={t("home.details.title")} rows={rows} />}
    </Page>
  );
}

export function TeacherHome() {
  const { t, lang } = useLang();
  const { profile } = useSession();
  const districtName = useDistrictName();
  const [waiting, setWaiting] = useState(0);
  const [toReview, setToReview] = useState(0);
  const verified = profile?.kind === "teacher" && profile.data.tier >= 1;
  useEffect(() => {
    if (!verified) return;
    let alive = true;
    getTeacherRequests()
      .then((r) => alive && setWaiting(r.pending.length))
      .catch(() => undefined);
    getReviewQueue()
      .then((r) => alive && setToReview(r.items.length))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [verified]);
  if (profile?.kind !== "teacher") return null;
  const p = profile.data;
  return (
    <Page title={t("home.hello", { name: p.name })} lead={t("home.teacher.lead")}>
      {verified ? (
        <NextStep
          icon={<CheckCircle2 className="size-8" />}
          tone="ok"
          title={t("home.teacher.status.title")}
          help={t("home.teacher.verified.help")}
          cta={t("home.teacher.requests.cta")}
          to="/t/requests"
        >
          <p>
            <span className="inline-block rounded-full bg-ok-bg px-3.5 py-1 text-base font-semibold text-ok">{t(`mentor.tier.${Math.min(p.tier, 2)}` as MessageKey)}</span>
          </p>
          {p.verified_areas.length > 0 && (
            <div className="flex flex-col gap-2">
              <h3 className="text-base font-semibold text-muted">{t("home.teacher.skills")}</h3>
              <ul className="flex flex-wrap gap-2">
                {p.verified_areas.map((a) => (
                  <li key={a.id} className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-3.5 py-1 text-base font-semibold">
                    <CheckCircle2 className="size-4 text-ok" aria-hidden="true" />
                    {a.name[lang]}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {waiting > 0 && <p className="text-lg font-semibold text-deep">{t("home.teacher.waiting", { n: waiting })}</p>}
          {toReview > 0 && (
            <p className="flex flex-wrap items-center gap-x-3 text-lg font-semibold text-deep">
              {t("home.teacher.review", { n: toReview })}
              <Link to="/t/review" className="text-accent underline">
                {t("home.teacher.review.cta")}
              </Link>
            </p>
          )}
        </NextStep>
      ) : (
        <NextStep
          icon={<Hourglass className="size-8" />}
          title={t("home.teacher.status.title")}
          help={t("home.teacher.status.help")}
          cta={t("home.teacher.assess.cta")}
          to="/t/assess"
        >
          <p>
            <span className="inline-block rounded-full bg-warn-bg px-3.5 py-1 text-base font-semibold text-warn">{t("home.teacher.status")}</span>
          </p>
        </NextStep>
      )}
      <Details
        title={t("home.details.title")}
        rows={[
          { label: t("home.teacher.roles"), value: p.roles.map((r) => t(`teacherRole.${r}` as MessageKey)).join(", ") },
          { label: t("home.teacher.hours"), value: String(p.weekly_hours) },
          { label: t("home.teacher.places"), value: t("home.teacher.placesValue", { free: p.capacity.free, limit: p.capacity.limit }) },
          { label: t("home.details.place"), value: `${p.block}, ${districtName(p.district)}` },
        ]}
      />
    </Page>
  );
}

/** Stands in for screens that later milestones build. It says so plainly and offers the way back. */
export function NotReady({ home }: { home: string }) {
  const { t } = useLang();
  return (
    <div className="flex max-w-xl flex-col items-start gap-4 pt-10">
      <h1 className="text-[34px] leading-tight font-bold tracking-tight">{t("notReady.title")}</h1>
      <p className="text-lg text-muted">{t("notReady.help")}</p>
      <Link to={home} className="inline-flex h-14 items-center rounded-xl bg-accent px-6 text-lg font-semibold text-white hover:bg-accent-hover">
        {t("notReady.home")}
      </Link>
    </div>
  );
}
