import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Check, Clock, GraduationCap, Hourglass, Languages, Loader2, MapPin, ShieldCheck, UserCheck, Users } from "lucide-react";
import { Button, Notice, cx } from "../components/ui";
import {
  cancelMentorRequest,
  getMentorCandidates,
  getMyJourney,
  isApiFailure,
  requestMentor,
  type Candidate,
  type Journey,
  type Mentor,
} from "../lib/api";
import { errorKey } from "../lib/errors";
import { LANGS, useLang, type MessageKey } from "../lib/i18n";
import { navigate } from "../lib/router";
import { useDistrictName } from "../lib/useDistrictName";

type View =
  | { state: "loading" }
  | { state: "none" }
  | { state: "error" }
  | { state: "ready"; journey: Journey; candidates: Candidate[] };

function hoursLeft(iso: string): number {
  return Math.max(1, Math.ceil((new Date(iso).getTime() - Date.now()) / 3_600_000));
}

function Tier({ tier }: { tier: number }) {
  const { t } = useLang();
  if (tier < 1) return null;
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-ok-bg px-3 py-1 text-sm font-semibold text-ok">
      <ShieldCheck className="size-4" aria-hidden="true" />
      {t(`mentor.tier.${Math.min(tier, 2)}` as MessageKey)}
    </span>
  );
}

function Fact({ icon: Icon, children, good = false }: { icon: typeof Clock; children: string; good?: boolean }) {
  return (
    <li className={cx("inline-flex items-center gap-2 text-[15px]", good ? "font-semibold text-ok" : "text-muted")}>
      <Icon className="size-4 shrink-0" aria-hidden="true" />
      {children}
    </li>
  );
}

function Header({ mentor }: { mentor: Pick<Mentor, "name" | "roles"> }) {
  const { t } = useLang();
  return (
    <div className="flex items-center gap-3.5">
      <span className="grid size-14 shrink-0 place-items-center rounded-full bg-deep text-2xl font-bold text-white" aria-hidden="true">
        {mentor.name.trim().charAt(0).toUpperCase()}
      </span>
      <div className="flex min-w-0 flex-col gap-0.5">
        <p className="truncate text-[22px] leading-tight font-bold">{mentor.name}</p>
        <p className="text-base text-muted">{mentor.roles.map((r) => t(`teacherRole.${r}` as MessageKey)).join(", ")}</p>
      </div>
    </div>
  );
}

function CandidateCard({ c, busy, onAsk, disabled }: { c: Candidate; busy: boolean; onAsk: () => void; disabled: boolean }) {
  const { t, lang } = useLang();
  const districtName = useDistrictName();
  const langs = c.languages.map((l) => LANGS.find((x) => x.code === l)?.label ?? l).join(", ");
  return (
    <li className="flex flex-col gap-4 rounded-2xl border border-line bg-surface p-5 shadow-(--shadow-soft)">
      <Header mentor={c} />
      <Tier tier={c.tier} />
      <ul className="flex flex-col gap-1.5">
        <Fact icon={Languages} good={c.speaks_your_language}>
          {c.speaks_your_language ? t("mentor.lang.same", { languages: langs }) : t("mentor.lang.other", { languages: langs })}
        </Fact>
        <Fact icon={MapPin} good={c.same_district}>
          {c.same_block
            ? t("mentor.place.block", { block: c.block })
            : c.same_district
              ? t("mentor.place.district", { district: districtName(c.district) })
              : t("mentor.place.far", { district: districtName(c.district) })}
        </Fact>
        <Fact icon={Users}>{t("mentor.places", { n: c.free_places })}</Fact>
      </ul>
      <div className="flex flex-col gap-1.5">
        <p className="text-sm font-semibold tracking-wide text-deep uppercase">{t("mentor.skills")}</p>
        <ul className="flex flex-wrap gap-2">
          {c.verified_in.map((s) => (
            <li key={s.id} className="rounded-full bg-tint px-3 py-1 text-[15px] font-semibold text-deep">
              {s.name[lang] ?? s.name.en}
            </li>
          ))}
        </ul>
      </div>
      <Button className="mt-auto h-12 text-base" loading={busy} disabled={disabled} onClick={onAsk}>
        {t("mentor.ask", { name: c.name })}
      </Button>
    </li>
  );
}

/** Reminds the learner that learning does not wait for a mentor, and points to the courses. */
function LearnBanner({ careerId }: { careerId: string }) {
  const { t } = useLang();
  return (
    <section className="flex flex-col gap-3 rounded-2xl bg-tint px-5 py-4 sm:flex-row sm:items-center sm:gap-4" aria-labelledby="optional-title">
      <GraduationCap className="size-7 shrink-0 text-accent" aria-hidden="true" />
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <h2 id="optional-title" className="text-lg font-bold text-deep">
          {t("mentor.optional.title")}
        </h2>
        <p className="text-base text-deep">{t("mentor.optional.help")}</p>
      </div>
      <Button full={false} className="h-11 text-base" onClick={() => navigate(`/paths/${careerId}`)}>
        {t("mentor.optional.cta")}
      </Button>
    </section>
  );
}

/** With `fit`, from 1024 px up the page is exactly one screen tall (the shell adds 76 px of header and 56 px of bottom
 *  padding, hence the height and the negative margin) and only a `Scroller` inside it scrolls, and only when it must. */
function Shell({ title, lead, fit = false, children }: { title: string; lead?: string; fit?: boolean; children: ReactNode }) {
  return (
    <div className={cx("flex flex-col gap-8 pt-2", fit && "lg:-mb-10 lg:h-[calc(100dvh-92px)] lg:gap-5")}>
      <div className="flex flex-col gap-2">
        <h1 className="text-[30px] leading-[1.1] font-bold tracking-tight md:text-[38px]">{title}</h1>
        {lead && <p className="max-w-3xl text-lg text-muted">{lead}</p>}
      </div>
      {children}
    </div>
  );
}

function Scroller({ children }: { children: ReactNode }) {
  return <div className="flex flex-col gap-5 lg:relative lg:-mx-1 lg:min-h-0 lg:flex-1 lg:overflow-y-auto lg:px-1 lg:py-1">{children}</div>;
}

export function MentorPage() {
  const { t, lang } = useLang();
  const districtName = useDistrictName();
  const [view, setView] = useState<View>({ state: "loading" });
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<MessageKey | null>(null);

  const load = useCallback(async () => {
    try {
      const journey = await getMyJourney();
      const candidates = journey.state === "path_selected" ? (await getMentorCandidates(journey.id)).candidates : [];
      setView({ state: "ready", journey, candidates });
    } catch (err) {
      setView(isApiFailure(err) && err.status === 404 ? { state: "none" } : { state: "error" });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const act = async (key: string, fn: () => Promise<unknown>) => {
    setBusy(key);
    setError(null);
    try {
      await fn();
      await load();
    } catch (err) {
      setError(errorKey(err));
      await load();
    } finally {
      setBusy(null);
    }
  };

  if (view.state === "loading") {
    return (
      <div className="flex items-center gap-3 pt-10 text-lg text-muted" role="status">
        <Loader2 className="size-6 animate-spin text-accent" aria-hidden="true" />
        {t("mentor.loading")}
      </div>
    );
  }
  if (view.state === "error") {
    return (
      <Shell title={t("mentor.title")}>
        <Notice>{t("err.network")}</Notice>
        <Button full={false} className="self-start" onClick={() => void load()}>
          {t("status.retry")}
        </Button>
      </Shell>
    );
  }
  if (view.state === "none") {
    return (
      <Shell title={t("mentor.title")} lead={t("mentor.none.help")}>
        <Button full={false} className="self-start" onClick={() => navigate("/paths")}>
          {t("mentor.none.cta")}
        </Button>
      </Shell>
    );
  }

  const { journey, candidates } = view;
  const career = journey.career.name?.[lang] ?? journey.career.career_id;
  const mentor = journey.mentor;

  if (journey.state === "in_progress" && mentor) {
    return (
      <Shell title={t("mentor.active.title", { name: mentor.name })} lead={t("mentor.active.help", { career })}>
        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <section className="flex flex-col gap-5 rounded-2xl border border-line bg-surface p-7 shadow-(--shadow-soft)">
            <Header mentor={mentor} />
            <Tier tier={mentor.tier} />
            <ul className="flex flex-col gap-2">
              <Fact icon={Languages}>{mentor.languages.map((l) => LANGS.find((x) => x.code === l)?.label ?? l).join(", ")}</Fact>
              <Fact icon={MapPin}>{`${mentor.block}, ${districtName(mentor.district)}`}</Fact>
            </ul>
          </section>
          <section className="flex gap-4 rounded-2xl bg-ok-bg p-7 text-ok">
            <UserCheck className="mt-1 size-7 shrink-0" aria-hidden="true" />
            <div className="flex flex-col gap-1.5">
              <h2 className="text-xl font-bold">{t("mentor.active.next.title")}</h2>
              <p className="text-lg">{t("mentor.active.next.help")}</p>
            </div>
          </section>
        </div>
      </Shell>
    );
  }

  if (journey.state === "mentor_pending" && mentor && journey.request) {
    const left = hoursLeft(journey.request.expires_at);
    return (
      <Shell title={t("mentor.pending.title", { name: mentor.name })} lead={t("mentor.pending.help", { name: mentor.name })}>
        {error && <Notice>{t(error)}</Notice>}
        <LearnBanner careerId={journey.career.career_id} />
        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <section className="flex flex-col gap-5 rounded-2xl border border-line bg-surface p-7 shadow-(--shadow-soft)">
            <Header mentor={mentor} />
            <Tier tier={mentor.tier} />
            <ul className="flex flex-col gap-2">
              <Fact icon={Languages}>{mentor.languages.map((l) => LANGS.find((x) => x.code === l)?.label ?? l).join(", ")}</Fact>
              <Fact icon={MapPin}>{`${mentor.block}, ${districtName(mentor.district)}`}</Fact>
            </ul>
          </section>
          <section className="flex flex-col gap-4 rounded-2xl bg-warn-bg p-7 text-warn">
            <div className="flex items-start gap-4">
              <Hourglass className="mt-1 size-7 shrink-0" aria-hidden="true" />
              <div className="flex flex-col gap-1">
                <h2 className="text-xl font-bold">{t("mentor.pending.left", { n: left })}</h2>
                <p className="text-lg">{t("mentor.pending.why")}</p>
              </div>
            </div>
            <Button
              variant="secondary"
              full={false}
              className="h-12 self-start bg-surface text-base"
              loading={busy === "cancel"}
              onClick={() => void act("cancel", () => cancelMentorRequest(journey.id))}
            >
              {t("mentor.pending.cancel")}
            </Button>
          </section>
        </div>
      </Shell>
    );
  }

  // path_selected: choose a mentor
  const last = journey.request;
  return (
    <Shell title={t("mentor.choose.title", { career })} lead={t("mentor.choose.help")} fit>
      {last && (last.status === "declined" || last.status === "expired") && <Notice tone="info">{t(`mentor.notice.${last.status}` as MessageKey)}</Notice>}
      {error && <Notice>{t(error)}</Notice>}
      <LearnBanner careerId={journey.career.career_id} />
      <Scroller>
      {candidates.length === 0 ? (
        <section className="flex max-w-3xl gap-4 rounded-2xl border border-line bg-surface p-7 shadow-(--shadow-soft)">
          <Users className="mt-1 size-7 shrink-0 text-accent" aria-hidden="true" />
          <div className="flex flex-col gap-2">
            <h2 className="text-xl font-bold">{t("mentor.empty.title")}</h2>
            <p className="text-lg text-muted">{t("mentor.empty.help")}</p>
          </div>
        </section>
      ) : (
        <ul className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {candidates.map((c) => (
            <CandidateCard
              key={c.teacher_id}
              c={c}
              busy={busy === c.teacher_id}
              disabled={busy !== null}
              onAsk={() => void act(c.teacher_id, () => requestMentor(journey.id, c.teacher_id))}
            />
          ))}
        </ul>
      )}
      <p className="flex max-w-3xl items-start gap-2.5 text-base text-muted">
        <Check className="mt-0.5 size-5 shrink-0 text-ok" aria-hidden="true" />
        {t("mentor.note")}
      </p>
      </Scroller>
    </Shell>
  );
}
