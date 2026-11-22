import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { PageBanner } from "../components/PageBanner";
import { ArrowLeft, BadgeCheck, Camera, CheckCircle2, CircleDashed, FileCheck2, Hourglass, Loader2, TriangleAlert, UserCheck, X, XCircle } from "lucide-react";
import { Button, Notice, Pill, TextField, cx } from "../components/ui";
import {
  addCredential,
  deleteProofPhoto,
  fetchProofPhoto,
  getTestArea,
  getTestAreas,
  startProofReview,
  submitTest,
  uploadProofPhoto,
  type Credential,
  type CredentialKind,
  type EvidenceStatus,
  type ProofPhoto,
  type TestArea,
  type TestAreaSummary,
  type TestResult,
} from "../lib/api";
import { errorKey } from "../lib/errors";
import { shrinkImage } from "../lib/image";
import { useLang, type MessageKey } from "../lib/i18n";
import { useSession } from "../lib/session";

const KINDS: CredentialKind[] = ["certificate", "work_sample", "experience", "reference"];
const SCORES = [1, 2, 3, 4] as const;

function StepTile({ icon: Icon, label, state, tone }: { icon: typeof BadgeCheck; label: string; state: string; tone: "ok" | "warn" | "idle" }) {
  const tones = { ok: "bg-ok-bg text-ok", warn: "bg-warn-bg text-warn", idle: "bg-bg text-muted" };
  return (
    <li className="flex items-center gap-4 rounded-[28px] border border-line bg-surface p-5 shadow-(--shadow-soft)">
      <span className={cx("grid size-12 shrink-0 place-items-center rounded-xl", tones[tone])} aria-hidden="true">
        <Icon className="size-6" />
      </span>
      <div className="flex min-w-0 flex-col gap-0.5">
        <p className="text-lg font-semibold">{label}</p>
        <p className={cx("text-[15px] font-semibold", tone === "ok" ? "text-ok" : tone === "warn" ? "text-warn" : "text-muted")}>{state}</p>
      </div>
    </li>
  );
}

function Card({ id, title, help, children }: { id: string; title: string; help: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-5 rounded-[28px] border border-line bg-surface p-6 shadow-(--shadow-soft) md:p-7" aria-labelledby={id}>
      <div className="flex flex-col gap-1.5">
        <h2 id={id} className="text-2xl font-bold tracking-tight">
          {title}
        </h2>
        <p className="text-base text-muted">{help}</p>
      </div>
      {children}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Proof (evidence)
// ---------------------------------------------------------------------------

/** A small preview of an uploaded photo, with what the check found and a button to remove it. */
function PhotoThumb({ credentialId, photo, locked, onRemove }: { credentialId: string; photo: ProofPhoto; locked: boolean; onRemove: () => void }) {
  const { t } = useLang();
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    let url: string | null = null;
    let alive = true;
    fetchProofPhoto(credentialId, photo.id)
      .then((blob) => {
        if (!alive) return;
        url = URL.createObjectURL(blob);
        setSrc(url);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [credentialId, photo.id]);

  return (
    <li className="flex w-[132px] flex-col gap-1.5">
      <div
        className={cx(
          "relative aspect-[4/3] overflow-hidden rounded-xl bg-bg ring-2",
          photo.good === true && "ring-ok",
          photo.good === false && "ring-bad",
          photo.good === null && "ring-line",
        )}
      >
        {src ? <img src={src} alt="" className="size-full object-cover" /> : <Loader2 className="absolute inset-0 m-auto size-5 animate-spin text-muted" aria-hidden="true" />}
        {!locked && (
          <button
            type="button"
            onClick={onRemove}
            aria-label={t("assess.photo.remove")}
            title={t("assess.photo.remove")}
            className="absolute top-1 right-1 grid size-8 place-items-center rounded-full bg-ink/70 text-white hover:bg-ink"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        )}
      </div>
      {photo.good === true && (
        <p className="flex items-center gap-1 text-sm font-semibold text-ok">
          <CheckCircle2 className="size-4 shrink-0" aria-hidden="true" />
          {t("assess.photo.good")}
        </p>
      )}
      {photo.good === false && (
        <p className="flex items-center gap-1 text-sm font-semibold text-bad">
          <TriangleAlert className="size-4 shrink-0" aria-hidden="true" />
          {t("assess.photo.fix")}
        </p>
      )}
    </li>
  );
}

/** The add-a-photo tile and the photos of one proof. `locked` proofs (approved) show their photos and nothing can be changed. */
function PhotoRow({ c, locked, busy, onPick, onRemove }: { c: Credential; locked: boolean; busy: string | null; onPick: (files: FileList | null) => void; onRemove: (photoId: string) => void }) {
  const { t } = useLang();
  return (
    <ul className="flex flex-wrap items-start gap-3">
      {c.photos.map((p) => (
        <PhotoThumb key={p.id} credentialId={c.id} photo={p} locked={locked} onRemove={() => onRemove(p.id)} />
      ))}
      {c.photos.length < 3 && !locked && (
        <li>
          <label
            className={cx(
              "flex h-[99px] w-[132px] cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border-[1.5px] border-dashed border-line-strong bg-surface text-center text-sm font-semibold text-accent hover:border-accent",
              busy === `photo-${c.id}` && "pointer-events-none opacity-60",
            )}
          >
            {busy === `photo-${c.id}` ? <Loader2 className="size-6 animate-spin" aria-hidden="true" /> : <Camera className="size-6" aria-hidden="true" />}
            {busy === `photo-${c.id}` ? t("assess.photo.uploading") : t("assess.photo.add")}
            <input
              type="file"
              accept="image/jpeg,image/png"
              capture="environment"
              className="sr-only"
              onChange={(e) => {
                onPick(e.target.files);
                e.target.value = "";
              }}
            />
          </label>
        </li>
      )}
    </ul>
  );
}

/** An approved proof, filed under the skill it proves. It cannot be changed, so the saved record stays as it was approved. */
function SavedProof({ c, onStartTest }: { c: Credential; onStartTest: (areaId: string) => void }) {
  const { t, lang } = useLang();
  return (
    <li className="flex flex-col gap-3 rounded-xl border border-line bg-surface p-4">
      <div className="flex items-start gap-3">
        <FileCheck2 className="mt-0.5 size-5 shrink-0 text-ok" aria-hidden="true" />
        <div className="flex min-w-0 flex-col">
          <p className="text-base font-semibold">{c.title}</p>
          <p className="text-sm text-muted">
            {t(`assess.kind.${c.kind}` as MessageKey)}
            {c.note ? `. ${c.note}` : ""}
          </p>
        </div>
      </div>
      <ul className="flex flex-wrap items-center gap-2" aria-label={t("assess.saved.skills")}>
        {c.areas.length === 0 && <li className="rounded-full bg-ok-bg px-3 py-1 text-sm font-semibold text-ok">{t("assess.saved.approved")}</li>}
        {c.areas.map((a) => (
          <li key={a.id} className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-tint px-3 py-1 text-sm font-semibold text-deep">{a.name[lang]}</span>
            {a.test_passed ? (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-ok-bg px-3 py-1 text-sm font-semibold text-ok">
                <CheckCircle2 className="size-4" aria-hidden="true" />
                {t("assess.saved.skillVerified")}
              </span>
            ) : (
              <Button variant="secondary" full={false} className="h-9 px-3.5 text-sm" onClick={() => onStartTest(a.id)}>
                {t("assess.saved.takeTest", { skill: a.name[lang] })}
              </Button>
            )}
          </li>
        ))}
      </ul>
      {c.photos.length > 0 && (
        <ul className="flex flex-wrap items-start gap-3">
          {c.photos.map((p) => (
            <PhotoThumb key={p.id} credentialId={c.id} photo={p} locked onRemove={() => undefined} />
          ))}
        </ul>
      )}
    </li>
  );
}

function ProofCard({ onChanged, onStartTest }: { onChanged: () => Promise<void>; onStartTest: (areaId: string) => void }) {
  const { t } = useLang();
  const { profile } = useSession();
  const [kind, setKind] = useState<CredentialKind>("certificate");
  const [title, setTitle] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<MessageKey | null>(null);
  const status: EvidenceStatus = profile?.kind === "teacher" ? profile.data.evidence.status : "none";
  const reviewing = profile?.kind === "teacher" && (profile.data.evidence.reviewing || status === "reviewing");

  // While the photos are being checked, look again every few seconds until the answer is in.
  useEffect(() => {
    if (!reviewing) return;
    const timer = setInterval(() => void onChanged(), 2500);
    return () => clearInterval(timer);
  }, [reviewing, onChanged]);

  if (profile?.kind !== "teacher") return null;
  const { evidence, credentials } = profile.data;
  const open = credentials.filter((c) => c.state === "new");
  const saved = credentials.filter((c) => c.state === "approved");
  const openPhotos = open.reduce((n, c) => n + c.photos.length, 0);
  const hasReasons = evidence.reasons.length > 0;

  const run = async (key: string, fn: () => Promise<unknown>) => {
    setBusy(key);
    setError(null);
    try {
      await fn();
      await onChanged();
    } catch (err) {
      setError(errorKey(err));
    } finally {
      setBusy(null);
    }
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (title.trim().length < 2) return setError("assess.cred.val");
    await run("add", async () => {
      await addCredential({ kind, title: title.trim(), note: note.trim() });
      setTitle("");
      setNote("");
    });
  };

  const pick = (credentialId: string, files: FileList | null) => {
    const file = files?.[0];
    if (!file) return;
    void run(`photo-${credentialId}`, async () => uploadProofPhoto(credentialId, await shrinkImage(file)));
  };

  return (
    <Card id="proof" title={t("assess.proof.title")} help={t("assess.proof.help")}>
      {reviewing && (
        <p className="flex items-center gap-3 rounded-xl bg-tint px-4 py-3 text-base font-medium text-deep" role="status">
          <Loader2 className="size-5 shrink-0 animate-spin" aria-hidden="true" />
          {t("assess.evidence.reviewingLong")}
        </p>
      )}
      {!reviewing && open.length > 0 && !hasReasons && <Notice tone="info">{t("assess.evidence.pendingLong")}</Notice>}
      {!reviewing && hasReasons && (
        <div className="flex flex-col gap-2 rounded-xl bg-bad-bg p-4 text-bad" role="alert">
          <p className="font-semibold">
            {evidence.reasons.includes("review_unavailable") ? t("assess.evidence.unavailableLong") : saved.length > 0 ? t("assess.evidence.partialLong") : t("assess.evidence.rejectedLong")}
          </p>
          <ul className="list-disc pl-5 text-[15px]">
            {evidence.reasons.map((r) => (
              <li key={r}>{t(`assess.reason.${r}` as MessageKey)}</li>
            ))}
          </ul>
        </div>
      )}
      {!reviewing && open.length === 0 && saved.length > 0 && <Notice tone="info">{t("assess.proof.another")}</Notice>}

      {open.length > 0 && (
        <ul className="flex flex-col gap-3">
          {open.map((c) => (
            <li key={c.id} className="flex flex-col gap-3 rounded-xl bg-bg p-4">
              <div className="flex items-start gap-3">
                <FileCheck2 className="mt-0.5 size-5 shrink-0 text-accent" aria-hidden="true" />
                <div className="flex min-w-0 flex-col">
                  <p className="text-base font-semibold">{c.title}</p>
                  <p className="text-sm text-muted">
                    {t(`assess.kind.${c.kind}` as MessageKey)}
                    {c.note ? `. ${c.note}` : ""}
                  </p>
                </div>
              </div>
              <PhotoRow c={c} locked={reviewing} busy={busy} onPick={(files) => pick(c.id, files)} onRemove={(pid) => void run(`rm-${pid}`, () => deleteProofPhoto(c.id, pid))} />
              {c.photos.some((p) => p.good === false) && (
                <ul className="list-disc pl-5 text-[15px] text-bad">
                  {[...new Set(c.photos.flatMap((p) => (p.good === false ? p.reasons : [])))].map((r) => (
                    <li key={r}>{t(`assess.reason.${r}` as MessageKey)}</li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}

      {open.length > 0 && (
        <div className="flex flex-col gap-2">
          <Button full={false} className="h-12 self-start text-base" loading={busy === "review" || Boolean(reviewing)} disabled={openPhotos === 0 || busy !== null} onClick={() => void run("review", startProofReview)}>
            {t("assess.proof.submit")}
          </Button>
          {openPhotos === 0 && <p className="text-sm text-muted">{t("assess.proof.noPhoto")}</p>}
        </div>
      )}

      {!reviewing && (
        <form onSubmit={submit} className={cx("flex flex-col gap-4 pt-5", (open.length > 0 || credentials.length > 0) && "border-t border-line")} noValidate>
          <div role="radiogroup" aria-label={t("assess.cred.kind")} className="flex flex-wrap gap-2.5">
            {KINDS.map((k) => (
              <Pill key={k} selected={kind === k} onSelect={() => setKind(k)}>
                {t(`assess.kind.${k}` as MessageKey)}
              </Pill>
            ))}
          </div>
          <TextField label={t("assess.cred.title")} value={title} onChange={(e) => { setTitle(e.target.value); setError(null); }} maxLength={100} />
          <label className="flex flex-col gap-2">
            <span className="text-base font-semibold text-ink">{t("assess.cred.note")}</span>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              maxLength={500}
              rows={2}
              className="w-full resize-y rounded-xl border-[1.5px] border-line-strong bg-surface px-4 py-3 text-lg text-ink outline-none focus:border-accent focus:ring-4 focus:ring-tint-strong"
            />
          </label>
          <p className="text-sm text-muted">{t("assess.cred.privacy")}</p>
          <Button type="submit" variant="secondary" full={false} loading={busy === "add"} disabled={busy !== null} className="h-12 self-start text-base">
            {t("assess.cred.add")}
          </Button>
        </form>
      )}
      {error && <Notice>{t(error)}</Notice>}

      {saved.length > 0 && (
        <section className="flex flex-col gap-3 border-t border-line pt-5" aria-labelledby="saved-proofs">
          <div className="flex flex-col gap-1">
            <h3 id="saved-proofs" className="text-xl font-bold">
              {t("assess.saved.title")}
            </h3>
            <p className="text-sm text-muted">{t("assess.saved.help")}</p>
          </div>
          <ul className="flex flex-col gap-3">
            {saved.map((c) => (
              <SavedProof key={c.id} c={c} onStartTest={onStartTest} />
            ))}
          </ul>
        </section>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Test
// ---------------------------------------------------------------------------

function TestRunner({ areaId, onClose, onChanged }: { areaId: string; onClose: () => void; onChanged: () => Promise<void> }) {
  const { t, lang } = useLang();
  const [area, setArea] = useState<TestArea | null>(null);
  const [scores, setScores] = useState<Record<string, number>>({});
  const [result, setResult] = useState<TestResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<MessageKey | null>(null);

  useEffect(() => {
    let alive = true;
    getTestArea(areaId)
      .then((a) => alive && setArea(a))
      .catch((err: unknown) => alive && setError(errorKey(err)));
    return () => {
      alive = false;
    };
  }, [areaId]);

  const back = (
    <Button variant="ghost" full={false} className="h-11 self-start px-3 text-base" icon={<ArrowLeft className="size-5" />} onClick={onClose}>
      {t("assess.test.back")}
    </Button>
  );

  if (!area) {
    return (
      <div className="flex flex-col gap-5">
        {back}
        {error ? <Notice>{t(error)}</Notice> : <Loader2 className="size-6 animate-spin text-accent" aria-label={t("req.loading")} />}
      </div>
    );
  }

  const answered = Object.keys(scores).length;
  const submit = async () => {
    if (answered < area.items.length) return setError("assess.test.unanswered");
    setBusy(true);
    setError(null);
    try {
      const r = await submitTest(area.id, scores);
      setResult(r);
      await onChanged();
    } catch (err) {
      setError(errorKey(err));
    } finally {
      setBusy(false);
    }
  };

  if (result) {
    return (
      <div className="flex flex-col gap-5">
        {back}
        <section className={cx("flex max-w-3xl gap-5 rounded-2xl p-7", result.passed ? "bg-ok-bg text-ok" : "bg-warn-bg text-warn")} role="status">
          {result.passed ? <CheckCircle2 className="mt-1 size-8 shrink-0" aria-hidden="true" /> : <XCircle className="mt-1 size-8 shrink-0" aria-hidden="true" />}
          <div className="flex flex-col gap-2">
            <h2 className="text-2xl font-bold">{result.passed ? t("assess.result.pass") : t("assess.result.fail")}</h2>
            <p className="text-lg">{t("assess.result.close", { close: result.close, of: result.of, needed: result.needed })}</p>
            {result.passed && <p className="text-lg">{result.tier >= 1 ? t("assess.result.tier") : t("assess.result.awaiting")}</p>}
            {!result.passed && <p className="text-lg">{result.attempts_left > 0 ? t("assess.result.again", { n: result.attempts_left }) : t("assess.result.none")}</p>}
          </div>
        </section>
        {!result.passed && result.attempts_left > 0 && (
          <Button full={false} className="h-12 self-start text-base" onClick={() => { setResult(null); setScores({}); }}>
            {t("assess.result.retry")}
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {back}
      <div className="flex flex-col gap-2">
        <h2 className="text-[28px] leading-tight font-bold tracking-tight">{area.name[lang]}</h2>
        <p className="max-w-3xl text-lg text-muted">{t("assess.test.help", { needed: area.pass_rule.needed, of: area.pass_rule.of })}</p>
      </div>
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <ol className="grid gap-5 xl:grid-cols-2">
          {area.items.map((item, i) => (
            <li key={item.id} className="flex flex-col gap-4 rounded-[28px] border border-line bg-surface p-6 shadow-(--shadow-soft)">
              <p className="text-sm font-semibold tracking-wide text-deep uppercase">{t("assess.test.item", { n: i + 1, total: area.items.length })}</p>
              <p className="text-lg">{item.work}</p>
              <div role="radiogroup" aria-label={t("assess.test.item", { n: i + 1, total: area.items.length })} className="mt-auto grid grid-cols-4 gap-2">
                {SCORES.map((s) => (
                  <button
                    key={s}
                    type="button"
                    role="radio"
                    aria-checked={scores[item.id] === s}
                    onClick={() => { setScores((prev) => ({ ...prev, [item.id]: s })); setError(null); }}
                    className={cx(
                      "min-h-12 rounded-xl border-[1.5px] text-xl font-bold transition-colors",
                      scores[item.id] === s ? "border-accent bg-accent text-white" : "border-line-strong bg-surface text-ink hover:border-accent",
                    )}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </li>
          ))}
        </ol>

        <aside className="flex flex-col gap-4 rounded-[28px] border border-line bg-surface p-6 shadow-(--shadow-soft) lg:sticky lg:top-4">
          <h3 className="text-lg font-bold">{t("assess.test.scale")}</h3>
          <dl className="flex flex-col gap-2.5">
            {SCORES.map((s) => (
              <div key={s} className="flex items-start gap-3">
                <dt className="grid size-8 shrink-0 place-items-center rounded-lg bg-tint font-bold text-deep">{s}</dt>
                <dd className="text-[15px] text-muted">{area.scale[String(s) as "1" | "2" | "3" | "4"]}</dd>
              </div>
            ))}
          </dl>
          <div className="h-1.5 overflow-hidden rounded-full bg-line" role="progressbar" aria-valuemin={0} aria-valuemax={area.items.length} aria-valuenow={answered} aria-label={t("assess.test.progress", { n: answered, total: area.items.length })}>
            <div className="h-full rounded-full bg-accent transition-[width]" style={{ width: `${(answered / area.items.length) * 100}%` }} />
          </div>
          <p className="text-sm font-medium text-muted">{t("assess.test.progress", { n: answered, total: area.items.length })}</p>
          <p className="text-sm text-muted">{t("assess.test.tries", { n: area.attempts_left })}</p>
          {error && <Notice>{t(error)}</Notice>}
          <Button loading={busy} className="h-12 text-base" onClick={() => void submit()}>
            {t("assess.test.submit")}
          </Button>
        </aside>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function TeacherAssessPage() {
  const { t, lang } = useLang();
  const { profile, reload } = useSession();
  const [areas, setAreas] = useState<TestAreaSummary[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setAreas((await getTestAreas()).areas);
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);
  const changed = useCallback(async () => {
    await Promise.all([load(), reload()]);
  }, [load, reload]);

  if (profile?.kind !== "teacher") return null;
  const me = profile.data;
  const evidence: EvidenceStatus = me.evidence.status;
  const passed = me.passed_areas.length;

  if (open) {
    return (
      <div className="pt-2">
        <TestRunner areaId={open} onClose={() => { setOpen(null); void load(); }} onChanged={changed} />
      </div>
    );
  }

  return (
    // From 1024 px up the page fits the window and only the two columns scroll. The shell adds 76 px of header and
    // 56 px of bottom padding, so the height and the negative margin below make the total exactly one screen.
    <div className="flex flex-col gap-8 pt-2 lg:-mb-10 lg:h-[calc(100dvh-92px)] lg:gap-5">
      <PageBanner title={t("assess.title")} lead={t("assess.lead")} />

      <ul className="grid gap-4 md:grid-cols-3">
        <StepTile icon={FileCheck2} label={t("assess.step.proof")} state={t(`assess.evidence.${evidence}` as MessageKey)} tone={evidence === "verified" ? "ok" : evidence === "pending" ? "warn" : "idle"} />
        <StepTile icon={BadgeCheck} label={t("assess.step.test")} state={passed ? t("assess.step.testDone", { n: passed }) : t("assess.step.testNone")} tone={passed ? "ok" : "idle"} />
        <StepTile icon={UserCheck} label={t("assess.step.matched")} state={me.tier >= 1 ? t("assess.step.matchedYes") : t("assess.step.matchedNo")} tone={me.tier >= 1 ? "ok" : "idle"} />
      </ul>

      <div className="grid items-start gap-6 lg:min-h-0 lg:flex-1 lg:grid-cols-2 lg:grid-rows-1 lg:items-stretch">
        <div className="lg:relative lg:-mx-1 lg:min-h-0 lg:overflow-y-auto lg:px-1 lg:pb-2">
          <ProofCard onChanged={changed} onStartTest={setOpen} />
        </div>
        <div className="lg:relative lg:-mx-1 lg:min-h-0 lg:overflow-y-auto lg:px-1 lg:pb-2">
        <Card id="test" title={t("assess.test.title")} help={t("assess.test.intro")}>
          {failed && <Notice>{t("err.network")}</Notice>}
          {!areas && !failed && <Loader2 className="size-6 animate-spin text-accent" aria-label={t("req.loading")} />}
          {areas && (
            <ul className="flex flex-col gap-3">
              {areas.map((a) => (
                <li key={a.id} className="flex flex-wrap items-center gap-3 rounded-xl border border-line px-4 py-3">
                  <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-tint text-accent" aria-hidden="true">
                    {a.passed ? <CheckCircle2 className="size-5 text-ok" /> : a.attempts_left > 0 ? <CircleDashed className="size-5" /> : <Hourglass className="size-5" />}
                  </span>
                  <div className="flex min-w-0 flex-1 flex-col">
                    <p className="text-lg font-semibold">{a.name[lang]}</p>
                    <p className={cx("text-sm font-medium", a.passed ? "text-ok" : "text-muted")}>
                      {a.passed ? t("assess.area.passed") : a.attempts_left > 0 ? t("assess.area.tries", { n: a.attempts_left }) : t("assess.area.none")}
                    </p>
                  </div>
                  {!a.passed && a.attempts_left > 0 && (
                    <Button variant="secondary" full={false} className="h-11 px-5 text-base" onClick={() => setOpen(a.id)}>
                      {t("assess.area.start")}
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>
        </div>
      </div>
    </div>
  );
}
