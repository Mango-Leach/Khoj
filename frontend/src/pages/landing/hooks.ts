import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import type { Lang } from "../../lib/i18n";

// ---------------------------------------------------------------------------
// Motion preference: every animation on this page respects it.
// ---------------------------------------------------------------------------

const QUERY = "(prefers-reduced-motion: reduce)";

function subscribeMotion(cb: () => void): () => void {
  const mq = window.matchMedia(QUERY);
  mq.addEventListener("change", cb);
  return () => mq.removeEventListener("change", cb);
}

export function usePrefersReducedMotion(): boolean {
  return useSyncExternalStore(subscribeMotion, () => window.matchMedia(QUERY).matches, () => false);
}

// ---------------------------------------------------------------------------
// Scroll reveal: true once the element has entered the viewport (and stays true).
// ---------------------------------------------------------------------------

export function useInView<T extends Element>(threshold = 0.15): [React.RefObject<T | null>, boolean] {
  const ref = useRef<T | null>(null);
  const [seen, setSeen] = useState(false);
  const reduced = usePrefersReducedMotion();

  useEffect(() => {
    const el = ref.current;
    if (!el || seen) return;
    if (reduced || typeof IntersectionObserver === "undefined") {
      setSeen(true);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setSeen(true);
          io.disconnect();
        }
      },
      { threshold, rootMargin: "0px 0px -8% 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [seen, reduced, threshold]);

  return [ref, seen];
}

// ---------------------------------------------------------------------------
// Typewriter for the voice demo. Restarts when the text or `active` changes.
// ---------------------------------------------------------------------------

export function useTypewriter(text: string, active: boolean, msPerChar = 42): { shown: string; done: boolean } {
  const reduced = usePrefersReducedMotion();
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (!active) {
      setCount(0);
      return;
    }
    if (reduced) {
      setCount(text.length);
      return;
    }
    setCount(0);
    const chars = Array.from(text).length;
    const timer = window.setInterval(() => {
      setCount((c) => {
        if (c >= chars) {
          window.clearInterval(timer);
          return c;
        }
        return c + 1;
      });
    }, msPerChar);
    return () => window.clearInterval(timer);
  }, [text, active, reduced, msPerChar]);

  const chars = Array.from(text);
  return { shown: chars.slice(0, count).join(""), done: count >= chars.length };
}

// ---------------------------------------------------------------------------
// Scroll progress of a tall element through the viewport, 0 to 1. Drives the drawn journey line.
// ---------------------------------------------------------------------------

export function useScrollProgress<T extends HTMLElement>(): [React.RefObject<T | null>, number] {
  const ref = useRef<T | null>(null);
  const [progress, setProgress] = useState(0);
  const reduced = usePrefersReducedMotion();

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (reduced) {
      setProgress(1);
      return;
    }
    let frame = 0;
    const update = () => {
      frame = 0;
      const rect = el.getBoundingClientRect();
      const vh = window.innerHeight;
      // The line reaches the end when the bottom of the section passes 60% of the viewport.
      const p = (vh * 0.6 - rect.top) / Math.max(rect.height, 1);
      setProgress(Math.min(1, Math.max(0, p)));
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [reduced]);

  return [ref, progress];
}

// ---------------------------------------------------------------------------
// True after the page has scrolled a little, for the sticky navigation bar.
// ---------------------------------------------------------------------------

export function useScrolled(offset = 12): boolean {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > offset);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [offset]);
  return scrolled;
}

// ---------------------------------------------------------------------------
// Cycle through the three languages, for the voice section.
// ---------------------------------------------------------------------------

export const CYCLE: Lang[] = ["hi", "mr", "en"];

export function useLanguageCycle(everyMs = 3400): Lang {
  const reduced = usePrefersReducedMotion();
  const [i, setI] = useState(0);
  useEffect(() => {
    if (reduced) return;
    const timer = window.setInterval(() => setI((n) => (n + 1) % CYCLE.length), everyMs);
    return () => window.clearInterval(timer);
  }, [reduced, everyMs]);
  return CYCLE[i];
}
