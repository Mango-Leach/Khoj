import { Check, CircleHelp, X } from "lucide-react";
import type { PartialLocalised, SchemeCondition, SchemeStatus } from "../lib/api";
import { useLang, type Lang, type MessageKey } from "../lib/i18n";
import { cx } from "./ui";

/** The text in the learner's language, else English (and says it fell back), else nothing. */
export function pick(value: PartialLocalised | Partial<Record<Lang, string>> | undefined, lang: Lang): { text: string; fallback: boolean } {
  if (!value) return { text: "", fallback: false };
  const own = value[lang];
  if (own) return { text: own, fallback: false };
  return { text: value.en ?? "", fallback: lang !== "en" && Boolean(value.en) };
}

/** One of the three words a rule check can give. It is never "eligible" while a needed value is unknown. */
export function StatusChip({ status, compact = false }: { status: SchemeStatus; compact?: boolean }) {
  const { t } = useLang();
  const icon = compact ? "size-4" : "size-5";
  const style = {
    eligible: { box: "bg-ok-bg text-ok", icon: <Check className={icon} aria-hidden="true" /> },
    check_with_office: { box: "bg-warn-bg text-warn", icon: <CircleHelp className={icon} aria-hidden="true" /> },
    not_eligible: { box: "bg-line text-muted", icon: <X className={icon} aria-hidden="true" /> },
  }[status];
  return (
    <span className={cx("inline-flex shrink-0 items-center gap-1.5 self-start rounded-full font-semibold", compact ? "px-3 py-1 text-sm" : "gap-2 px-4 py-1.5 text-base", style.box)}>
      {style.icon}
      {t(`schemes.status.${status}` as MessageKey)}
    </span>
  );
}

export function Reasons({ title, items, tone }: { title: MessageKey; items: SchemeCondition[]; tone: "ok" | "bad" | "ask" }) {
  const { t, lang } = useLang();
  if (items.length === 0) return null;
  const Icon = tone === "ok" ? Check : tone === "bad" ? X : CircleHelp;
  const color = tone === "ok" ? "text-ok" : tone === "bad" ? "text-bad" : "text-warn";
  return (
    <div className="flex flex-col gap-1.5">
      <p className="text-sm font-semibold tracking-wide text-deep uppercase">{t(title)}</p>
      <ul className="flex flex-col gap-1.5">
        {items.map((c) => (
          <li key={c.fact + c.label.en} className="flex gap-2.5 text-base">
            <Icon className={cx("mt-0.5 size-5 shrink-0", color)} aria-hidden="true" />
            <span>{pick(c.label, lang).text}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** "This opens when you are 18 years old", for an age or class limit the learner has not reached yet. */
export function opensText(opens: { fact: "age" | "grade"; value: number }[], t: (k: MessageKey, v?: Record<string, string | number>) => string): string[] {
  return opens.map((o) => {
    if (o.fact === "age") return t("schemes.opens.age", { n: o.value });
    return o.value >= 13 ? t("schemes.opens.college") : t("schemes.opens.grade", { n: o.value });
  });
}
