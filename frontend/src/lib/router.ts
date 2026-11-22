import { useSyncExternalStore } from "react";

/**
 * A tiny history-API router. The app has a few dozen flat routes and no nested data
 * loading, so a library would only add weight against the 200 KB script budget.
 */
const NAV_EVENT = "khoj:navigate";

export function currentPath(): string {
  return typeof window === "undefined" ? "/" : window.location.pathname;
}

export function navigate(path: string, opts: { replace?: boolean } = {}): void {
  if (path === currentPath()) return;
  if (opts.replace) window.history.replaceState(null, "", path);
  else window.history.pushState(null, "", path);
  window.dispatchEvent(new Event(NAV_EVENT));
  window.scrollTo({ top: 0 });
}

function subscribe(listener: () => void): () => void {
  window.addEventListener("popstate", listener);
  window.addEventListener(NAV_EVENT, listener);
  return () => {
    window.removeEventListener("popstate", listener);
    window.removeEventListener(NAV_EVENT, listener);
  };
}

export function usePath(): string {
  return useSyncExternalStore(subscribe, currentPath, () => "/");
}
