import { useSyncExternalStore } from "react";
import { WifiOff } from "lucide-react";
import { useLang } from "../lib/i18n";
import { cx } from "./ui";

function subscribe(cb: () => void): () => void {
  window.addEventListener("online", cb);
  window.addEventListener("offline", cb);
  return () => {
    window.removeEventListener("online", cb);
    window.removeEventListener("offline", cb);
  };
}

/** Says nothing while the connection is fine. It appears only when the phone is offline, because that is when the
 *  learner needs to know that actions will wait and sync later. */
export function ConnectionBadge() {
  const { t } = useLang();
  const online = useSyncExternalStore(subscribe, () => navigator.onLine, () => true);
  if (online) return null;
  return (
    <span role="status" className={cx("inline-flex h-10 items-center gap-2 rounded-xl bg-bad-bg px-2.5 text-[15px] font-semibold text-bad sm:px-3.5")}>
      <WifiOff className="size-4" aria-hidden="true" />
      <span className="sr-only sm:not-sr-only">{t("connection.offline")}</span>
    </span>
  );
}
