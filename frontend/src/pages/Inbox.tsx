import { useEffect, useState } from "react";
import { PageBanner } from "../components/PageBanner";
import { Bell, CheckCheck, ChevronRight, Loader2 } from "lucide-react";
import { Button, Notice, cx } from "../components/ui";
import { getNotifications, markAllNotificationsRead, markNotificationRead, type AppNotification } from "../lib/api";
import { errorKey } from "../lib/errors";
import { useLang, type MessageKey } from "../lib/i18n";
import { navigate } from "../lib/router";
import { waited } from "../lib/text";
import { setUnread } from "../lib/unread";

function sentence(n: AppNotification): MessageKey {
  if (n.kind === "review_ready") return n.params.result === "approved" ? "inbox.kind.review_ready.approved" : "inbox.kind.review_ready.returned";
  return `inbox.kind.${n.kind}` as MessageKey;
}

/** The inbox, the same page for a learner and a mentor. Every message has one short neutral sentence and a link. */
export function InboxPage() {
  const { t } = useLang();
  const [items, setItems] = useState<AppNotification[] | null>(null);
  const [error, setError] = useState<MessageKey | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    getNotifications()
      .then((r) => {
        if (!alive) return;
        setItems(r.items);
        setUnread(r.unread);
      })
      .catch((err) => alive && setError(errorKey(err)));
    return () => {
      alive = false;
    };
  }, []);

  const open = (n: AppNotification) => {
    if (!n.read) {
      setItems((list) => list?.map((x) => (x.id === n.id ? { ...x, read: true } : x)) ?? null);
      markNotificationRead(n.id)
        .then((r) => setUnread(r.unread))
        .catch(() => undefined);
    }
    navigate(n.link);
  };

  const readAll = async () => {
    setBusy(true);
    try {
      const r = await markAllNotificationsRead();
      setUnread(r.unread);
      setItems((list) => list?.map((x) => ({ ...x, read: true })) ?? null);
    } catch (err) {
      setError(errorKey(err));
    } finally {
      setBusy(false);
    }
  };

  const when = (iso: string) => {
    const { hours, days } = waited(iso);
    if (days >= 1) return t("inbox.when.days", { n: days });
    return hours >= 1 ? t("inbox.when.hours", { n: hours }) : t("inbox.when.now");
  };
  const unread = items?.filter((n) => !n.read).length ?? 0;

  return (
    <div className="flex flex-col gap-6 pt-2">
      <PageBanner
        title={t("inbox.title")}
        lead={t("inbox.lead")}
        aside={
          unread > 0 && (
            <Button variant="secondary" full={false} loading={busy} icon={<CheckCheck className="size-5" />} onClick={() => void readAll()} className="h-11 text-base">
              {t("inbox.markAll")}
            </Button>
          )
        }
      />

      {error && <Notice>{t(error)}</Notice>}
      {!items && !error && (
        <div className="flex items-center gap-3 text-lg text-muted" role="status">
          <Loader2 className="size-6 animate-spin text-accent" aria-hidden="true" />
          {t("req.loading")}
        </div>
      )}
      {items && items.length === 0 && (
        <section className="flex max-w-3xl gap-4 rounded-[28px] border border-line bg-surface p-7 shadow-(--shadow-soft)">
          <Bell className="mt-1 size-7 shrink-0 text-accent" aria-hidden="true" />
          <p className="text-lg text-muted">{t("inbox.empty")}</p>
        </section>
      )}
      {items && items.length > 0 && (
        <ul className="grid max-w-4xl gap-3">
          {items.map((n) => (
            <li key={n.id}>
              <button
                type="button"
                onClick={() => open(n)}
                className={cx(
                  "flex w-full items-center gap-4 rounded-2xl border px-5 py-4 text-left transition-colors hover:border-accent",
                  n.read ? "border-line bg-surface" : "border-accent/40 bg-tint",
                )}
              >
                <span className={cx("size-3 shrink-0 rounded-full", n.read ? "bg-transparent" : "bg-accent")} aria-hidden="true" />
                <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span className={cx("text-lg leading-snug", n.read ? "font-medium" : "font-bold")}>{t(sentence(n))}</span>
                  <span className="text-sm text-muted">
                    {!n.read && <span className="sr-only">{t("inbox.unread")} </span>}
                    {when(n.created_at)}
                  </span>
                </span>
                <ChevronRight className="size-5 shrink-0 text-muted" aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
