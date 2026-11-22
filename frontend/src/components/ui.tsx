import { useId, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from "react";
import { AlertCircle, Check, ChevronRight, Loader2 } from "lucide-react";
import markUrl from "../assets/khoj-mark.svg";

export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

// ---------------------------------------------------------------------------
// Logo: a placeholder mark (a magnifier, from the name "khoj" = search). The real mark is still to be designed.
// ---------------------------------------------------------------------------

export function Logo({ inverse = false, large = false }: { inverse?: boolean; large?: boolean }) {
  return (
    <span className={cx("inline-flex items-center", large ? "gap-3 lg:gap-3.5" : "gap-2.5")}>
      {/* The mark has a transparent background, so it sits straight on the page. On a dark or coloured background it gets a white tile. */}
      {inverse ? (
        <span
          className={cx(
            "grid place-items-center bg-white",
            large ? "size-11 rounded-xl sm:size-14 sm:rounded-2xl lg:size-[58px] lg:rounded-[18px]" : "size-12 rounded-xl",
          )}
          aria-hidden="true"
        >
          <img src={markUrl} alt="" className={large ? "h-7 w-auto sm:h-9 lg:h-[37px]" : "h-9 w-auto"} width={32} height={36} />
        </span>
      ) : (
        <img src={markUrl} alt="" aria-hidden="true" className={large ? "h-10 w-auto sm:h-12 lg:h-14" : "h-11 w-auto"} width={39} height={44} />
      )}
      <span
        className={cx(
          "font-bold tracking-wide",
          large ? "text-[22px] sm:text-[26px] lg:text-[29px]" : "text-[22px]",
          inverse ? "text-white" : "text-ink",
        )}
      >
        KHOJ
      </span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// Buttons
// ---------------------------------------------------------------------------

type Variant = "primary" | "secondary" | "ghost";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  loading?: boolean;
  icon?: ReactNode;
  full?: boolean;
}

const VARIANTS: Record<Variant, string> = {
  primary: "bg-night text-white hover:bg-black active:bg-night",
  secondary: "border-[1.5px] border-line-strong bg-surface text-ink hover:border-accent hover:text-accent",
  ghost: "text-muted hover:bg-tint hover:text-accent",
};

export function Button({ variant = "primary", loading = false, icon, full = true, className, children, disabled, ...rest }: ButtonProps) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cx(
        "inline-flex h-14 items-center justify-center gap-2.5 rounded-full px-7 text-lg font-semibold transition-colors",
        "disabled:cursor-not-allowed disabled:opacity-55",
        full && "w-full",
        VARIANTS[variant],
        className,
      )}
    >
      {loading ? <Loader2 className="size-5 animate-spin" aria-hidden="true" /> : icon}
      {children}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Form fields
// ---------------------------------------------------------------------------

interface FieldShellProps {
  label: string;
  help?: string;
  error?: string | null;
  children: (ids: { inputId: string; describedBy: string | undefined; invalid: boolean }) => ReactNode;
}

function FieldShell({ label, help, error, children }: FieldShellProps) {
  const id = useId();
  const helpId = help ? `${id}-help` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [errorId, helpId].filter(Boolean).join(" ") || undefined;
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="text-base font-semibold text-ink">
        {label}
      </label>
      {children({ inputId: id, describedBy, invalid: Boolean(error) })}
      {help && !error && (
        <p id={helpId} className="text-[15px] text-muted">
          {help}
        </p>
      )}
      {error && (
        <p id={errorId} role="alert" className="flex items-start gap-1.5 text-[15px] font-medium text-bad">
          <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          {error}
        </p>
      )}
    </div>
  );
}

const INPUT_CLASS =
  "h-14 w-full rounded-2xl border-[1.5px] bg-surface px-4 text-xl text-ink outline-none transition-colors " +
  "placeholder:text-[#6b7690] focus:border-accent focus:ring-4 focus:ring-tint-strong";

interface TextFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "id"> {
  label: string;
  help?: string;
  error?: string | null;
  prefix?: string;
}

export function TextField({ label, help, error, prefix, className, ...rest }: TextFieldProps) {
  return (
    <FieldShell label={label} help={help} error={error}>
      {({ inputId, describedBy, invalid }) => (
        <div className="relative">
          {prefix && (
            <span className="pointer-events-none absolute inset-y-0 left-4 flex items-center border-r border-line pr-3 text-xl font-semibold text-muted">
              {prefix}
            </span>
          )}
          <input
            {...rest}
            id={inputId}
            aria-invalid={invalid || undefined}
            aria-describedby={describedBy}
            className={cx(INPUT_CLASS, invalid ? "border-bad" : "border-line-strong", prefix && "pl-[4.75rem]", className)}
          />
        </div>
      )}
    </FieldShell>
  );
}

interface SelectFieldProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, "id"> {
  label: string;
  help?: string;
  error?: string | null;
}

export function SelectField({ label, help, error, className, children, ...rest }: SelectFieldProps) {
  return (
    <FieldShell label={label} help={help} error={error}>
      {({ inputId, describedBy, invalid }) => (
        <select
          {...rest}
          id={inputId}
          aria-invalid={invalid || undefined}
          aria-describedby={describedBy}
          className={cx(INPUT_CLASS, "appearance-auto", invalid ? "border-bad" : "border-line-strong", className)}
        >
          {children}
        </select>
      )}
    </FieldShell>
  );
}

// ---------------------------------------------------------------------------
// Choice: a large selectable row or chip. Selected state is shown by border, tint AND a check mark.
// ---------------------------------------------------------------------------

interface ChoiceProps {
  selected: boolean;
  onSelect: () => void;
  title: string;
  description?: string;
  icon?: ReactNode;
  /** "action" is a one-tap row that goes somewhere; the others keep a selection. */
  type?: "radio" | "checkbox" | "action";
  compact?: boolean;
}

export function Choice({ selected, onSelect, title, description, icon, type = "radio", compact = false }: ChoiceProps) {
  return (
    <button
      type="button"
      role={type === "action" ? undefined : type}
      aria-checked={type === "action" ? undefined : selected}
      onClick={onSelect}
      className={cx(
        "flex w-full items-center gap-4 rounded-3xl border-[1.5px] text-left transition-colors",
        compact ? "min-h-14 px-4 py-2.5" : "min-h-[72px] px-5 py-3.5",
        selected ? "border-accent bg-tint" : "border-line bg-surface hover:border-line-strong",
      )}
    >
      {icon && (
        <span
          className={cx("grid size-11 shrink-0 place-items-center rounded-xl", selected ? "bg-accent text-white" : "bg-tint text-accent")}
          aria-hidden="true"
        >
          {icon}
        </span>
      )}
      <span className="min-w-0 flex-1">
        <span className="block text-lg font-semibold text-ink">{title}</span>
        {description && <span className="block text-[15px] text-muted">{description}</span>}
      </span>
      {type === "action" ? (
        <ChevronRight className="size-6 shrink-0 text-muted" aria-hidden="true" />
      ) : (
        <span
          className={cx(
            "grid size-7 shrink-0 place-items-center border-2",
            type === "radio" ? "rounded-full" : "rounded-md",
            selected ? "border-accent bg-accent text-white" : "border-line-strong bg-surface",
          )}
          aria-hidden="true"
        >
          {selected && <Check className="size-4" strokeWidth={3} />}
        </span>
      )}
    </button>
  );
}

/** A short pill choice for grades, hours and the like. */
export function Pill({ selected, onSelect, children }: { selected: boolean; onSelect: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={onSelect}
      className={cx(
        "min-h-12 rounded-full border-[1.5px] px-5 text-base font-semibold transition-colors",
        selected ? "border-accent bg-accent text-white" : "border-line-strong bg-surface text-ink hover:border-accent",
      )}
    >
      {children}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Notice: errors and quiet information
// ---------------------------------------------------------------------------

export function Notice({ tone = "error", children }: { tone?: "error" | "info"; children: ReactNode }) {
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={cx(
        "flex items-start gap-3 rounded-2xl px-4 py-3 text-base font-medium",
        tone === "error" ? "bg-bad-bg text-bad" : "bg-tint text-deep",
      )}
    >
      <AlertCircle className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
      <span>{children}</span>
    </div>
  );
}
