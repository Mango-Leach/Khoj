import { useCallback, useEffect, useState } from "react";
import { getHealth, type Health } from "../lib/api";
import { useLang, type MessageKey } from "../lib/i18n";

type State = { phase: "loading" } | { phase: "error" } | { phase: "ready"; health: Health };
type Tone = "ok" | "warn" | "bad" | "idle";

interface Row {
  label: MessageKey;
  text: MessageKey;
  tone: Tone;
}

function rowsFor(state: State): Row[] {
  if (state.phase === "loading") {
    const idle = (label: MessageKey): Row => ({ label, text: "status.checking", tone: "idle" });
    return [idle("status.server"), idle("status.database"), idle("status.ollama"), idle("status.gemini")];
  }
  if (state.phase === "error") {
    return [
      { label: "status.server", text: "status.unreachable", tone: "bad" },
      { label: "status.database", text: "status.unreachable", tone: "idle" },
      { label: "status.ollama", text: "status.unreachable", tone: "idle" },
      { label: "status.gemini", text: "status.unreachable", tone: "idle" },
    ];
  }
  const { db, llm } = state.health;
  return [
    { label: "status.server", text: "status.ok", tone: "ok" },
    db.ok
      ? { label: "status.database", text: "status.ok", tone: "ok" }
      : db.configured
        ? { label: "status.database", text: "status.unreachable", tone: "bad" }
        : { label: "status.database", text: "status.notConfigured", tone: "warn" },
    llm.ollama.reachable
      ? { label: "status.ollama", text: "status.ok", tone: "ok" }
      : { label: "status.ollama", text: "status.unreachable", tone: "warn" },
    llm.gemini.configured
      ? { label: "status.gemini", text: "status.configured", tone: "ok" }
      : { label: "status.gemini", text: "status.notConfigured", tone: "warn" },
  ];
}

const TONE_CLASS: Record<Tone, string> = {
  ok: "text-ok",
  warn: "text-warn",
  bad: "text-bad",
  idle: "text-muted",
};

export function StatusPanel() {
  const { t } = useLang();
  const [state, setState] = useState<State>({ phase: "loading" });

  const load = useCallback((signal?: AbortSignal) => {
    setState({ phase: "loading" });
    getHealth(signal)
      .then((health) => setState({ phase: "ready", health }))
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setState({ phase: "error" });
      });
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  return (
    <section aria-labelledby="status-title" className="rounded-xl border border-line bg-surface p-4">
      <h2 id="status-title" className="text-lg font-semibold">
        {t("status.title")}
      </h2>
      <dl className="mt-3 divide-y divide-line">
        {rowsFor(state).map((row) => (
          <div key={row.label} className="flex min-h-12 items-center justify-between gap-4 py-2">
            <dt>{t(row.label)}</dt>
            <dd className={"font-semibold " + TONE_CLASS[row.tone]}>{t(row.text)}</dd>
          </div>
        ))}
      </dl>
      <button
        type="button"
        onClick={() => load()}
        className="mt-3 min-h-12 w-full rounded-lg border border-line px-4 font-semibold hover:border-accent"
      >
        {t("status.retry")}
      </button>
    </section>
  );
}
