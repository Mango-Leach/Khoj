import type { ReactNode } from "react";
import { cx } from "./ui";

const GRID = "linear-gradient(rgb(255 255 255 / 0.07) 1px, transparent 1px), linear-gradient(90deg, rgb(255 255 255 / 0.07) 1px, transparent 1px)";

export const GRID_STYLE = { backgroundImage: GRID, backgroundSize: "56px 56px" } as const;

interface PageBannerProps {
  title: string;
  lead?: string;
  /** Something that belongs on the right of the title: a status, a button, a small card. */
  aside?: ReactNode;
  /** "lg" is the greeting on Home; everything else uses "md". */
  size?: "md" | "lg";
}

/** The blue heading of a signed-in page: one title, one line of help, and at most one thing on the right. */
export function PageBanner({ title, lead, aside, size = "md" }: PageBannerProps) {
  return (
    <header
      className="relative shrink-0 overflow-hidden rounded-[28px] bg-accent text-white"
      style={GRID_STYLE}
    >
      <div
        className={cx(
          "flex flex-col gap-5 md:flex-row md:justify-between md:gap-8",
          size === "lg" ? "p-7 md:items-center md:p-9" : "p-6 md:items-center md:px-9 md:py-7",
        )}
      >
        <div className="flex min-w-0 flex-col gap-2">
          <h1 className={cx("leading-[1.1] font-bold tracking-tight text-balance", size === "lg" ? "text-[30px] md:text-[40px]" : "text-[28px] md:text-[36px]")}>{title}</h1>
          {lead && <p className="max-w-3xl text-[17px] leading-relaxed text-white/80">{lead}</p>}
        </div>
        {aside && <div className="flex shrink-0 flex-wrap items-center gap-3">{aside}</div>}
      </div>
    </header>
  );
}
