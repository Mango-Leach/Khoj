import { useCallback, useEffect, useState } from "react";
import { PageBanner } from "../components/PageBanner";
import { CalendarClock, CheckCircle2, Loader2, Lock, ShieldCheck, Star, UserRound } from "lucide-react";
import { Button, Notice, Pill, SelectField, TextField, cx } from "../components/ui";
import { addCallSlot, cancelCallSlot, getHostCalls, setOfferingCalls, type CallContactKind, type HostCalls, type HostSlot } from "../lib/api";
import { dayLabel, spacedPhone, timeLabel, todayIst, toIso } from "../lib/calls";
import { errorKey } from "../lib/errors";
import { useLang, type MessageKey } from "../lib/i18n";
import { navigate } from "../lib/router";
import { pickText } from "../lib/text";

const SLOT_GRID = "grid grid-cols-[repeat(auto-fill,minmax(min(100%,18rem),1fr))] gap-4";

function Switch({ on, disabled, busy, onChange, label }: { on: boolean; disabled: boolean; busy: boolean; onChange: (v: boolean) => void; label: string }) {
  const { t } = useLang();
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      disabled={disabled || busy}
      onClick={() => onChange(!on)}
      className={cx(
        "inline-flex h-12 shrink-0 items-center gap-3 rounded-full border-[1.5px] pr-5 pl-1.5 text-base font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-60",
        on ? "border-accent bg-accent text-white" : "border-line-strong bg-surface text-ink",
      )}
    >
      <span className={cx("grid size-9 place-items-center rounded-full transition-colors", on ? "bg-white text-accent" : "bg-bg text-muted")} aria-hidden="true">
        {busy ? <Loader2 className="size-5 animate-spin" /> : on ? <CheckCircle2 className="size-5" /> : <span className="size-3 rounded-full bg-line-strong" />}
      </span>
      {on ? t("tcalls.on") : t("tcalls.off")}
    </button>
  );
}

function StatusChip({ slot }: { slot: HostSlot }) {
  const { t } = useLang();
  const booked = slot.status === "booked";
  return (
    <span className={cx("inline-flex shrink-0 items-center rounded-full px-3 py-1 text-sm font-semibold", booked ? "bg-ok-bg text-ok" : "bg-tint text-accent")}>
      {t(`tcalls.status.${slot.status}` as MessageKey)}
    </span>
  );
}

function SlotCard({ slot, busy, onCancel }: { slot: HostSlot; busy: boolean; onCancel: () => void }) {
  const { t, lang } = useLang();
  const [sure, setSure] = useState(false);
  const contact = slot.contact_kind === "phone" ? spacedPhone(slot.contact) : slot.contact;
  return (
    <li className="flex flex-col gap-3.5 rounded-[28px] border border-line bg-surface p-5 shadow-(--shadow-soft)">
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-[26px] leading-none font-bold tracking-tight">{timeLabel(slot.starts_at, lang)}</p>
        <StatusChip slot={slot} />
      </div>
      <div className="flex flex-col gap-0.5">
        <p className="text-base font-semibold">{dayLabel(slot.starts_at, lang)}</p>
        <p className="text-[15px] text-muted">
          {pickText(slot.career_name, lang)} · {t("calls.minutes", { n: slot.minutes })}
        </p>
      </div>

      {slot.learner && (
        <div className="flex flex-col gap-1 rounded-xl bg-bg px-3.5 py-3">
          <p className="inline-flex items-center gap-2 text-base font-semibold">
            <UserRound className="size-4 shrink-0 text-accent" aria-hidden="true" />
            {slot.learner.first_name}
            {slot.learner.age_band ? <span className="font-medium text-muted">· {slot.learner.age_band}</span> : null}
          </p>
          {slot.learner.guardian_near && (
            <p className="inline-flex items-center gap-2 text-sm font-medium text-ok">
              <ShieldCheck className="size-4 shrink-0" aria-hidden="true" />
              {t("tcalls.guardian")}
            </p>
          )}
        </div>
      )}

      <p className="text-sm break-all text-muted">{t("tcalls.contact.shown", { contact })}</p>

      <Button
        variant="secondary"
        className="mt-auto h-11 text-[15px]"
        loading={busy}
        onClick={() => {
          if (!sure) {
            setSure(true);
            window.setTimeout(() => setSure(false), 4000); // a second tap soon after confirms; otherwise it goes back
            return;
          }
          onCancel();
        }}
      >
        {sure ? t("tcalls.cancel.sure") : t("tcalls.cancel")}
      </Button>
    </li>
  );
}

function PastRow({ slot }: { slot: HostSlot }) {
  const { t, lang } = useLang();
  const text = slot.outcome === "held" ? t("tcalls.outcome.held") : slot.outcome === "missed" ? t("tcalls.outcome.missed") : t("tcalls.outcome.none");
  return (
    <li className="flex items-center justify-between gap-3 rounded-xl border border-line bg-surface px-4 py-3">
      <span className="flex min-w-0 flex-col">
        <span className="truncate text-base font-semibold">{slot.learner?.first_name}</span>
        <span className="text-sm text-muted">{dayLabel(slot.starts_at, lang)}</span>
      </span>
      <span className={cx("inline-flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1 text-sm font-semibold", slot.outcome === "held" ? "bg-ok-bg text-ok" : "bg-bg text-muted")}>
        {text}
        {slot.outcome === "held" && slot.rating ? (
          <>
            <Star className="size-3.5 fill-current" aria-hidden="true" />
            <span aria-label={t("calls.rate.n", { n: slot.rating })}>{slot.rating}</span>
          </>
        ) : null}
      </span>
    </li>
  );
}

/** Where a mentor turns "career calls" on and adds the times a learner can book. Unpaid, and never on the ledger. */
export function TeacherCallsPage() {
  const { t, lang } = useLang();
  const [data, setData] = useState<HostCalls | null>(null);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<MessageKey | null>(null);
  const [added, setAdded] = useState(false);

  const [careerId, setCareerId] = useState("");
  const [date, setDate] = useState("");
  const [time, setTime] = useState("11:00");
  const [minutes, setMinutes] = useState<30 | 45>(30);
  const [kind, setKind] = useState<CallContactKind>("link");
  const [contact, setContact] = useState("");

  const load = useCallback(async () => {
    try {
      const d = await getHostCalls();
      setData(d);
      setFailed(false);
      setCareerId((current) => (d.careers.some((c) => c.career_id === current) ? current : (d.careers[0]?.career_id ?? "")));
    } catch {
      setFailed(true);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const toggle = async (on: boolean) => {
    setBusy("switch");
    setError(null);
    try {
      setData(await setOfferingCalls(on));
    } catch (err) {
      setError(errorKey(err));
    } finally {
      setBusy(null);
    }
  };

  const add = async () => {
    setError(null);
    setAdded(false);
    if (!careerId || !date || !time || contact.trim().length < 3) {
      setError("err.generic");
      return;
    }
    setBusy("add");
    try {
      await addCallSlot({ career_id: careerId, starts_at: toIso(date, time), minutes, contact_kind: kind, contact: contact.trim() });
      setAdded(true);
      await load();
    } catch (err) {
      setError(errorKey(err));
    } finally {
      setBusy(null);
    }
  };

  const cancel = async (id: string) => {
    setBusy(id);
    setError(null);
    try {
      await cancelCallSlot(id);
      await load();
    } catch (err) {
      setError(errorKey(err));
    } finally {
      setBusy(null);
    }
  };

  const today = todayIst();
  const last = todayIst(Date.now() + 30 * 86_400_000);
  const career = data?.careers.find((c) => c.career_id === careerId);

  return (
    // From 1280 px up the page is exactly one screen tall (the shell adds 76 px of header and 56 px of bottom padding), and only the two panels below scroll.
    <div className="flex flex-col gap-8 pt-2 xl:-mb-10 xl:h-[calc(100dvh-92px)] xl:gap-4">
      <PageBanner title={t("tcalls.title")} lead={t("tcalls.lead")} />

      {failed && <Notice>{t("err.network")}</Notice>}
      {!data && !failed && (
        <div className="flex items-center gap-3 text-lg text-muted" role="status">
          <Loader2 className="size-6 animate-spin text-accent" aria-hidden="true" />
          {t("req.loading")}
        </div>
      )}

      {data && (
        <>
          {!data.can_host ? (
            <section className="flex flex-col gap-4 rounded-2xl bg-warn-bg p-6 text-warn sm:flex-row sm:items-center">
              <Lock className="size-7 shrink-0" aria-hidden="true" />
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                <h2 className="text-xl font-bold">{t("tcalls.locked.title")}</h2>
                <p className="text-lg">{t("tcalls.locked.help")}</p>
              </div>
              <Button full={false} className="h-12 bg-warn text-base hover:bg-warn" onClick={() => navigate("/t/assess")}>
                {t("req.locked.cta")}
              </Button>
            </section>
          ) : (
            <section className="flex flex-col gap-3 rounded-[28px] border border-line bg-surface p-4 shadow-(--shadow-soft) sm:flex-row sm:items-center sm:gap-4" aria-labelledby="tcalls-switch">
              <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-tint text-accent" aria-hidden="true">
                <CalendarClock className="size-5" />
              </span>
              <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                <h2 id="tcalls-switch" className="text-lg leading-tight font-bold">
                  {t("tcalls.switch.title")}
                </h2>
                <p className="max-w-4xl text-[15px] text-muted">{t("tcalls.switch.help")}</p>
                <p className="max-w-4xl text-sm text-muted">{t("tcalls.label.note")}</p>
              </div>
              <Switch on={data.offers_calls} disabled={false} busy={busy === "switch"} onChange={(v) => void toggle(v)} label={t("tcalls.switch.title")} />
            </section>
          )}

          {error && <Notice>{t(error)}</Notice>}

          {data.offers_calls && (
            <div className="grid items-start gap-8 xl:min-h-0 xl:flex-1 xl:grid-cols-[minmax(340px,440px)_minmax(0,1fr)] xl:grid-rows-1 xl:items-stretch">
              {/* On a wide screen the form fills the height left on the screen and scrolls on its own. Its rows must not shrink, or the button squashes. */}
              <section
                className="flex flex-col gap-5 rounded-[28px] border border-line bg-surface p-5 shadow-(--shadow-soft) sm:p-6 xl:min-h-0 xl:overflow-y-auto [&>*]:shrink-0"
                aria-labelledby="tcalls-add"
              >
                <h2 id="tcalls-add" className="text-xl font-bold tracking-tight">
                  {t("tcalls.add.title")}
                </h2>
                <SelectField label={t("tcalls.field.career")} value={careerId} onChange={(e) => setCareerId(e.target.value)}>
                  {data.careers.map((c) => (
                    <option key={c.career_id} value={c.career_id}>
                      {pickText(c.name, lang)}
                    </option>
                  ))}
                </SelectField>
                {career && (
                  <p className="-mt-2 inline-flex items-start gap-2 text-[15px] font-medium text-ok">
                    <ShieldCheck className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                    {t("calls.verified", { skills: career.verified_in.map((s) => s.name[lang] ?? s.name.en).join(", ") })}
                  </p>
                )}
                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
                  <TextField label={t("tcalls.field.date")} type="date" min={today} max={last} value={date} onChange={(e) => setDate(e.target.value)} />
                  <TextField label={t("tcalls.field.time")} type="time" step={900} value={time} onChange={(e) => setTime(e.target.value)} />
                </div>
                <p className="-mt-2 text-sm text-muted">{t("tcalls.hours.help")}</p>

                <div className="flex flex-col gap-2">
                  <p className="text-base font-semibold">{t("tcalls.field.minutes")}</p>
                  <div role="radiogroup" aria-label={t("tcalls.field.minutes")} className="flex flex-wrap gap-2">
                    {([30, 45] as const).map((m) => (
                      <Pill key={m} selected={minutes === m} onSelect={() => setMinutes(m)}>
                        {t("calls.minutes", { n: m })}
                      </Pill>
                    ))}
                  </div>
                </div>

                <div className="flex flex-col gap-2">
                  <p className="text-base font-semibold">{t("tcalls.field.contact")}</p>
                  <div role="radiogroup" aria-label={t("tcalls.field.contact")} className="flex flex-wrap gap-2">
                    <Pill selected={kind === "link"} onSelect={() => setKind("link")}>
                      {t("tcalls.contact.link")}
                    </Pill>
                    <Pill selected={kind === "phone"} onSelect={() => setKind("phone")}>
                      {t("tcalls.contact.phone")}
                    </Pill>
                  </div>
                </div>
                <TextField
                  label={kind === "link" ? t("tcalls.field.link") : t("tcalls.field.phone")}
                  help={t("tcalls.contact.help")}
                  type={kind === "link" ? "url" : "tel"}
                  inputMode={kind === "link" ? "url" : "numeric"}
                  autoComplete="off"
                  maxLength={200}
                  value={contact}
                  onChange={(e) => setContact(e.target.value)}
                />

                <Button className="h-12 text-base" loading={busy === "add"} disabled={!date || contact.trim().length < 3} onClick={() => void add()}>
                  {t("tcalls.add")}
                </Button>
                {added && (
                  <p className="inline-flex items-center gap-2 text-base font-semibold text-ok" role="status">
                    <CheckCircle2 className="size-5" aria-hidden="true" />
                    {t("tcalls.added")}
                  </p>
                )}
              </section>

              <div className="flex min-w-0 flex-col gap-8 xl:min-h-0 xl:overflow-y-auto xl:pr-1">
                <section className="flex flex-col gap-4" aria-labelledby="tcalls-upcoming">
                  <h2 id="tcalls-upcoming" className="text-2xl font-bold tracking-tight">
                    {t("tcalls.upcoming")}
                  </h2>
                  {data.upcoming.length === 0 ? (
                    <p className="text-lg text-muted">{t("tcalls.empty")}</p>
                  ) : (
                    <ul className={SLOT_GRID}>
                      {data.upcoming.map((s) => (
                        <SlotCard key={s.id} slot={s} busy={busy === s.id} onCancel={() => void cancel(s.id)} />
                      ))}
                    </ul>
                  )}
                </section>

                {data.past.length > 0 && (
                  <section className="flex flex-col gap-3" aria-labelledby="tcalls-past">
                    <h2 id="tcalls-past" className="text-xl font-bold tracking-tight">
                      {t("tcalls.past")}
                    </h2>
                    <ul className="grid gap-3 md:grid-cols-2">
                      {data.past.map((s) => (
                        <PastRow key={s.id} slot={s} />
                      ))}
                    </ul>
                  </section>
                )}
              </div>
            </div>
          )}

          {!data.offers_calls && data.upcoming.length > 0 && (
            <section className="flex flex-col gap-4" aria-labelledby="tcalls-upcoming-off">
              <h2 id="tcalls-upcoming-off" className="text-2xl font-bold tracking-tight">
                {t("tcalls.upcoming")}
              </h2>
              <ul className={SLOT_GRID}>
                {data.upcoming.map((s) => (
                  <SlotCard key={s.id} slot={s} busy={busy === s.id} onCancel={() => void cancel(s.id)} />
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  );
}
