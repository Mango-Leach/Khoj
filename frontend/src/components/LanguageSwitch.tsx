import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { Check, ChevronDown, Globe } from "lucide-react";
import { LANGS, useLang } from "../lib/i18n";
import { cx } from "./ui";

/**
 * One button showing the current language, and a menu of the three. Each language is named in
 * its own script so a learner can find theirs without reading English. `tone="dark"` is for a
 * dark or coloured background, where the button is a translucent white pill.
 */
export function LanguageSwitch({ tone = "light" }: { tone?: "light" | "dark" }) {
  const { lang, t, setLang } = useLang();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const optionRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const menuId = useId();
  const currentIndex = Math.max(0, LANGS.findIndex((l) => l.code === lang));
  const current = LANGS[currentIndex];

  // A press anywhere outside the control closes the menu.
  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  // Opening moves focus to the language in use, so the keyboard starts where the learner is.
  useEffect(() => {
    if (open) optionRefs.current[currentIndex]?.focus();
  }, [open, currentIndex]);

  const close = (returnFocus: boolean) => {
    setOpen(false);
    if (returnFocus) buttonRef.current?.focus();
  };

  const choose = (code: (typeof LANGS)[number]["code"]) => {
    setLang(code);
    close(true);
  };

  const onMenuKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const at = optionRefs.current.findIndex((el) => el === document.activeElement);
    const move = (i: number) => {
      e.preventDefault();
      optionRefs.current[(i + LANGS.length) % LANGS.length]?.focus();
    };
    if (e.key === "ArrowDown") move(at + 1);
    else if (e.key === "ArrowUp") move(at - 1);
    else if (e.key === "Home") move(0);
    else if (e.key === "End") move(LANGS.length - 1);
    else if (e.key === "Escape") {
      e.preventDefault();
      close(true);
    } else if (e.key === "Tab") close(false);
  };

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        aria-label={`${t("lang.label")}: ${current.label}`}
        onClick={() => setOpen((v) => !v)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown" && !open) {
            e.preventDefault();
            setOpen(true);
          }
        }}
        className={cx(
          "inline-flex h-11 items-center gap-2 rounded-full border-[1.5px] pr-3 pl-3.5 text-[16px] font-semibold transition-colors",
          tone === "dark"
            ? "border-white/30 bg-white/12 text-white hover:bg-white/20"
            : "border-line-strong bg-surface text-ink shadow-(--shadow-soft) hover:border-accent hover:text-accent",
        )}
      >
        <Globe className="size-[18px] shrink-0" aria-hidden="true" />
        <span lang={current.code}>{current.label}</span>
        <ChevronDown className={cx("size-4 shrink-0 transition-transform duration-200", open && "rotate-180")} aria-hidden="true" />
      </button>

      {open && (
        <div
          id={menuId}
          role="listbox"
          aria-label={t("lang.label")}
          onKeyDown={onMenuKeyDown}
          className="absolute top-[calc(100%+8px)] right-0 z-[60] min-w-[11.5rem] overflow-hidden rounded-2xl border border-line bg-white p-1.5 text-ink shadow-[0_18px_40px_-16px_rgb(11_13_28/0.35)]"
        >
          {LANGS.map((l, i) => {
            const active = l.code === lang;
            return (
              <button
                key={l.code}
                ref={(el) => {
                  optionRefs.current[i] = el;
                }}
                type="button"
                role="option"
                lang={l.code}
                aria-selected={active}
                onClick={() => choose(l.code)}
                className={cx(
                  "flex h-12 w-full items-center justify-between gap-4 rounded-xl px-4 text-left text-[16px] font-semibold transition-colors",
                  active ? "bg-tint text-accent" : "text-ink hover:bg-tint hover:text-accent",
                )}
              >
                {l.label}
                {active && <Check className="size-[18px]" strokeWidth={3} aria-hidden="true" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
