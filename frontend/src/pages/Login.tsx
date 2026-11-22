import { useEffect, useState, type FormEvent } from "react";
import { AuthLayout, StepFrame } from "../components/AuthLayout";
import { Button, Notice, TextField } from "../components/ui";
import { isApiFailure, requestOtp, verifyOtp } from "../lib/api";
import { errorKey } from "../lib/errors";
import { useLang, type MessageKey } from "../lib/i18n";
import { cleanPhone, formatPhone, isValidPhone, maskPhone } from "../lib/phone";
import { useSession } from "../lib/session";

function useNow(active: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [active]);
  return now;
}

export function LoginPage() {
  const { t } = useLang();
  const { signIn } = useSession();
  const [stage, setStage] = useState<"phone" | "code">("phone");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<MessageKey | null>(null);
  const [busy, setBusy] = useState(false);
  const [resendAt, setResendAt] = useState(0);
  const now = useNow(stage === "code");
  const secondsLeft = Math.max(0, Math.ceil((resendAt - now) / 1000));

  const sendCode = async (e?: FormEvent) => {
    e?.preventDefault();
    if (!isValidPhone(phone)) {
      setError("val.phone");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await requestOtp(phone);
      setResendAt(Date.now() + res.resend_after * 1000);
      setCode("");
      setStage("code");
    } catch (err) {
      if (isApiFailure(err) && err.code === "otp_cooldown") {
        // A code was sent a moment ago: carry on to entering it.
        setResendAt(Date.now() + Number(err.extra.retry_after ?? 30) * 1000);
        setStage("code");
      } else {
        setError(errorKey(err));
      }
    } finally {
      setBusy(false);
    }
  };

  const verify = async (e: FormEvent) => {
    e.preventDefault();
    if (code.length !== 6) {
      setError("val.code");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await signIn(await verifyOtp(phone, code));
    } catch (err) {
      setError(errorKey(err));
      setBusy(false);
    }
  };

  if (stage === "phone") {
    return (
      <AuthLayout>
        <StepFrame title={t("login.phone.title")} help={t("login.phone.help")} key="phone">
          <form onSubmit={sendCode} className="flex flex-col gap-6" noValidate>
            <TextField
              label={t("login.phone.label")}
              prefix="+91"
              value={formatPhone(phone)}
              onChange={(e) => {
                setPhone(cleanPhone(e.target.value));
                setError(null);
              }}
              inputMode="numeric"
              autoComplete="tel-national"
              placeholder="98765 43210"
              maxLength={12}
              autoFocus
              error={error && error.startsWith("val.") ? t(error) : null}
            />
            {error && !error.startsWith("val.") && <Notice>{t(error)}</Notice>}
            <Button type="submit" loading={busy}>
              {t("login.phone.send")}
            </Button>
          </form>
        </StepFrame>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout>
      <StepFrame
        key="code"
        title={t("login.code.title")}
        help={t("login.code.help", { phone: maskPhone(phone) })}
        onBack={() => {
          setStage("phone");
          setError(null);
        }}
      >
        <form onSubmit={verify} className="flex flex-col gap-6" noValidate>
          <TextField
            label={t("login.code.label")}
            value={code}
            onChange={(e) => {
              setCode(e.target.value.replace(/\D/g, "").slice(0, 6));
              setError(null);
            }}
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            autoFocus
            className="tabular text-center text-[28px] font-semibold tracking-[0.5em]"
            error={error && error.startsWith("val.") ? t(error) : null}
          />
          {error && !error.startsWith("val.") && <Notice>{t(error)}</Notice>}
          <Button type="submit" loading={busy}>
            {t("login.code.verify")}
          </Button>
          <Button type="button" variant="ghost" disabled={secondsLeft > 0 || busy} onClick={() => void sendCode()}>
            {secondsLeft > 0 ? t("login.code.resendIn", { seconds: secondsLeft }) : t("login.code.resend")}
          </Button>
        </form>
      </StepFrame>
    </AuthLayout>
  );
}
