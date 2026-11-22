import { useState, type FormEvent } from "react";
import { Briefcase, GraduationCap, Hammer, Users } from "lucide-react";
import { AuthLayout, StepFrame } from "../components/AuthLayout";
import { PlaceFields } from "../components/PlaceFields";
import { Button, Choice, Notice, Pill, TextField } from "../components/ui";
import { createTeacher, isApiFailure, type TeacherRole } from "../lib/api";
import { errorKey } from "../lib/errors";
import { LANGS, type Lang, type MessageKey, useLang } from "../lib/i18n";
import { homePath } from "../lib/routes";
import { navigate } from "../lib/router";
import { useSession } from "../lib/session";

const ROLES: { id: TeacherRole; icon: typeof Users }[] = [
  { id: "teacher", icon: GraduationCap },
  { id: "mentor", icon: Briefcase },
  { id: "facilitator", icon: Users },
  { id: "expert", icon: Hammer },
];
const HOUR_PRESETS = [2, 5, 10, 20];
const TOTAL = 4;
type Step = 0 | 1 | 2 | 3;

function toggle<T>(list: T[], item: T): T[] {
  return list.includes(item) ? list.filter((x) => x !== item) : [...list, item];
}

/** Name, how they help, languages and hours, then place. Skills are claimed later, at the skill check. */
export function TeacherProfilePage() {
  const { t, lang } = useLang();
  const { reload } = useSession();
  const [step, setStep] = useState<Step>(0);
  const [name, setName] = useState("");
  const [roles, setRoles] = useState<TeacherRole[]>([]);
  const [languages, setLanguages] = useState<Lang[]>([lang]);
  const [hours, setHours] = useState("5");
  const [district, setDistrict] = useState("");
  const [block, setBlock] = useState("");
  const [error, setError] = useState<MessageKey | null>(null);
  const [busy, setBusy] = useState(false);

  const go = (next: Step) => {
    setError(null);
    setStep(next);
  };

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await createTeacher({ name: name.trim(), roles, languages, district, block: block.trim(), weekly_hours: Number(hours) });
      await reload();
      navigate(homePath("teacher"), { replace: true });
    } catch (err) {
      if (isApiFailure(err) && err.code === "profile_exists") {
        await reload();
        navigate(homePath("teacher"), { replace: true });
        return;
      }
      setError(errorKey(err));
      setBusy(false);
    }
  };

  const next = async (e: FormEvent) => {
    e.preventDefault();
    if (step === 0) return name.trim() ? go(1) : setError("val.name");
    if (step === 1) return roles.length ? go(2) : setError("val.roles");
    if (step === 2) {
      const h = Number(hours);
      if (!languages.length) return setError("val.languages");
      if (!Number.isInteger(h) || h < 1 || h > 60) return setError("val.hours");
      return go(3);
    }
    if (!district) return setError("val.district");
    if (!block.trim()) return setError("val.block");
    return submit();
  };

  const titles: Record<Step, MessageKey> = {
    0: "teacher.name.title",
    1: "teacher.roles.title",
    2: "teacher.hours.title",
    3: "teacher.place.title",
  };
  const fieldError = (key: MessageKey) => (error === key ? error : null);

  return (
    <AuthLayout>
      <StepFrame
        key={step}
        title={t(titles[step])}
        help={step === 1 ? t("teacher.roles.help") : undefined}
        step={{ current: step + 1, total: TOTAL }}
        onBack={step > 0 ? () => go((step - 1) as Step) : undefined}
      >
        <form onSubmit={next} className="flex flex-col gap-6" noValidate>
          {step === 0 && (
            <TextField
              label={t("teacher.name.label")}
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                setError(null);
              }}
              maxLength={80}
              autoComplete="given-name"
              autoFocus
              error={fieldError("val.name") ? t("val.name") : null}
            />
          )}

          {step === 1 && (
            <div className="flex flex-col gap-3">
              {ROLES.map(({ id, icon: Icon }) => (
                <Choice
                  key={id}
                  type="checkbox"
                  selected={roles.includes(id)}
                  onSelect={() => {
                    setRoles(toggle(roles, id));
                    setError(null);
                  }}
                  icon={<Icon className="size-5" />}
                  title={t(`teacherRole.${id}` as MessageKey)}
                  description={t(`teacherRole.${id}.help` as MessageKey)}
                  compact
                />
              ))}
              {error === "val.roles" && <p role="alert" className="text-[15px] font-medium text-bad">{t("val.roles")}</p>}
            </div>
          )}

          {step === 2 && (
            <>
              <div role="group" aria-label={t("teacher.languages.label")} className="flex flex-col gap-2">
                <span className="text-base font-semibold text-ink">{t("teacher.languages.label")}</span>
                <div className="flex flex-wrap gap-2.5">
                  {LANGS.map((l) => (
                    <button
                      key={l.code}
                      type="button"
                      lang={l.code}
                      role="checkbox"
                      aria-checked={languages.includes(l.code)}
                      onClick={() => {
                        setLanguages(toggle(languages, l.code));
                        setError(null);
                      }}
                      className={
                        "min-h-12 rounded-xl border-[1.5px] px-5 text-base font-semibold transition-colors " +
                        (languages.includes(l.code)
                          ? "border-accent bg-accent text-white"
                          : "border-line-strong bg-surface text-ink hover:border-accent")
                      }
                    >
                      {l.label}
                    </button>
                  ))}
                </div>
                {error === "val.languages" && <p role="alert" className="text-[15px] font-medium text-bad">{t("val.languages")}</p>}
              </div>
              <div className="flex flex-col gap-3">
                <TextField
                  label={`${t("teacher.hours.label")} (${t("teacher.hours.unit")})`}
                  value={hours}
                  onChange={(e) => {
                    setHours(e.target.value.replace(/\D/g, "").slice(0, 2));
                    setError(null);
                  }}
                  inputMode="numeric"
                  maxLength={2}
                  className="max-w-40"
                  error={fieldError("val.hours") ? t("val.hours") : null}
                />
                <div role="radiogroup" className="flex flex-wrap gap-2.5">
                  {HOUR_PRESETS.map((h) => (
                    <Pill key={h} selected={hours === String(h)} onSelect={() => setHours(String(h))}>
                      {h}
                    </Pill>
                  ))}
                </div>
              </div>
            </>
          )}

          {step === 3 && (
            <PlaceFields
              district={district}
              block={block}
              onDistrict={(v) => {
                setDistrict(v);
                setError(null);
              }}
              onBlock={(v) => {
                setBlock(v);
                setError(null);
              }}
              districtError={fieldError("val.district")}
              blockError={fieldError("val.block")}
            />
          )}

          {error && !error.startsWith("val.") && <Notice>{t(error)}</Notice>}
          <Button type="submit" loading={busy}>
            {step === 3 ? t("teacher.finish") : t("common.next")}
          </Button>
        </form>
      </StepFrame>
    </AuthLayout>
  );
}
