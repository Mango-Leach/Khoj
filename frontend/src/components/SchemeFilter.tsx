import { useState } from "react";
import {
  BookOpen,
  Check,
  ChevronDown,
  GraduationCap,
  Hammer,
  Landmark,
  Loader2,
  Lock,
  School,
  SlidersHorizontal,
  Users,
  Wallet,
  Banknote,
  X,
  type LucideIcon,
} from "lucide-react";
import type { SchemeFactKey, SchemeFacts } from "../lib/api";
import { useLang, type MessageKey } from "../lib/i18n";
import { cx } from "./ui";

const CHOICES: Partial<Record<SchemeFactKey, string[]>> = {
  social_category: ["sc", "st", "obc", "dnt", "ebc", "general"],
  school_type: ["government", "government_aided", "local_body", "private", "central_residential"],
  qualification: ["none", "diploma", "vocational_certificate", "graduate"],
};
const YES_NO: SchemeFactKey[] = ["in_professional_course", "works_in_listed_trade", "govt_service_in_family", "took_similar_loan_5y"];

const ICONS: Record<SchemeFactKey, LucideIcon> = {
  social_category: Users,
  annual_income_inr: Wallet,
  govt_service_in_family: Landmark,
  school_type: School,
  in_professional_course: BookOpen,
  qualification: GraduationCap,
  works_in_listed_trade: Hammer,
  took_similar_loan_5y: Banknote,
};

// Questions are grouped so a long list reads as three short ones.
const SECTIONS: { key: "family" | "studies" | "work"; facts: SchemeFactKey[] }[] = [
  { key: "family", facts: ["social_category", "annual_income_inr", "govt_service_in_family"] },
  { key: "studies", facts: ["school_type", "in_professional_course", "qualification"] },
  { key: "work", facts: ["works_in_listed_trade", "took_similar_loan_5y"] },
];

const INR = new Intl.NumberFormat("en-IN");

function without(facts: SchemeFacts, fact: SchemeFactKey): SchemeFacts {
  const next = { ...facts } as Record<string, unknown>;
  delete next[fact];
  return next as SchemeFacts;
}

function Chip({ selected, onClick, children }: { selected: boolean; onClick: () => void; children: string }) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={onClick}
      className={cx(
        "inline-flex min-h-11 items-center gap-1.5 rounded-full border-[1.5px] px-4 text-[15px] font-semibold transition-colors",
        selected ? "border-accent bg-accent text-white" : "border-line-strong bg-surface text-ink hover:border-accent hover:text-accent",
      )}
    >
      {selected && <Check className="size-4 shrink-0" aria-hidden="true" />}
      {children}
    </button>
  );
}

function YesNo({ value, onChange, label }: { value: boolean | undefined; onChange: (v: boolean | undefined) => void; label: string }) {
  const { t } = useLang();
  return (
    <div role="radiogroup" aria-label={label} className="grid grid-cols-2 gap-1 rounded-xl bg-bg p-1">
      {[
        { v: true, text: t("schemes.yes") },
        { v: false, text: t("schemes.no") },
      ].map((o) => (
        <button
          key={String(o.v)}
          type="button"
          role="radio"
          aria-checked={value === o.v}
          onClick={() => onChange(value === o.v ? undefined : o.v)}
          className={cx(
            "min-h-11 rounded-lg text-[15px] font-semibold transition-colors",
            value === o.v ? "bg-accent text-white shadow-(--shadow-soft)" : "text-ink hover:bg-tint hover:text-accent",
          )}
        >
          {o.text}
        </button>
      ))}
    </div>
  );
}

function IncomeInput({ value, onChange, label }: { value: number | undefined; onChange: (v: number | undefined) => void; label: string }) {
  const { t } = useLang();
  const lakh = value !== undefined ? Number((value / 100000).toFixed(2)) : null;
  return (
    <div className="flex flex-col gap-2">
      <div className="flex h-12 items-center overflow-hidden rounded-xl border-[1.5px] border-line-strong bg-surface focus-within:border-accent focus-within:ring-4 focus-within:ring-tint-strong">
        <span className="grid h-full w-12 place-items-center border-r border-line bg-bg text-lg font-semibold text-muted" aria-hidden="true">
          ₹
        </span>
        <input
          type="text"
          inputMode="numeric"
          autoComplete="off"
          maxLength={9}
          aria-label={label}
          placeholder={t("schemes.income.unit")}
          value={value !== undefined ? String(value) : ""}
          onChange={(e) => {
            const digits = e.target.value.replace(/\D/g, "");
            onChange(digits === "" ? undefined : Number(digits));
          }}
          className="h-full min-w-0 flex-1 bg-transparent px-3 text-lg text-ink outline-none placeholder:text-[#6b7690]"
        />
      </div>
      {value !== undefined && (
        <p className="text-sm font-medium text-deep" aria-live="polite">
          ₹{INR.format(value)} {t("schemes.income.perYear")} ({t("schemes.income.lakh", { n: lakh ?? 0 })})
        </p>
      )}
    </div>
  );
}

function Question({
  fact,
  facts,
  usedBy,
  onChange,
}: {
  fact: SchemeFactKey;
  facts: SchemeFacts;
  usedBy: number;
  onChange: (next: SchemeFacts) => void;
}) {
  const { t } = useLang();
  const Icon = ICONS[fact];
  const label = t(`schemes.question.${fact}` as MessageKey);
  const current = facts[fact];
  const answered = current !== undefined;
  const set = (value: unknown) => onChange({ ...facts, [fact]: value } as SchemeFacts);

  let control;
  if (fact === "annual_income_inr") {
    control = <IncomeInput label={label} value={facts.annual_income_inr} onChange={(v) => onChange(v === undefined ? without(facts, fact) : { ...facts, annual_income_inr: v })} />;
  } else if (YES_NO.includes(fact)) {
    control = <YesNo label={label} value={current as boolean | undefined} onChange={(v) => onChange(v === undefined ? without(facts, fact) : ({ ...facts, [fact]: v } as SchemeFacts))} />;
  } else {
    control = (
      <div role="radiogroup" aria-label={label} className="flex flex-wrap gap-2">
        {(CHOICES[fact] ?? []).map((v) => (
          <Chip key={v} selected={current === v} onClick={() => (current === v ? onChange(without(facts, fact)) : set(v))}>
            {t(`schemes.opt.${fact}.${v}` as MessageKey)}
          </Chip>
        ))}
      </div>
    );
  }

  return (
    <div className={cx("flex flex-col gap-3 rounded-xl border p-4 transition-colors", answered ? "border-accent/40 bg-tint/50" : "border-line bg-surface")}>
      <div className="flex items-start gap-3">
        <span className={cx("grid size-9 shrink-0 place-items-center rounded-lg", answered ? "bg-accent text-white" : "bg-tint text-accent")} aria-hidden="true">
          <Icon className="size-[18px]" />
        </span>
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <p className="text-[15px] leading-snug font-semibold">{label}</p>
          <p className="text-sm text-muted">{t("schemes.usedBy", { n: usedBy })}</p>
        </div>
        {answered && (
          <button
            type="button"
            onClick={() => onChange(without(facts, fact))}
            aria-label={t("schemes.clearOne")}
            title={t("schemes.clearOne")}
            className="grid size-9 shrink-0 place-items-center rounded-lg text-muted hover:bg-bg hover:text-bad"
          >
            <X className="size-5" aria-hidden="true" />
          </button>
        )}
      </div>
      {control}
    </div>
  );
}

/**
 * The questions beside the results. Answers change the results as they are given (after a short pause), so it works like
 * a filter. Only questions some scheme actually uses are shown, and nothing typed here is stored.
 */
export function SchemeFilter({
  wanted,
  usedBy,
  facts,
  onChange,
  busy,
}: {
  wanted: SchemeFactKey[];
  usedBy: Record<string, number>;
  facts: SchemeFacts;
  onChange: (next: SchemeFacts) => void;
  busy: boolean;
}) {
  const { t } = useLang();
  const [open, setOpen] = useState(false); // phones: the panel starts folded so the results are not pushed far down
  const done = wanted.filter((f) => facts[f] !== undefined).length;
  const percent = wanted.length ? Math.round((done / wanted.length) * 100) : 0;

  return (
    <section
      className="flex flex-col rounded-2xl border border-line bg-surface shadow-(--shadow-soft) lg:sticky lg:top-4 lg:max-h-[calc(100dvh-2rem)] lg:overflow-y-auto"
      aria-labelledby="schemes-questions"
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls="schemes-filter-body"
        className="flex w-full items-center gap-3 p-5 text-left lg:pointer-events-none lg:cursor-default"
      >
        <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-tint text-accent" aria-hidden="true">
          <SlidersHorizontal className="size-5" />
        </span>
        <span className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span id="schemes-questions" className="text-xl leading-tight font-bold tracking-tight">
            {t("schemes.questions.title")}
          </span>
          <span className="text-sm font-medium text-muted">{t("schemes.progress", { done, total: wanted.length })}</span>
        </span>
        <ChevronDown className={cx("size-6 shrink-0 text-muted transition-transform lg:hidden", open && "rotate-180")} aria-hidden="true" />
      </button>

      <div className="mx-5 h-1.5 overflow-hidden rounded-full bg-line" role="progressbar" aria-valuemin={0} aria-valuemax={wanted.length} aria-valuenow={done} aria-label={t("schemes.progress", { done, total: wanted.length })}>
        <div className="h-full rounded-full bg-accent transition-[width] duration-300" style={{ width: `${percent}%` }} />
      </div>

      <div id="schemes-filter-body" className={cx("flex-col gap-5 p-5", open ? "flex" : "hidden lg:flex")}>
        <p className="flex items-start gap-2.5 rounded-xl bg-tint p-3 text-sm text-deep">
          <Lock className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <span>{t("schemes.privacy")}</span>
        </p>

        {SECTIONS.map((section) => {
          const facts_here = section.facts.filter((f) => wanted.includes(f));
          if (facts_here.length === 0) return null;
          return (
            <fieldset key={section.key} className="flex min-w-0 flex-col gap-3">
              <legend className="mb-1 flex w-full items-center gap-3 text-sm font-semibold tracking-wide text-deep uppercase">
                <span>{t(`schemes.section.${section.key}` as MessageKey)}</span>
                <span className="h-px flex-1 bg-line" aria-hidden="true" />
              </legend>
              {facts_here.map((f) => (
                <Question key={f} fact={f} facts={facts} usedBy={usedBy[f] ?? 0} onChange={onChange} />
              ))}
            </fieldset>
          );
        })}

        <div className="flex items-center justify-between gap-3 border-t border-line pt-4">
          <p className="flex items-center gap-2 text-sm font-medium text-muted" role="status">
            {busy ? (
              <>
                <Loader2 className="size-4 animate-spin text-accent" aria-hidden="true" />
                {t("schemes.updating")}
              </>
            ) : (
              <>
                <Check className="size-4 text-ok" aria-hidden="true" />
                {t("schemes.updated")}
              </>
            )}
          </p>
          <button
            type="button"
            onClick={() => onChange({})}
            disabled={done === 0}
            className="min-h-11 rounded-xl px-3 text-[15px] font-semibold text-accent hover:bg-tint disabled:pointer-events-none disabled:text-muted disabled:opacity-60"
          >
            {t("schemes.clear")}
          </button>
        </div>
      </div>
    </section>
  );
}
