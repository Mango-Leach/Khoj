import { useCallback, useEffect, useState } from "react";
import { PageBanner } from "../components/PageBanner";
import { Check, Hourglass, Loader2, Lock, X } from "lucide-react";
import { LearnerCardView } from "../components/LearnerCard";
import { Button, Notice } from "../components/ui";
import { answerRequest, getTeacherRequests, type IncomingRequest } from "../lib/api";
import { errorKey } from "../lib/errors";
import { useLang, type MessageKey } from "../lib/i18n";
import { navigate } from "../lib/router";
import { useSession } from "../lib/session";

type Data = { capacity: { limit: number; free: number }; pending: IncomingRequest[]; recent: IncomingRequest[] };

function hoursLeft(iso: string): number {
  return Math.max(1, Math.ceil((new Date(iso).getTime() - Date.now()) / 3_600_000));
}

export function TeacherRequestsPage() {
  const { t } = useLang();
  const { profile, reload } = useSession();
  const [data, setData] = useState<Data | null>(null);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<MessageKey | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await getTeacherRequests());
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const answer = async (id: string, accept: boolean) => {
    setBusy(id);
    setError(null);
    try {
      await answerRequest(id, accept);
      await Promise.all([load(), reload()]);
    } catch (err) {
      setError(errorKey(err));
      await load();
    } finally {
      setBusy(null);
    }
  };

  const unverified = profile?.kind === "teacher" && profile.data.tier < 1;

  return (
    <div className="flex flex-col gap-8 pt-2">
      <PageBanner title={t("req.title")} lead={t("req.lead")} />

      {unverified && (
        <section className="flex flex-col gap-4 rounded-2xl bg-warn-bg p-6 text-warn sm:flex-row sm:items-center">
          <Lock className="size-7 shrink-0" aria-hidden="true" />
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <h2 className="text-xl font-bold">{t("req.locked.title")}</h2>
            <p className="text-lg">{t("req.locked.help")}</p>
          </div>
          <Button full={false} className="h-12 bg-warn text-base hover:bg-warn" onClick={() => navigate("/t/assess")}>
            {t("req.locked.cta")}
          </Button>
        </section>
      )}

      {error && <Notice>{t(error)}</Notice>}
      {failed && <Notice>{t("err.network")}</Notice>}
      {!data && !failed && (
        <div className="flex items-center gap-3 text-lg text-muted" role="status">
          <Loader2 className="size-6 animate-spin text-accent" aria-hidden="true" />
          {t("req.loading")}
        </div>
      )}

      {data && (
        <>
          <p className="text-lg font-semibold text-deep">{t("req.places", { free: data.capacity.free, limit: data.capacity.limit })}</p>

          {data.pending.length === 0 ? (
            <section className="flex max-w-3xl gap-4 rounded-[28px] border border-line bg-surface p-7 shadow-(--shadow-soft)">
              <Hourglass className="mt-1 size-7 shrink-0 text-accent" aria-hidden="true" />
              <p className="text-lg text-muted">{t("req.empty")}</p>
            </section>
          ) : (
            <ul className="grid gap-5 md:grid-cols-2 2xl:grid-cols-3">
              {data.pending.map((r) => (
                <li key={r.id} className="flex flex-col gap-5 rounded-[28px] border border-line bg-surface p-6 shadow-(--shadow-soft)">
                  <LearnerCardView card={r.student} />
                  <p className="inline-flex items-center gap-2 text-[15px] font-semibold text-warn">
                    <Hourglass className="size-4" aria-hidden="true" />
                    {t("req.left", { n: hoursLeft(r.expires_at) })}
                  </p>
                  <div className="mt-auto grid grid-cols-2 gap-3">
                    <Button className="h-12 text-base" icon={<Check className="size-5" />} loading={busy === r.id} disabled={busy !== null} onClick={() => void answer(r.id, true)}>
                      {t("req.accept")}
                    </Button>
                    <Button variant="secondary" className="h-12 text-base" icon={<X className="size-5" />} disabled={busy !== null} onClick={() => void answer(r.id, false)}>
                      {t("req.decline")}
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}

          {data.recent.length > 0 && (
            <section className="flex flex-col gap-3" aria-labelledby="recent">
              <h2 id="recent" className="text-2xl font-bold tracking-tight">
                {t("req.recent")}
              </h2>
              <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {data.recent.map((r) => (
                  <li key={r.id} className="flex items-center justify-between gap-3 rounded-xl border border-line bg-surface px-4 py-3">
                    <span className="min-w-0 truncate text-lg font-semibold">{r.student.name}</span>
                    <span className="shrink-0 rounded-full bg-bg px-3 py-1 text-sm font-semibold text-muted">{t(`req.status.${r.status}` as MessageKey)}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  );
}
