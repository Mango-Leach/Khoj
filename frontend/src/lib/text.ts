import type { Lang } from "./i18n";
import type { TextMap } from "./api";

/** Text in the wanted language, else English, else whatever was written. */
export function pickText(text: TextMap | undefined, lang: Lang): string {
  if (!text) return "";
  return text[lang] || text.en || Object.values(text).find(Boolean) || "";
}

/** True when the learner's language is not the one the text was written in, so a note can say so. */
export function notInLang(text: TextMap | undefined, lang: Lang): boolean {
  return Boolean(text) && !text?.[lang];
}

export function waited(iso: string, now = Date.now()): { hours: number; days: number } {
  const hours = Math.max(0, Math.floor((now - new Date(iso).getTime()) / 3_600_000));
  return { hours, days: Math.floor(hours / 24) };
}
