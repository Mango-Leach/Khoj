import { useId, useState, type ComponentType } from "react";
import { Briefcase, Compass, FileCheck2, Mic, Users, type LucideIcon } from "lucide-react";
import { cx } from "../../components/ui";
import { useLang, type MessageKey } from "../../lib/i18n";
import { JobsScreen, MentorScreen, PathsScreen, ReviewScreen, SpeakScreen } from "./mocks";
import { usePrefersReducedMotion } from "./hooks";

interface Stage {
  id: string;
  label: MessageKey;
  icon: LucideIcon;
  Screen: ComponentType;
}

const STAGES: Stage[] = [
  { id: "speak", label: "lp.tour.speak", icon: Mic, Screen: SpeakScreen },
  { id: "paths", label: "lp.tour.paths", icon: Compass, Screen: PathsScreen },
  { id: "mentor", label: "lp.tour.mentor", icon: Users, Screen: MentorScreen },
  { id: "review", label: "lp.tour.review", icon: FileCheck2, Screen: ReviewScreen },
  { id: "jobs", label: "lp.tour.jobs", icon: Briefcase, Screen: JobsScreen },
];

/**
 * The opening's working part: a product window that walks through the real journey, one
 * screen at a time. It advances by itself, pauses when pointed at, and every step is a button.
 */
export function Tour() {
  const { t } = useLang();
  const reduced = usePrefersReducedMotion();
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const baseId = useId();
  const { Screen } = STAGES[index];

  return (
    <div
      className="overflow-hidden rounded-[28px] border border-line bg-white shadow-[0_40px_90px_-30px_rgb(29_78_216/0.45),0_8px_24px_-12px_rgb(11_18_32/0.12)]"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      <div className="flex h-12 items-center border-b border-line bg-bg px-5" aria-hidden="true">
        <span className="flex gap-2">
          <i className="size-3 rounded-full bg-line-strong" />
          <i className="size-3 rounded-full bg-line-strong" />
          <i className="size-3 rounded-full bg-line-strong" />
        </span>
        <span className="mx-auto rounded-lg bg-white px-4 py-1 text-sm font-semibold text-muted shadow-(--shadow-soft)">{t("lp.tour.label")}</span>
        <span className="w-[52px]" />
      </div>

      <div id={`${baseId}-panel`} role="tabpanel" aria-labelledby={`${baseId}-${STAGES[index].id}`} className="h-[440px] overflow-hidden bg-white">
        <div key={index} className="tour-screen h-full">
          <Screen />
        </div>
      </div>

      <div role="tablist" aria-label={t("lp.tour.label")} className="grid grid-cols-5 border-t border-line">
        {STAGES.map(({ id, label, icon: Icon }, i) => {
          const active = i === index;
          return (
            <button
              key={id}
              id={`${baseId}-${id}`}
              type="button"
              role="tab"
              aria-selected={active}
              aria-controls={`${baseId}-panel`}
              onClick={() => setIndex(i)}
              className={cx(
                "relative flex h-[76px] items-center justify-center gap-2.5 text-[17px] font-semibold transition-colors",
                "max-sm:flex-col max-sm:gap-1 max-sm:text-sm",
                active ? "bg-tint text-accent" : "text-muted hover:bg-bg hover:text-ink",
              )}
            >
              {active && (
                <span
                  key={`bar-${index}`}
                  aria-hidden="true"
                  onAnimationEnd={() => setIndex((n) => (n + 1) % STAGES.length)}
                  className="tour-bar absolute inset-x-0 top-0 h-[3px] origin-left bg-accent"
                  style={{ animationPlayState: paused || reduced ? "paused" : "running" }}
                />
              )}
              <Icon className="size-[22px] shrink-0" aria-hidden="true" />
              {t(label)}
            </button>
          );
        })}
      </div>
    </div>
  );
}
