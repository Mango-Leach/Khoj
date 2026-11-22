import { GraduationCap, Languages, MapPin, ShieldCheck, TriangleAlert } from "lucide-react";
import type { LearnerCard as Card } from "../lib/api";
import { LANGS, useLang, type MessageKey } from "../lib/i18n";
import { useDistrictName } from "../lib/useDistrictName";

/** What a mentor sees about a learner. Name, class, place, language and what they told us they can do. No phone number. */
export function LearnerCardView({ card }: { card: Card }) {
  const { t, lang } = useLang();
  const districtName = useDistrictName();
  const career = card.career.name?.[lang] ?? card.career.name?.en ?? card.career.career_id;
  const own = LANGS.find((l) => l.code === card.language)?.label ?? card.language;

  return (
    <div className="flex min-w-0 flex-col gap-4">
      <div className="flex items-center gap-3">
        <span className="grid size-12 shrink-0 place-items-center rounded-full bg-accent text-xl font-bold text-white" aria-hidden="true">
          {card.name.trim().charAt(0).toUpperCase()}
        </span>
        <div className="flex min-w-0 flex-col">
          <p className="truncate text-xl font-bold">{card.name}</p>
          <p className="text-base text-muted">{t("req.wants", { career })}</p>
        </div>
      </div>

      <ul className="flex flex-wrap gap-x-5 gap-y-1.5 text-[15px] text-muted">
        {card.grade !== null && (
          <li className="inline-flex items-center gap-1.5">
            <GraduationCap className="size-4 shrink-0" aria-hidden="true" />
            {t(`grade.${card.grade}` as MessageKey)}
          </li>
        )}
        {card.district && (
          <li className="inline-flex items-center gap-1.5">
            <MapPin className="size-4 shrink-0" aria-hidden="true" />
            {card.block}, {districtName(card.district)}
          </li>
        )}
        <li className="inline-flex items-center gap-1.5">
          <Languages className="size-4 shrink-0" aria-hidden="true" />
          {t("req.speaks", { language: own })}
        </li>
        {card.guardian_consent && (
          <li className="inline-flex items-center gap-1.5 text-ok">
            <ShieldCheck className="size-4 shrink-0" aria-hidden="true" />
            {t("req.consent")}
          </li>
        )}
      </ul>

      {card.skills.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <p className="text-sm font-semibold tracking-wide text-deep uppercase">{t("req.skills")}</p>
          <ul className="flex flex-wrap gap-2">
            {card.skills.map((s) => (
              <li key={s.id} className="rounded-full bg-tint px-3 py-1 text-[15px] font-semibold text-deep">
                {s.name[lang] ?? s.name.en}
              </li>
            ))}
          </ul>
        </div>
      )}

      {card.theory_only && (
        <p className="flex items-start gap-2.5 rounded-xl bg-warn-bg p-3 text-[15px] font-medium text-warn">
          <TriangleAlert className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
          <span>{t("req.theory")}</span>
        </p>
      )}
    </div>
  );
}
