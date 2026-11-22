import { useEffect, useSyncExternalStore } from "react";
import { getUnreadCount } from "./api";

// How many messages in the inbox are unread. One shared number, so the bell and the inbox page always agree.
let count = 0;
const listeners = new Set<() => void>();

export function setUnread(n: number): void {
  if (n === count) return;
  count = n;
  listeners.forEach((l) => l());
}

export async function refreshUnread(): Promise<void> {
  try {
    setUnread((await getUnreadCount()).unread);
  } catch {
    /* offline or signed out: keep the last number */
  }
}

const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => listeners.delete(l);
};

const POLL_MS = 60_000;

/** The unread count for the bell. It refreshes when `key` changes (a new page), every minute, and when the tab is shown again. */
export function useUnread(key: string): number {
  useEffect(() => {
    void refreshUnread();
  }, [key]);
  useEffect(() => {
    const id = window.setInterval(() => void refreshUnread(), POLL_MS);
    const onVisible = () => document.visibilityState === "visible" && void refreshUnread();
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, []);
  return useSyncExternalStore(subscribe, () => count, () => 0);
}
