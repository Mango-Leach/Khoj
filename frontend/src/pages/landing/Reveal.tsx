import type { CSSProperties, ElementType, ReactNode } from "react";
import { cx } from "../../components/ui";
import { useInView } from "./hooks";

type Variant = "up" | "scale" | "left";

interface RevealProps {
  children: ReactNode;
  variant?: Variant;
  /** Milliseconds before this element starts, for staggering lists. */
  delay?: number;
  className?: string;
  as?: ElementType;
}

/** Brings its content in once, when the visitor scrolls to it. */
export function Reveal({ children, variant = "up", delay = 0, className, as: Tag = "div" }: RevealProps) {
  const [ref, seen] = useInView<HTMLElement>();
  return (
    <Tag
      ref={ref}
      data-in={seen}
      style={{ "--d": `${delay}ms` } as CSSProperties}
      className={cx("reveal", variant === "scale" && "reveal-scale", variant === "left" && "reveal-left", className)}
    >
      {children}
    </Tag>
  );
}

/** Mounts its children only once scrolled into view, so their own animations start when seen. */
export function WhenSeen({ children, className, minHeight }: { children: ReactNode; className?: string; minHeight?: number }) {
  const [ref, seen] = useInView<HTMLDivElement>(0.3);
  return (
    <div ref={ref} className={className} style={minHeight ? { minHeight } : undefined}>
      {seen ? children : null}
    </div>
  );
}
