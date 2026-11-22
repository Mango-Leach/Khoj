import { useState, type FormEvent } from "react";
import { AuthLayout, StepFrame } from "../components/AuthLayout";
import { PlaceFields } from "../components/PlaceFields";
import { Button, Choice, Notice, Pill, TextField } from "../components/ui";
import { createStudent, isApiFailure } from "../lib/api";
import { errorKey } from "../lib/errors";
import { useLang, type MessageKey } from "../lib/i18n";
import { homePath } from "../lib/routes";
import { navigate } from "../lib/router";
import { useSession } from "../lib/session";

const GRADES = [9, 10, 11, 12, 13, 14] as const;
type Step = 0 | 1 | 2 | 3;

/** Name, then age and class, then place; a guardian's consent is asked only under 18. */
export function StudentProfilePage() {
  const { t } = useLang();
  const { reload } = useSession();
  const [step, setStep] = useState<Step>(0);
  const [name, setName] = useState("");
  const [age, setAge] = useState("");
  const [grade, setGrade] = useState<number | null>(null);
  const [district, setDistrict] = useState("");
  const [block, setBlock] = useState("");
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState<MessageKey | null>(null);
  const [busy, setBusy] = useState(false);

  const ageNum = Number(age);
  const ageOk = Number.isInteger(ageNum) && ageNum >= 10 && ageNum <= 40;
  const adult = ageOk && ageNum >= 18;
  const minor = ageOk && !adult;
  // Most learners are under 18, so the guardian step is counted until an adult age is entered.
  const total = adult ? 3 : 4;

  const go = (next: Step) => {
    setError(null);
    setStep(next);
  };

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await createStudent({ name: name.trim(), age: ageNum, grade: grade as number, district, block: block.trim(), guardian_consent: consent });
      await reload();
      navigate(homePath("student"), { replace: true });
    } catch (err) {
      if (isApiFailure(err) && err.code === "profile_exists") {
        await reload();
        navigate(homePath("student"), { replace: true });
        return;
      }
      setError(errorKey(err));
      setBusy(false);
    }
  };

  const next = async (e: FormEvent) => {
    e.preventDefault();
    if (step === 0) {
      if (!name.trim()) return setError("val.name");
      return go(1);
    }
    if (step === 1) {
      if (!ageOk) return setError("val.age");
      if (grade === null) return setError("val.grade");
      return go(2);
    }
    if (step === 2) {
      if (!district) return setError("val.district");
      if (!block.trim()) return setError("val.block");
      return minor ? go(3) : submit();
    }
    if (!consent) return setError("val.consent");
    return submit();
  };

  const last = step === total - 1;
  const fieldError = (keys: MessageKey[]) => (error && keys.includes(error) ? error : null);
  const titles: Record<Step, MessageKey> = {
    0: "student.name.title",
    1: "student.age.title",
    2: "student.place.title",
    3: "student.consent.title",
  };

  return (
    <AuthLayout>
      <StepFrame
        key={step}
        title={t(titles[step])}
        help={step === 3 ? t("student.consent.help") : undefined}
        step={{ current: step + 1, total }}
        onBack={step > 0 ? () => go((step - 1) as Step) : undefined}
      >
        <form onSubmit={next} className="flex flex-col gap-6" noValidate>
          {step === 0 && (
            <TextField
              label={t("student.name.label")}
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                setError(null);
              }}
              maxLength={80}
              autoComplete="given-name"
              autoFocus
              error={fieldError(["val.name"]) ? t("val.name") : null}
            />
          )}

          {step === 1 && (
            <>
              <TextField
                label={t("student.age.label")}
                value={age}
                onChange={(e) => {
                  setAge(e.target.value.replace(/\D/g, "").slice(0, 2));
                  setError(null);
                }}
                inputMode="numeric"
                maxLength={2}
                autoFocus
                className="max-w-40"
                error={fieldError(["val.age"]) ? t("val.age") : null}
              />
              <div role="radiogroup" aria-label={t("student.grade.label")} className="flex flex-col gap-2">
                <span className="text-base font-semibold text-ink">{t("student.grade.label")}</span>
                <div className="flex flex-wrap gap-2.5">
                  {GRADES.map((g) => (
                    <Pill
                      key={g}
                      selected={grade === g}
                      onSelect={() => {
                        setGrade(g);
                        setError(null);
                      }}
                    >
                      {t(`grade.${g}` as MessageKey)}
                    </Pill>
                  ))}
                </div>
                {error === "val.grade" && <p role="alert" className="text-[15px] font-medium text-bad">{t("val.grade")}</p>}
              </div>
            </>
          )}

          {step === 2 && (
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
              districtError={fieldError(["val.district"])}
              blockError={fieldError(["val.block"])}
            />
          )}

          {step === 3 && (
            <Choice
              type="checkbox"
              selected={consent}
              onSelect={() => {
                setConsent(!consent);
                setError(null);
              }}
              title={t("student.consent.yes")}
            />
          )}

          {error && !error.startsWith("val.") && <Notice>{t(error)}</Notice>}
          {error === "val.consent" && <Notice>{t("val.consent")}</Notice>}
          <Button type="submit" loading={busy}>
            {last ? t("student.finish") : t("common.next")}
          </Button>
        </form>
      </StepFrame>
    </AuthLayout>
  );
}
