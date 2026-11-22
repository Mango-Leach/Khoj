import { useCallback, useEffect, useMemo, useState } from "react";
import { PageBanner } from "../components/PageBanner";
import { CalendarClock, CheckCircle2, Languages, Loader2, MapPin, PhoneCall, ShieldCheck, Star, Video } from "lucide-react";
import { Button, Choice, Notice, Pill, cx } from "../components/ui";
import {
  bookCall,
  cancelCall,
  getCalls,
  isApiFailure,
  sendCallFeedback,
  type CallHost,
  type CallsOverview,
  type MyCall,
  type OpenCall,
} from "../lib/api";
import { contactHref, dayKey, dayLabel, spacedPhone, timeLabel } from "../lib/calls";
import { errorKey } from "../lib/errors";
import { LANGS, useLang, type MessageKey } from "../lib/i18n";
import { navigate } from "../lib/router";
import { pickText } from "../lib/text";
import { useDistrictName } from "../lib/useDistrictName";

const SLOT_GRID = "grid grid-cols-[repeat(auto-fill,minmax(min(100%,19rem),1fr))] gap-5";

type State = "loading" | "nopath" | "error" | "ready";

function HostHeader({ host }: { host: CallHost }) {
  const { t } = useLang();
  return (
    <div className="flex items-center gap-3.5">
      <span className="grid size-12 shrink-0 place-items-center rounded-full bg-accent text-xl font-bold text-white" aria-hidden="true">
        {host.name.trim().charAt(0).toUpperCase()}
      </span>
      <div className="flex min-w-0 flex-col gap-0.5">
        <p className="truncate text-xl leading-tight font-bold">{host.name}</p>
        <p className="text-[15px] text-muted">{host.roles.map((r) => t(`teacherRole.${r}` as MessageKey)).join(", ")}</p>
      </div>
    </div>
  );
}

/** What a host is verified in. It says skill, never that they work in the job. */
function Verified({ host }: { host: CallHost }) {
  const { t, lang } = useLang();
  if (host.verified_in.length === 0) return null;
  const skills = host.verified_in.map((s) => s.name[lang] ?? s.name.en).join(", ");
  return (
    <p className="inline-flex items-start gap-2 self-start rounded-xl bg-ok-bg px-3 py-2 text-[15px] leading-snug font-semibold text-ok">
      <ShieldCheck className="mt-px size-5 shrink-0" aria-hidden="true" />
      {t("calls.verified", { skills })}
    </p>
  );
}

function Facts({ host }: { host: CallHost }) {
  const { t } = useLang();
  const districtName = useDistrictName();
  const langs = host.languages.map((l) => LANGS.find((x) => x.code === l)?.label ?? l).join(", ");
  return (
    <ul className="flex flex-col gap-1.5 text-[15px]">
      <li className={cx("inline-flex items-center gap-2", host.speaks_your_language ? "font-semibold text-ok" : "text-muted")}>
        <Languages className="size-4 shrink-0" aria-hidden="true" />
        {host.speaks_your_language ? t("mentor.lang.same", { languages: langs }) : t("mentor.lang.other", { languages: langs })}
      </li>
      <li className="inline-flex items-center gap-2 text-muted">
        <MapPin className="size-4 shrink-0" aria-hidden="true" />
        {t("calls.place", { block: host.block, district: districtName(host.district) })}
      </li>
    </ul>
  );
}

function SlotCard({
  slot,
  canBook,
  needsGuardian,
  picking,
  busy,
  error,
  onPick,
  onBook,
}: {
  slot: OpenCall;
  canBook: boolean;
  needsGuardian: boolean;
  picking: boolean;
  busy: boolean;
  error: MessageKey | null;
  onPick: (open: boolean) => void;
  onBook: (agreed: boolean, guardianNear: boolean) => void;
}) {
  const { t, lang } = useLang();
  const [agreed, setAgreed] = useState(false);
  const [guardian, setGuardian] = useState(false);
  const ready = agreed && (!needsGuardian || guardian);
  const rules: MessageKey[] = ["calls.rule.1", "calls.rule.2", "calls.rule.3"];

  return (
    <li className={cx("flex flex-col gap-4 rounded-2xl border bg-surface p-5 shadow-(--shadow-soft) transition-colors", picking ? "border-accent" : "border-line")}>
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-[26px] leading-none font-bold tracking-tight">{timeLabel(slot.starts_at, lang)}</p>
        <p className="text-[15px] font-semibold text-muted">{t("calls.minutes", { n: slot.minutes })}</p>
      </div>
      <HostHeader host={slot.host} />
      <Verified host={slot.host} />
      <Facts host={slot.host} />

      {!picking && (
        <Button className="mt-auto h-12 text-base" disabled={!canBook} onClick={() => onPick(true)}>
          {t("calls.book")}
        </Button>
      )}

      {picking && (
        <div className="mt-auto flex flex-col gap-4 border-t border-line pt-4">
          <div className="flex flex-col gap-2">
            <p className="text-base font-bold text-deep">{t("calls.rules.title")}</p>
            <ul className="flex list-disc flex-col gap-1 pl-5 text-[15px] marker:text-line-strong">
              {rules.map((k) => (
                <li key={k}>{t(k)}</li>
              ))}
            </ul>
          </div>
          <div className="flex flex-col gap-2.5">
            <Choice type="checkbox" compact selected={agreed} onSelect={() => setAgreed((v) => !v)} title={t("calls.rules.agree")} />
            {needsGuardian && (
              <Choice type="checkbox" compact selected={guardian} onSelect={() => setGuardian((v) => !v)} title={t("calls.guardian")} description={t("calls.guardian.help")} />
            )}
          </div>
          {error && <Notice>{t(error)}</Notice>}
          <div className="flex flex-col gap-2.5">
            <Button className="h-12 text-base" loading={busy} disabled={!ready} onClick={() => onBook(agreed, guardian)}>
              {t("calls.confirm")}
            </Button>
            <Button variant="secondary" className="h-12 text-base" disabled={busy} onClick={() => onPick(false)}>
              {t("calls.notNow")}
            </Button>
          </div>
        </div>
      )}
    </li>
  );
}

function When({ call }: { call: MyCall }) {
  const { t, lang } = useLang();
  return (
    <p className="text-[22px] leading-snug font-bold tracking-tight">
      {dayLabel(call.starts_at, lang)}, {timeLabel(call.starts_at, lang)}
      <span className="ml-2 text-base font-semibold text-muted">{t("calls.minutes", { n: call.minutes })}</span>
    </p>
  );
}

/** The booked call, with the one thing a learner needs: how to join it. */
function MyCallCard({ call, needsGuardian, busy, onGiveBack }: { call: MyCall; needsGuardian: boolean; busy: boolean; onGiveBack: () => void }) {
  const { t } = useLang();
  const phone = call.contact_kind === "phone";
  return (
    <section className="flex flex-col gap-5 rounded-2xl border border-accent/30 bg-tint p-5 sm:p-6 lg:flex-row lg:items-center lg:gap-8" aria-labelledby={`mine-${call.id}`}>
      <div className="flex min-w-0 flex-1 items-start gap-4">
        <span className="grid size-12 shrink-0 place-items-center rounded-xl bg-surface text-accent shadow-(--shadow-soft)" aria-hidden="true">
          <CalendarClock className="size-6" />
        </span>
        <div className="flex min-w-0 flex-col gap-1.5">
          <h2 id={`mine-${call.id}`} className="text-xl font-bold text-deep">
            {t("calls.mine.title")}
          </h2>
          <When call={call} />
          {call.host && <p className="text-base text-deep">{t("calls.mine.with", { name: call.host.name })}</p>}
          {call.host && <Verified host={call.host} />}
          {needsGuardian && <p className="text-[15px] text-muted">{t("calls.guardian.help")}</p>}
        </div>
      </div>
      <div className="flex shrink-0 flex-col gap-3 lg:w-72">
        {phone && <p className="text-sm text-muted">{t("calls.phone.help")}</p>}
        <a
          href={contactHref(call.contact_kind, call.contact)}
          {...(phone ? {} : { target: "_blank", rel: "noopener noreferrer" })}
          className="inline-flex h-12 items-center justify-center gap-2.5 rounded-full bg-night px-6 text-base font-semibold text-white transition-colors hover:bg-black"
        >
          {phone ? <PhoneCall className="size-5" aria-hidden="true" /> : <Video className="size-5" aria-hidden="true" />}
          {phone ? t("calls.phone", { number: spacedPhone(call.contact) }) : t("calls.join")}
        </a>
        <Button variant="secondary" className="h-12 text-base" loading={busy} onClick={onGiveBack}>
          {t("calls.giveBack")}
        </Button>
      </div>
    </section>
  );
}

/** After the call has ended: did it happen, and was it useful. Only the learner answers. */
function AskCard({ call, onSent }: { call: MyCall; onSent: () => void }) {
  const { t, lang } = useLang();
  const [yes, setYes] = useState(false);
  const [rating, setRating] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<MessageKey | null>(null);

  const send = async (tookPlace: boolean) => {
    setBusy(true);
    setError(null);
    try {
      await sendCallFeedback(call.id, tookPlace && rating ? { took_place: true, rating } : { took_place: tookPlace });
      onSent();
    } catch (err) {
      setError(errorKey(err));
      setBusy(false);
    }
  };

  return (
    <section className="flex flex-col gap-4 rounded-[28px] border border-line bg-surface p-5 shadow-(--shadow-soft) sm:p-6" aria-labelledby={`ask-${call.id}`}>
      <div className="flex flex-col gap-1">
        <h2 id={`ask-${call.id}`} className="text-xl font-bold">
          {t("calls.ask.title")}
        </h2>
        <p className="text-base text-muted">
          {dayLabel(call.starts_at, lang)}, {timeLabel(call.starts_at, lang)}
          {call.host ? ` · ${call.host.name}` : ""}
        </p>
      </div>
      {!yes ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:max-w-xl">
          <Button className="h-12 text-base" disabled={busy} onClick={() => setYes(true)}>
            {t("calls.ask.yes")}
          </Button>
          <Button variant="secondary" className="h-12 text-base" loading={busy} onClick={() => void send(false)}>
            {t("calls.ask.no")}
          </Button>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <p className="text-base font-semibold">{t("calls.rate")}</p>
          <div role="radiogroup" aria-label={t("calls.rate")} className="flex flex-wrap gap-2">
            {[1, 2, 3, 4, 5].map((n) => (
              <Pill key={n} selected={rating === n} onSelect={() => setRating(n)}>
                {t("calls.rate.n", { n })}
              </Pill>
            ))}
          </div>
          <Button full={false} className="h-12 self-start text-base" loading={busy} onClick={() => void send(true)}>
            {t("calls.send")}
          </Button>
        </div>
      )}
      {error && <Notice>{t(error)}</Notice>}
    </section>
  );
}

function PastRow({ call }: { call: MyCall }) {
  const { t, lang } = useLang();
  const held = call.outcome === "held";
  return (
    <li className="flex items-center justify-between gap-3 rounded-xl border border-line bg-surface px-4 py-3">
      <span className="flex min-w-0 flex-col">
        <span className="truncate text-base font-semibold">{call.host?.name}</span>
        <span className="text-sm text-muted">{dayLabel(call.starts_at, lang)}</span>
      </span>
      <span className={cx("inline-flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1 text-sm font-semibold", held ? "bg-ok-bg text-ok" : "bg-bg text-muted")}>
        {held ? <CheckCircle2 className="size-4" aria-hidden="true" /> : null}
        {held && call.rating ? (
          <>
            {t("calls.outcome.held")}
            <Star className="size-3.5 fill-current" aria-hidden="true" />
            <span aria-label={t("calls.rate.n", { n: call.rating })}>{call.rating}</span>
          </>
        ) : held ? (
          t("calls.outcome.held")
        ) : (
          t("calls.outcome.missed")
        )}
      </span>
    </li>
  );
}

function NoPath() {
  const { t } = useLang();
  return (
    <section className="flex max-w-2xl flex-col items-start gap-4 rounded-[28px] border border-line bg-surface p-7 shadow-(--shadow-soft)">
      <PhoneCall className="size-8 text-accent" aria-hidden="true" />
      <h2 className="text-2xl font-bold tracking-tight">{t("calls.nopath.title")}</h2>
      <p className="text-lg text-muted">{t("calls.nopath.help")}</p>
      <Button full={false} onClick={() => navigate("/paths")}>
        {t("opp.locked.cta")}
      </Button>
    </section>
  );
}

/** "A day in the life": book a 30 to 45 minute call with a mentor who is verified in the skill for the learner's path. */
export function CallsPage() {
  const { t, lang } = useLang();
  const [data, setData] = useState<CallsOverview | null>(null);
  const [state, setState] = useState<State>("loading");
  const [picking, setPicking] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<MessageKey | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await getCalls());
      setState("ready");
    } catch (err) {
      setState(isApiFailure(err) && err.code === "no_path" ? "nopath" : "error");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const book = async (id: string, agreed: boolean, guardianNear: boolean) => {
    setBusy(id);
    setError(null);
    try {
      await bookCall(id, { agreed, guardian_near: guardianNear });
      setPicking(null);
      await load();
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      setError(errorKey(err));
      await load(); // another learner may have taken the time just now
    } finally {
      setBusy(null);
    }
  };

  const giveBack = async (id: string) => {
    setBusy(id);
    setError(null);
    try {
      await cancelCall(id);
      await load();
    } catch (err) {
      setError(errorKey(err));
    } finally {
      setBusy(null);
    }
  };

  const days = useMemo(() => {
    const map = new Map<string, OpenCall[]>();
    for (const s of data?.slots ?? []) map.set(dayKey(s.starts_at), [...(map.get(dayKey(s.starts_at)) ?? []), s]);
    return [...map.values()];
  }, [data]);

  const asking = (data?.past ?? []).filter((c) => c.outcome === null);
  const recorded = (data?.past ?? []).filter((c) => c.outcome !== null);
  const title = t("calls.title");

  return (
    <div className="flex flex-col gap-8 pt-2">
      <PageBanner title={title} lead={data ? t("calls.lead", { career: pickText(data.career_name, lang) }) : undefined} />

      {state === "loading" && (
        <p className="flex items-center gap-3 text-lg text-muted" role="status">
          <Loader2 className="size-5 animate-spin text-accent" aria-hidden="true" />
          {t("req.loading")}
        </p>
      )}
      {state === "error" && <Notice>{t("err.network")}</Notice>}
      {state === "nopath" && <NoPath />}
      {error && state === "ready" && !picking && <Notice>{t(error)}</Notice>}

      {data && state === "ready" && (
        <>
          {data.upcoming.map((c) => (
            <MyCallCard key={c.id} call={c} needsGuardian={data.needs_guardian} busy={busy === c.id} onGiveBack={() => void giveBack(c.id)} />
          ))}
          {asking.map((c) => (
            <AskCard key={c.id} call={c} onSent={() => void load()} />
          ))}

          <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_320px]">
            <div className="flex min-w-0 flex-col gap-8">
              <div className="flex flex-col gap-1">
                <h2 className="text-2xl font-bold tracking-tight">{t("calls.slots.title")}</h2>
                {!data.can_book && <p className="text-base text-muted">{t("calls.slots.limit")}</p>}
              </div>

              {days.length === 0 && !data.can_book ? null : days.length === 0 ? (
                <section className="flex max-w-2xl gap-4 rounded-[28px] border border-line bg-surface p-6 shadow-(--shadow-soft)">
                  <CalendarClock className="mt-0.5 size-7 shrink-0 text-accent" aria-hidden="true" />
                  <div className="flex flex-col gap-1">
                    <h3 className="text-xl font-bold">{t("calls.slots.empty.title")}</h3>
                    <p className="text-base text-muted">{t("calls.slots.empty.help")}</p>
                  </div>
                </section>
              ) : (
                days.map((group) => (
                  <section key={dayKey(group[0].starts_at)} className="flex flex-col gap-4" aria-label={dayLabel(group[0].starts_at, lang)}>
                    <h3 className="text-lg font-bold text-deep">{dayLabel(group[0].starts_at, lang)}</h3>
                    <ul className={SLOT_GRID}>
                      {group.map((slot) => (
                        <SlotCard
                          key={slot.id}
                          slot={slot}
                          canBook={data.can_book}
                          needsGuardian={data.needs_guardian}
                          picking={picking === slot.id}
                          busy={busy === slot.id}
                          error={picking === slot.id ? error : null}
                          onPick={(open) => {
                            setError(null);
                            setPicking(open ? slot.id : null);
                          }}
                          onBook={(agreed, guardianNear) => void book(slot.id, agreed, guardianNear)}
                        />
                      ))}
                    </ul>
                  </section>
                ))
              )}

              {recorded.length > 0 && (
                <section className="flex flex-col gap-3" aria-labelledby="calls-past">
                  <h2 id="calls-past" className="text-xl font-bold tracking-tight">
                    {t("calls.past.title")}
                  </h2>
                  <ul className="grid gap-3 md:grid-cols-2">
                    {recorded.map((c) => (
                      <PastRow key={c.id} call={c} />
                    ))}
                  </ul>
                </section>
              )}
            </div>

            <aside className="flex flex-col gap-5 rounded-[28px] border border-line bg-surface p-5 shadow-(--shadow-soft) lg:sticky lg:top-4" aria-labelledby="calls-how">
              <h2 id="calls-how" className="text-xl font-bold tracking-tight">
                {t("calls.how.title")}
              </h2>
              <ol className="flex flex-col gap-3.5">
                {(["calls.how.1", "calls.how.2", "calls.how.3"] as const).map((k, i) => (
                  <li key={k} className="flex items-start gap-3 text-[15px] leading-snug">
                    <span className="grid size-7 shrink-0 place-items-center rounded-full bg-tint text-sm font-bold text-accent" aria-hidden="true">
                      {i + 1}
                    </span>
                    <span className="pt-0.5">{t(k)}</span>
                  </li>
                ))}
              </ol>
              <p className="border-t border-line pt-4 text-[15px] text-muted">{t("calls.honest")}</p>
            </aside>
          </div>
        </>
      )}
    </div>
  );
}
