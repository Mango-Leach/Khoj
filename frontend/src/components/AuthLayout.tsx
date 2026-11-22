import type { ReactNode } from "react";
import { ArrowLeft, Compass, Mic, UserCheck } from "lucide-react";
import { useLang } from "../lib/i18n";
import { ConnectionBadge } from "./ConnectionBadge";
import { Link } from "./Link";
import { LanguageSwitch } from "./LanguageSwitch";
import { Button, Logo } from "./ui";

/** The signed-out frame: a brand panel on the left, one task on the right. */
/** Splits "Speak your skill. Find your first income." so the promise can carry the colour. */
function splitTagline(text: string): [string, string] {
  const m = text.match(/^(.+?[.,।])\s+(.+)$/);
  return m ? [m[1], m[2]] : [text, ""];
}

export function AuthLayout({ children }: { children: ReactNode }) {
  const { t } = useLang();
  const [first, second] = splitTagline(t("app.tagline"));
  const how = [
    { icon: Mic, text: t("brand.how1") },
    { icon: Compass, text: t("brand.how2") },
    { icon: UserCheck, text: t("brand.how3") },
  ];
  return (
    <div className="grid min-h-dvh lg:grid-cols-[minmax(440px,5fr)_7fr]">
      <aside
        className="relative m-3 hidden flex-col justify-between rounded-[32px] bg-accent p-12 text-white lg:flex"
        style={{
          backgroundImage: "linear-gradient(rgb(255 255 255 / 0.07) 1px, transparent 1px), linear-gradient(90deg, rgb(255 255 255 / 0.07) 1px, transparent 1px)",
          backgroundSize: "56px 56px",
        }}
      >
        <Link to="/" aria-label="KHOJ" className="self-start">
          <Logo inverse />
        </Link>
        <div>
          <h1 className="max-w-[16ch] text-balance text-[46px] leading-[1.1] font-bold tracking-tight">
            <span className="block">{first}</span>
            {second && <span className="block text-lime">{second}</span>}
          </h1>
          <ul className="mt-12 flex flex-col gap-5">
            {how.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-center gap-4 text-lg text-white/90">
                <span className="grid size-11 shrink-0 place-items-center rounded-full bg-lime" aria-hidden="true">
                  <Icon className="size-5 text-night" />
                </span>
                {text}
              </li>
            ))}
          </ul>
        </div>
        <p className="text-[15px] text-white/70">{t("app.expansion")}</p>
      </aside>

      <div className="flex min-h-dvh flex-col">
        <header className="flex items-center justify-between gap-4 px-10 py-6">
          <Link to="/" aria-label="KHOJ" className="lg:invisible">
            <Logo />
          </Link>
          <div className="flex items-center gap-3">
            <ConnectionBadge />
            <LanguageSwitch />
          </div>
        </header>
        <main className="flex flex-1 items-center justify-center px-10 pb-20">
          <div className="w-full max-w-[480px]">{children}</div>
        </main>
      </div>
    </div>
  );
}

interface StepFrameProps {
  title: string;
  help?: string;
  step?: { current: number; total: number };
  onBack?: () => void;
  children: ReactNode;
  footer?: ReactNode;
}

/** One question per screen: a title, one task, a back button and one primary action. */
export function StepFrame({ title, help, step, onBack, children, footer }: StepFrameProps) {
  const { t } = useLang();
  return (
    <section className="step-in flex flex-col gap-7" aria-labelledby="step-title">
      <div className="flex flex-col gap-3">
        <div className="flex h-10 items-center justify-between">
          {onBack ? (
            <Button variant="ghost" full={false} onClick={onBack} icon={<ArrowLeft className="size-5" />} className="-ml-3 h-10 px-3 text-base">
              {t("common.back")}
            </Button>
          ) : (
            <span />
          )}
          {step && (
            <span className="tabular text-[15px] font-medium text-muted">{t("step.of", { current: step.current, total: step.total })}</span>
          )}
        </div>
        {step && (
          <div className="h-1.5 overflow-hidden rounded-full bg-tint-strong" role="presentation">
            <div
              className="h-full rounded-full bg-accent transition-[width] duration-500 ease-(--ease-out-expo)"
              style={{ width: `${(step.current / step.total) * 100}%` }}
            />
          </div>
        )}
        <h2 id="step-title" className="mt-2 text-[34px] leading-[1.15] font-bold tracking-tight text-balance text-ink">
          {title}
        </h2>
        {help && <p className="text-lg text-muted">{help}</p>}
      </div>
      {children}
      {footer && <div className="flex flex-col gap-3">{footer}</div>}
    </section>
  );
}
