import { GraduationCap, UsersRound } from "lucide-react";
import { AuthLayout, StepFrame } from "../components/AuthLayout";
import { Choice } from "../components/ui";
import { useLang } from "../lib/i18n";
import { navigate } from "../lib/router";

/** The first sign-in picks a role. One tap goes straight to that role's profile. */
export function RolePage() {
  const { t } = useLang();
  return (
    <AuthLayout>
      <StepFrame title={t("role.title")} help={t("role.help")}>
        <div className="flex flex-col gap-3.5">
          <Choice
            type="action"
            selected={false}
            icon={<GraduationCap className="size-6" />}
            title={t("role.student")}
            description={t("role.student.help")}
            onSelect={() => navigate("/profile/student")}
          />
          <Choice
            type="action"
            selected={false}
            icon={<UsersRound className="size-6" />}
            title={t("role.teacher")}
            description={t("role.teacher.help")}
            onSelect={() => navigate("/profile/teacher")}
          />
        </div>
      </StepFrame>
    </AuthLayout>
  );
}
