import { LANGS, useLang } from "../lib/i18n";
import { cx } from "./ui";

/** Three languages, each named in its own script, always visible. */
export function LanguageSwitch() {
  const { lang, t, setLang } = useLang();
  return (
    <div role="group" aria-label={t("lang.label")} className="flex gap-1 rounded-xl border border-line bg-surface p-1 shadow-(--shadow-soft)">
      {LANGS.map((l) => {
        const active = l.code === lang;
        return (
          <button
            key={l.code}
            type="button"
            lang={l.code}
            aria-pressed={active}
            onClick={() => setLang(l.code)}
            className={cx(
              "h-10 rounded-lg px-2 text-[14px] font-semibold transition-colors sm:px-4 sm:text-[15px]",
              active ? "bg-ink text-white" : "text-muted hover:bg-tint hover:text-accent",
            )}
          >
            {l.label}
          </button>
        );
      })}
    </div>
  );
}
