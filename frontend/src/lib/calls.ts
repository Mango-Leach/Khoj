import type { CallContactKind } from "./api";
import type { Lang } from "./i18n";

// Every call is in Indian time, whatever the phone's own setting says, so a mentor and a learner see the same hour.
const ZONE = "Asia/Kolkata";
const LOCALE: Record<Lang, string> = { en: "en-IN-u-nu-latn", hi: "hi-IN-u-nu-latn", mr: "mr-IN-u-nu-latn" };

export function dayLabel(iso: string, lang: Lang): string {
  return new Intl.DateTimeFormat(LOCALE[lang], { timeZone: ZONE, weekday: "long", day: "numeric", month: "long" }).format(new Date(iso));
}

export function timeLabel(iso: string, lang: Lang): string {
  return new Intl.DateTimeFormat(LOCALE[lang], { timeZone: ZONE, hour: "numeric", minute: "2-digit", hour12: true }).format(new Date(iso));
}

/** The calendar day in Indian time as YYYY-MM-DD, to group times by day. */
export function dayKey(iso: string): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: ZONE }).format(new Date(iso));
}

export function todayIst(now = Date.now()): string {
  return dayKey(new Date(now).toISOString());
}

/** A date and a time typed in Indian time, as the UTC moment the server stores. */
export function toIso(date: string, time: string): string {
  return new Date(`${date}T${time}:00+05:30`).toISOString();
}

export function contactHref(kind: CallContactKind, contact: string): string {
  return kind === "phone" ? `tel:+91${contact}` : contact;
}

/** A number as 98765 43210, to read aloud or dial. */
export function spacedPhone(contact: string): string {
  return contact.length === 10 ? `${contact.slice(0, 5)} ${contact.slice(5)}` : contact;
}
