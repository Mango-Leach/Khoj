import { useCallback, useEffect, useState } from "react";
import { PageBanner } from "../components/PageBanner";
import { Check, Handshake, Loader2, Lock, MapPin, MessageCircle, PhoneCall, ShieldAlert, ShieldCheck, Sparkles, UserRound } from "lucide-react";
import { Button, Choice, Notice, Pill, TextField, cx } from "../components/ui";
import {
  answerConnect,
  blockPerson,
  getConnect,
  isApiFailure,
  removeConnection,
  reportPerson,
  requestConnect,
  setMyCard,
  type CallContactKind,
  type ConnectOverview,
  type PeerCard,
  type PeerConnection,
  type ReportReason,
} from "../lib/api";
import { contactHref, spacedPhone } from "../lib/calls";
import { errorKey } from "../lib/errors";
import { useLang, type MessageKey } from "../lib/i18n";
import { navigate } from "../lib/router";
import { useSession } from "../lib/session";
import { pickText } from "../lib/text";

type Ready = Extract<ConnectOverview, { eligible: true }>;
type State = "loading" | "nopath" | "error" | "ready";

const CARD_GRID = "grid grid-cols-[repeat(auto-fill,minmax(min(100%,19rem),1fr))] gap-5";
const REASONS: ReportReason[] = ["pressure", "unsafe", "spam", "other"];

function Avatar({ name }: { name: string }) {
  return (
    <span className="grid size-12 shrink-0 place-items-center rounded-full bg-accent text-xl font-bold text-white" aria-hidden="true">
      {name.trim().charAt(0).toUpperCase()}
    </span>
  );
}

/** One person: a first name, the state, the path and the skills. Nothing else exists to show. */
function Person({ card }: { card: PeerCard }) {
  const { t, lang } = useLang();
  const shared = new Set(card.shared_skills);
  return (
    <div className="flex min-w-0 flex-col gap-3">
      <div className="flex items-center gap-3.5">
        <Avatar name={card.first_name} />
        <div className="flex min-w-0 flex-col gap-0.5">
          <p className="truncate text-xl leading-tight font-bold">{card.first_name}</p>
          {card.state && (
            <p className="inline-flex items-center gap-1.5 text-[15px] text-muted">
              <MapPin className="size-4 shrink-0" aria-hidden="true" />
              {card.state}
            </p>
          )}
        </div>
      </div>
      {card.career_name && (
        <p className="flex flex-wrap items-center gap-2 text-[15px] font-semibold text-deep">
          {pickText(card.career_name, lang)}
          {card.same_path && <span className="rounded-full bg-ok-bg px-2.5 py-0.5 text-sm font-semibold text-ok">{t("connect.card.same")}</span>}
        </p>
      )}
      {card.skills.length > 0 && (
        <ul className="flex flex-wrap gap-1.5">
          {card.skills.map((s) => (
            <li
              key={s.id}
              className={cx("rounded-full px-2.5 py-1 text-sm font-medium", shared.has(s.id) ? "bg-tint text-accent ring-1 ring-accent/30" : "bg-bg text-muted")}
              title={shared.has(s.id) ? t("connect.card.shared") : undefined}
            >
              {shared.has(s.id) && <Sparkles className="mr-1 inline size-3.5 align-[-2px]" aria-label={t("connect.card.shared")} />}
              {pickText(s.name, lang)}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Block or report. A report also blocks, and says nothing about what the team will do next. */
function SafetyMenu({ cardId, onDone }: { cardId: string; onDone: () => void }) {
  const { t } = useLang();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState<ReportReason | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<MessageKey | null>(null);

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      onDone();
    } catch (err) {
      setError(errorKey(err));
      setBusy(false);
    }
  };

  if (!open)
    return (
      <button type="button" className="inline-flex items-center gap-1.5 self-start text-sm font-semibold text-muted underline-offset-2 hover:text-deep hover:underline" onClick={() => setOpen(true)}>
        <ShieldAlert className="size-4" aria-hidden="true" />
        {t("connect.safety")}
      </button>
    );
  return (
    <div className="flex flex-col gap-3 rounded-xl bg-bg p-3.5">
      <p className="text-sm font-bold text-deep">{t("connect.report.why")}</p>
      <div role="radiogroup" aria-label={t("connect.report.why")} className="flex flex-wrap gap-2">
        {REASONS.map((r) => (
          <Pill key={r} selected={reason === r} onSelect={() => setReason(r)}>
            {t(`connect.reason.${r}` as MessageKey)}
          </Pill>
        ))}
      </div>
      {error && <Notice>{t(error)}</Notice>}
      <div className="flex flex-col gap-2">
        <Button className="h-11 text-[15px]" loading={busy} disabled={!reason} onClick={() => reason && void run(() => reportPerson(cardId, reason))}>
          {t("connect.report")}
        </Button>
        <Button variant="secondary" className="h-11 text-[15px]" disabled={busy} onClick={() => void run(() => blockPerson(cardId))}>
          {t("connect.block")}
        </Button>
        <button type="button" className="text-sm font-semibold text-muted hover:text-deep" disabled={busy} onClick={() => setOpen(false)}>
          {t("calls.notNow")}
        </button>
      </div>
    </div>
  );
}

function SuggestionCard({ card, canAsk, busy, onAsk, onSafety }: { card: PeerCard; canAsk: boolean; busy: boolean; onAsk: () => void; onSafety: () => void }) {
  const { t } = useLang();
  return (
    <li className="flex flex-col gap-4 rounded-[28px] border border-line bg-surface p-5 shadow-(--shadow-soft)">
      <Person card={card} />
      <div className="mt-auto flex flex-col gap-3">
        <Button className="h-12 text-base" loading={busy} disabled={!canAsk} onClick={onAsk}>
          {t("connect.ask")}
        </Button>
        <SafetyMenu cardId={card.card_id} onDone={onSafety} />
      </div>
    </li>
  );
}

/** The one way to reach a connection, as buttons: call, WhatsApp, or open their link. */
function Reach({ conn }: { conn: PeerConnection }) {
  const { t } = useLang();
  if (!conn.reach || !conn.reach_kind) return <p className="text-[15px] text-muted">{t("connect.reach.off")}</p>;
  const btn = "inline-flex h-11 items-center justify-center gap-2 rounded-full px-5 text-[15px] font-semibold transition-colors";
  if (conn.reach_kind === "link")
    return (
      <a href={conn.reach} target="_blank" rel="noopener noreferrer" className={cx(btn, "bg-night text-white hover:bg-black")}>
        <MessageCircle className="size-5" aria-hidden="true" />
        {t("connect.reach.link")}
      </a>
    );
  return (
    <div className="flex flex-wrap gap-2.5">
      <a href={contactHref("phone", conn.reach)} className={cx(btn, "bg-night text-white hover:bg-black")}>
        <PhoneCall className="size-5" aria-hidden="true" />
        {t("connect.reach.phone", { number: spacedPhone(conn.reach) })}
      </a>
      <a href={`https://wa.me/91${conn.reach}`} target="_blank" rel="noopener noreferrer" className={cx(btn, "border-[1.5px] border-line-strong bg-surface text-ink hover:bg-bg")}>
        <MessageCircle className="size-5" aria-hidden="true" />
        {t("connect.reach.whatsapp")}
      </a>
    </div>
  );
}

function MyCardPanel({ data, onSaved }: { data: Ready; onSaved: (d: ConnectOverview) => void }) {
  const { t, lang } = useLang();
  const { profile } = useSession();
  const first = (profile?.data.name ?? "").trim().split(" ")[0];
  const [kind, setKind] = useState<CallContactKind>(data.me.reach_kind);
  const [reach, setReach] = useState(data.me.reach);
  const [agreed, setAgreed] = useState(data.me.visible);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<MessageKey | null>(null);
  const [saved, setSaved] = useState(false);

  // the server tidies a number (spaces, +91), so show back what it kept
  useEffect(() => {
    setKind(data.me.reach_kind);
    setReach(data.me.reach);
  }, [data.me.reach_kind, data.me.reach]);

  const save = async (visible: boolean) => {
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      onSaved(await setMyCard({ visible, reach_kind: kind, reach: reach.trim(), agreed }));
      setSaved(true);
    } catch (err) {
      setError(errorKey(err));
    } finally {
      setBusy(false);
    }
  };

  const on = data.me.visible;
  return (
    <section className="flex flex-col gap-5 rounded-[28px] border border-line bg-surface p-5 shadow-(--shadow-soft) lg:sticky lg:top-4 xl:static xl:h-full xl:min-h-0 xl:overflow-y-auto [&>*]:shrink-0" aria-labelledby="connect-me">
      <div className="flex items-start justify-between gap-3">
        <h2 id="connect-me" className="text-xl font-bold tracking-tight">
          {t("connect.me.title")}
        </h2>
        <span className={cx("inline-flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1 text-sm font-semibold", on ? "bg-ok-bg text-ok" : "bg-bg text-muted")}>
          {on ? <Check className="size-4" aria-hidden="true" /> : <Lock className="size-4" aria-hidden="true" />}
          {on ? t("connect.me.live") : t("connect.me.hidden")}
        </span>
      </div>
      <p className="text-[15px] text-muted">{t("connect.me.help")}</p>

      <div className="flex flex-col gap-2 rounded-xl bg-bg p-4">
        <p className="inline-flex items-center gap-2 text-base font-bold">
          <UserRound className="size-4 text-accent" aria-hidden="true" />
          {first}
        </p>
        <p className="text-[15px] text-muted">{pickText(data.career_name, lang)}</p>
        {data.my_skills.length > 0 && <p className="text-sm text-muted">{data.my_skills.map((s) => pickText(s.name, lang)).join(", ")}</p>}
      </div>

      <div className="flex flex-col gap-2">
        <p className="text-base font-semibold">{t("connect.reach.title")}</p>
        <div role="radiogroup" aria-label={t("connect.reach.title")} className="flex flex-wrap gap-2">
          <Pill selected={kind === "phone"} onSelect={() => setKind("phone")}>
            {t("connect.reach.kind.phone")}
          </Pill>
          <Pill selected={kind === "link"} onSelect={() => setKind("link")}>
            {t("connect.reach.kind.link")}
          </Pill>
        </div>
      </div>
      <TextField
        label={kind === "link" ? t("tcalls.field.link") : t("tcalls.field.phone")}
        help={t("connect.reach.help")}
        type={kind === "link" ? "url" : "tel"}
        inputMode={kind === "link" ? "url" : "numeric"}
        autoComplete="off"
        maxLength={200}
        value={reach}
        onChange={(e) => setReach(e.target.value)}
      />
      <Choice type="checkbox" compact selected={agreed} onSelect={() => setAgreed((v) => !v)} title={t("connect.agree")} />
      {error && <Notice>{t(error)}</Notice>}
      <div className="flex flex-col gap-2.5">
        <Button className="h-12 text-base" loading={busy} disabled={!agreed || reach.trim().length < 3} onClick={() => void save(true)}>
          {on ? t("connect.me.save") : t("connect.me.on")}
        </Button>
        {on && (
          <Button variant="secondary" className="h-12 text-base" disabled={busy} onClick={() => void save(false)}>
            {t("connect.me.off")}
          </Button>
        )}
      </div>
      {saved && (
        <p className="inline-flex items-center gap-2 text-base font-semibold text-ok" role="status">
          <Check className="size-5" aria-hidden="true" />
          {t("connect.me.saved")}
        </p>
      )}

      <section className="flex flex-col gap-3 border-t border-line pt-5" aria-labelledby="connect-tips">
        <h3 id="connect-tips" className="inline-flex items-center gap-2 text-lg font-bold tracking-tight">
          <ShieldCheck className="size-5 text-ok" aria-hidden="true" />
          {t("connect.tips.title")}
        </h3>
        <ul className="flex list-disc flex-col gap-1.5 pl-5 text-[15px] marker:text-line-strong">
          {(["connect.tip.1", "connect.tip.2", "connect.tip.3"] as const).map((k) => (
            <li key={k}>{t(k)}</li>
          ))}
        </ul>
        <p className="text-[15px] text-muted">{t("connect.honest")}</p>
      </section>
    </section>
  );
}

/** Connect: adult learners with similar goals introduce themselves, then talk however they like outside KHOJ. */
export function ConnectPage() {
  const { t, lang } = useLang();
  const [data, setData] = useState<ConnectOverview | null>(null);
  const [state, setState] = useState<State>("loading");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<MessageKey | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await getConnect());
      setState("ready");
    } catch (err) {
      setState(isApiFailure(err) && err.code === "no_path" ? "nopath" : "error");
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
    } catch (err) {
      setError(errorKey(err));
    } finally {
      await load();
      setBusy(null);
    }
  };

  const ready = data && data.eligible ? data : null;

  return (
    // From 1280 px up the page is exactly one screen tall (the shell adds 76 px of header and 56 px of bottom padding); only the people column and the card panel scroll.
    <div className="flex flex-col gap-8 pt-2 xl:-mb-10 xl:h-[calc(100dvh-92px)] xl:gap-4">
      <PageBanner title={t("connect.title")} lead={t("connect.lead")} />

      {state === "loading" && (
        <p className="flex items-center gap-3 text-lg text-muted" role="status">
          <Loader2 className="size-5 animate-spin text-accent" aria-hidden="true" />
          {t("req.loading")}
        </p>
      )}
      {state === "error" && <Notice>{t("err.network")}</Notice>}
      {state === "nopath" && (
        <section className="flex max-w-2xl flex-col items-start gap-4 rounded-[28px] border border-line bg-surface p-7 shadow-(--shadow-soft)">
          <Handshake className="size-8 text-accent" aria-hidden="true" />
          <h2 className="text-2xl font-bold tracking-tight">{t("connect.nopath.title")}</h2>
          <p className="text-lg text-muted">{t("connect.nopath.help")}</p>
          <Button full={false} onClick={() => navigate("/paths")}>
            {t("opp.locked.cta")}
          </Button>
        </section>
      )}

      {data && !data.eligible && state === "ready" && (
        <section className="flex max-w-2xl flex-col items-start gap-4 rounded-2xl bg-warn-bg p-7 text-warn">
          <Lock className="size-8" aria-hidden="true" />
          <h2 className="text-2xl font-bold tracking-tight">{t("connect.locked.title", { age: data.opens_at })}</h2>
          <p className="text-lg">{t("connect.locked.help")}</p>
          <Button full={false} className="bg-warn hover:bg-warn" onClick={() => navigate("/calls")}>
            {t("connect.locked.cta")}
          </Button>
        </section>
      )}

      {ready && state === "ready" && (
        <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_360px] xl:min-h-0 xl:flex-1 xl:grid-rows-1 xl:items-stretch">
          <div className="flex min-w-0 flex-col gap-10 xl:min-h-0 xl:overflow-y-auto xl:pr-1">
            {error && <Notice>{t(error)}</Notice>}

            {ready.incoming.length > 0 && (
              <section className="flex flex-col gap-4" aria-labelledby="connect-in">
                <h2 id="connect-in" className="text-2xl font-bold tracking-tight">
                  {t("connect.in.title")}
                </h2>
                <ul className={CARD_GRID}>
                  {ready.incoming.map((r) => (
                    <li key={r.id} className="flex flex-col gap-4 rounded-[28px] border border-accent/40 bg-tint p-5">
                      <Person card={r.card} />
                      <div className="mt-auto flex flex-col gap-2.5">
                        <Button className="h-12 text-base" loading={busy === `a-${r.id}`} disabled={!ready.me.visible} onClick={() => void act(`a-${r.id}`, () => answerConnect(r.id, "accept"))}>
                          {t("connect.accept")}
                        </Button>
                        <Button variant="secondary" className="h-12 text-base" loading={busy === `d-${r.id}`} onClick={() => void act(`d-${r.id}`, () => answerConnect(r.id, "decline"))}>
                          {t("connect.decline")}
                        </Button>
                        {!ready.me.visible && <p className="text-sm text-muted">{t("connect.needcard")}</p>}
                        <SafetyMenu cardId={r.card.card_id} onDone={() => void load()} />
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            <section className="flex flex-col gap-4" aria-labelledby="connect-conns">
              <h2 id="connect-conns" className="text-2xl font-bold tracking-tight">
                {t("connect.conns.title")}
              </h2>
              {ready.connections.length === 0 ? (
                <p className="text-lg text-muted">{t("connect.conns.empty")}</p>
              ) : (
                <ul className="grid gap-5 xl:grid-cols-2">
                  {ready.connections.map((c) => (
                    <li key={c.id} className="flex flex-col gap-4 rounded-[28px] border border-line bg-surface p-5 shadow-(--shadow-soft)">
                      <Person card={c.card} />
                      <Reach conn={c} />
                      <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
                        <button type="button" className="text-sm font-semibold text-muted underline-offset-2 hover:text-deep hover:underline" disabled={busy === `r-${c.id}`} onClick={() => void act(`r-${c.id}`, () => removeConnection(c.id))}>
                          {t("connect.remove")}
                        </button>
                        <SafetyMenu cardId={c.card.card_id} onDone={() => void load()} />
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="flex flex-col gap-4" aria-labelledby="connect-sug">
              <div className="flex flex-col gap-1">
                <h2 id="connect-sug" className="text-2xl font-bold tracking-tight">
                  {t("connect.suggest.title")}
                </h2>
                <p className="text-base text-muted">{t("connect.suggest.help")}</p>
                <p className="text-sm font-semibold text-deep">{t("connect.left", { n: ready.requests_left })}</p>
              </div>
              {!ready.me.visible ? (
                <Notice>{t("connect.needcard")}</Notice>
              ) : ready.suggestions.length === 0 ? (
                <section className="flex max-w-2xl gap-4 rounded-[28px] border border-line bg-surface p-6 shadow-(--shadow-soft)">
                  <Handshake className="mt-0.5 size-7 shrink-0 text-accent" aria-hidden="true" />
                  <div className="flex flex-col gap-1">
                    <h3 className="text-xl font-bold">{t("connect.suggest.empty.title")}</h3>
                    <p className="text-base text-muted">{t("connect.suggest.empty.help")}</p>
                  </div>
                </section>
              ) : (
                <ul className={CARD_GRID}>
                  {ready.suggestions.map((c) => (
                    <SuggestionCard key={c.card_id} card={c} canAsk={ready.requests_left > 0} busy={busy === `q-${c.card_id}`} onAsk={() => void act(`q-${c.card_id}`, () => requestConnect(c.card_id))} onSafety={() => void load()} />
                  ))}
                </ul>
              )}
            </section>

            {ready.outgoing.length > 0 && (
              <section className="flex flex-col gap-3" aria-labelledby="connect-out">
                <h2 id="connect-out" className="text-xl font-bold tracking-tight">
                  {t("connect.out.title")}
                </h2>
                <ul className="grid gap-3 md:grid-cols-2">
                  {ready.outgoing.map((r) => (
                    <li key={r.id} className="flex items-center justify-between gap-3 rounded-xl border border-line bg-surface px-4 py-3">
                      <span className="flex min-w-0 flex-col">
                        <span className="truncate text-base font-semibold">{r.card.first_name}</span>
                        <span className="truncate text-sm text-muted">{r.card.career_name ? pickText(r.card.career_name, lang) : ""}</span>
                      </span>
                      <Button variant="secondary" full={false} className="h-10 shrink-0 px-4 text-sm" loading={busy === `c-${r.id}`} onClick={() => void act(`c-${r.id}`, () => answerConnect(r.id, "cancel"))}>
                        {t("connect.takeback")}
                      </Button>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>

          <aside className="flex min-w-0 flex-col gap-6 xl:min-h-0">
            <MyCardPanel data={ready} onSaved={(d) => setData(d)} />
          </aside>
        </div>
      )}
    </div>
  );
}
