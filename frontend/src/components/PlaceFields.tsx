import { useEffect, useState } from "react";
import { getDistricts, type District } from "../lib/api";
import { useLang, type MessageKey } from "../lib/i18n";
import { SelectField, TextField } from "./ui";

interface PlaceFieldsProps {
  district: string;
  block: string;
  onDistrict: (id: string) => void;
  onBlock: (value: string) => void;
  districtError?: MessageKey | null;
  blockError?: MessageKey | null;
}

/** District from a list of Maharashtra's 36, and the taluka as typed text. No street address is collected. */
export function PlaceFields({ district, block, onDistrict, onBlock, districtError, blockError }: PlaceFieldsProps) {
  const { lang, t } = useLang();
  const [districts, setDistricts] = useState<District[]>([]);

  useEffect(() => {
    const controller = new AbortController();
    getDistricts()
      .then((res) => setDistricts(res.districts))
      .catch(() => undefined); // the select stays empty; submitting is blocked by validation
    return () => controller.abort();
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <SelectField
        label={t("place.district.label")}
        value={district}
        onChange={(e) => onDistrict(e.target.value)}
        error={districtError ? t(districtError) : null}
      >
        <option value="">{t("place.district.choose")}</option>
        {districts.map((d) => (
          <option key={d.id} value={d.id}>
            {d[lang]}
          </option>
        ))}
      </SelectField>
      <TextField
        label={t("place.block.label")}
        help={t("place.block.help")}
        value={block}
        maxLength={80}
        autoComplete="off"
        onChange={(e) => onBlock(e.target.value)}
        error={blockError ? t(blockError) : null}
      />
    </div>
  );
}
