import { useCallback, useEffect, useState } from "react";
import {
  createAssessment,
  getAssessment,
  getLatestAssessment,
  getLatestIntake,
  getMyJourney,
  isApiFailure,
  type Assessment,
  type Journey,
} from "./api";

export type PathsState =
  | { state: "loading" }
  | { state: "no_intake" }
  | { state: "error" }
  | { state: "ready"; assessment: Assessment };

const POLL_MS = 2000;
const POLL_MAX = 10;

const notFound = (err: unknown): boolean => isApiFailure(err) && err.status === 404;

/**
 * The learner's paths. They are ranked by the server when the learner has finished the questions, and ranked again
 * when the questions were answered again since. The nicer one-sentence reasons arrive a little later, so while the
 * server says they are pending this asks a few more times and swaps them in.
 */
export function usePaths(): PathsState {
  const [value, setValue] = useState<PathsState>({ state: "loading" });

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const poll = (id: string, tries: number) => {
      timer = setTimeout(() => {
        getAssessment(id)
          .then((a) => {
            if (!alive) return;
            setValue({ state: "ready", assessment: a });
            if (a.enrichment === "pending" && tries < POLL_MAX) poll(id, tries + 1);
          })
          .catch(() => undefined); // the paths already on screen stay
      }, POLL_MS);
    };

    (async () => {
      try {
        let intake;
        try {
          intake = await getLatestIntake();
        } catch (err) {
          if (notFound(err)) return alive && setValue({ state: "no_intake" });
          throw err;
        }
        if (intake.status !== "done") return alive && setValue({ state: "no_intake" });

        let assessment: Assessment | null = null;
        try {
          assessment = await getLatestAssessment();
        } catch (err) {
          if (!notFound(err)) throw err;
        }
        if (!assessment || assessment.intake_id !== intake.id) assessment = await createAssessment();
        if (!alive) return;
        setValue({ state: "ready", assessment });
        if (assessment.enrichment === "pending") poll(assessment.id, 1);
      } catch {
        if (alive) setValue({ state: "error" });
      }
    })();

    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
    };
  }, []);

  return value;
}

/** The learner's current choice, or null when they have not picked a path. */
export function useJourney(): { journey: Journey | null; set: (j: Journey) => void; loaded: boolean } {
  const [journey, setJourney] = useState<Journey | null>(null);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    let alive = true;
    getMyJourney()
      .then((j) => alive && setJourney(j))
      .catch(() => undefined)
      .finally(() => alive && setLoaded(true));
    return () => {
      alive = false;
    };
  }, []);
  const set = useCallback((j: Journey) => setJourney(j), []);
  return { journey, set, loaded };
}
