import { useSyncExternalStore } from "react";
import en from "../i18n/en.json";
import hi from "../i18n/hi.json";
import mr from "../i18n/mr.json";

export type Lang = "en" | "hi" | "mr";
export type MessageKey = keyof typeof en;
export type Vars = Record<string, string | number>;

// Each language is named in its own script so a learner can find theirs without reading English.
export const LANGS: { code: Lang; label: string }[] = [
  { code: "en", label: "English" },
  { code: "hi", label: "हिन्दी" },
  { code: "mr", label: "मराठी" },
];

const dictionaries: Record<Lang, Record<string, string>> = { en, hi, mr };
const STORAGE_KEY = "khoj.lang";

/** Replaces {name} style placeholders. A missing variable is left visible rather than hidden. */
export function interpolate(text: string, vars?: Vars): string {
  if (!vars) return text;
  return text.replace(/\{(\w+)\}/g, (whole, name: string) => (name in vars ? String(vars[name]) : whole));
}

export function translate(lang: Lang, key: MessageKey, vars?: Vars): string {
  return interpolate(dictionaries[lang][key] ?? dictionaries.en[key] ?? key, vars);
}

/** True when the key exists in the English dictionary (used to map server error codes). */
export function hasKey(key: string): key is MessageKey {
  return key in en;
}

export function isLang(value: unknown): value is Lang {
  return value === "en" || value === "hi" || value === "mr";
}

// Storage can throw (private windows, blocked site data), so it is only a convenience.
function readStored(): Lang {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (isLang(stored)) return stored;
  } catch {
    /* fall through to default */
  }
  return "en";
}

let current: Lang = readStored();
const listeners = new Set<() => void>();

export function getLang(): Lang {
  return current;
}

export function setLang(lang: Lang): void {
  current = lang;
  try {
    localStorage.setItem(STORAGE_KEY, lang);
  } catch {
    /* not persisted; the choice still applies for this session */
  }
  if (typeof document !== "undefined") document.documentElement.lang = lang;
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useLang(): { lang: Lang; t: (key: MessageKey, vars?: Vars) => string; setLang: (l: Lang) => void } {
  const lang = useSyncExternalStore(subscribe, () => current, () => "en" as Lang);
  return { lang, t: (key, vars) => translate(lang, key, vars), setLang };
}

if (typeof document !== "undefined") document.documentElement.lang = current;
