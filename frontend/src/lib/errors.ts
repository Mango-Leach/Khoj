import { isApiFailure } from "./api";
import { hasKey, type MessageKey } from "./i18n";

/** Maps any thrown value to a translation key. Unknown server codes fall back to a generic message. */
export function errorKey(err: unknown): MessageKey {
  if (isApiFailure(err)) {
    if (err.code === "network") return "err.network";
    const key = `err.${err.code}`;
    if (hasKey(key)) return key;
  }
  return "err.generic";
}
