import { Loader2, Square, Volume2 } from "lucide-react";
import { useLang } from "../lib/i18n";
import { useSpeaker } from "../lib/speech";
import { cx } from "./ui";

/** Reads `text` aloud in the current language. Not shown when the browser has no speech voice at all. */
export function ListenButton({ text, className }: { text: string; className?: string }) {
  const { t, lang } = useLang();
  const { available, speaking, loading, toggle } = useSpeaker(lang);
  if (!available) return null;
  return (
    <button
      type="button"
      onClick={() => toggle(text)}
      aria-pressed={speaking}
      aria-busy={loading || undefined}
      className={cx(
        "inline-flex h-12 shrink-0 items-center gap-2 rounded-full border-[1.5px] px-5 text-base font-semibold transition-colors",
        speaking ? "border-accent bg-accent text-white" : "border-line-strong bg-surface text-accent hover:border-accent",
        className,
      )}
    >
      {loading ? (
        <Loader2 className="size-5 animate-spin" aria-hidden="true" />
      ) : speaking ? (
        <Square className="size-4 fill-current" aria-hidden="true" />
      ) : (
        <Volume2 className="size-5" aria-hidden="true" />
      )}
      {speaking || loading ? t("listen.stop") : t("listen")}
    </button>
  );
}
