import { useCallback, useEffect, useState } from "react";
import { getLatestIntake, getSkills, isApiFailure, type IntakeSession, type SkillInfo } from "./api";
import { useLang } from "./i18n";

export type LatestIntake =
  | { state: "loading" }
  | { state: "none" }
  | { state: "error" }
  | { state: "ready"; session: IntakeSession };

/** The learner's most recent intake, or "none" when they have never started one. */
export function useLatestIntake(): LatestIntake {
  const [value, setValue] = useState<LatestIntake>({ state: "loading" });
  useEffect(() => {
    let alive = true;
    getLatestIntake()
      .then((session) => alive && setValue({ state: "ready", session }))
      .catch((err: unknown) => {
        if (!alive) return;
        setValue(isApiFailure(err) && err.status === 404 ? { state: "none" } : { state: "error" });
      });
    return () => {
      alive = false;
    };
  }, []);
  return value;
}

let skillCache: SkillInfo[] | null = null;

/** Turns a skill id from the controlled vocabulary into its name in the current language. */
export function useSkillNames(): (id: string) => string {
  const { lang } = useLang();
  const [skills, setSkills] = useState<SkillInfo[]>(skillCache ?? []);

  useEffect(() => {
    if (skillCache) return;
    getSkills()
      .then((res) => {
        skillCache = res.skills;
        setSkills(res.skills);
      })
      .catch(() => undefined);
  }, []);

  return useCallback((id: string) => skills.find((s) => s.id === id)?.name[lang] ?? id, [skills, lang]);
}
