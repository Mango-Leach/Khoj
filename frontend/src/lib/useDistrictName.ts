import { useCallback, useEffect, useState } from "react";
import { getDistricts, type District } from "./api";
import { useLang } from "./i18n";

let cache: District[] | null = null;

/** Returns a function that turns a stored district id into its name in the current language. */
export function useDistrictName(): (id: string) => string {
  const { lang } = useLang();
  const [districts, setDistricts] = useState<District[]>(cache ?? []);

  useEffect(() => {
    if (cache) return;
    getDistricts()
      .then((res) => {
        cache = res.districts;
        setDistricts(res.districts);
      })
      .catch(() => undefined);
  }, []);

  return useCallback((id: string) => districts.find((d) => d.id === id)?.[lang] ?? id, [districts, lang]);
}
