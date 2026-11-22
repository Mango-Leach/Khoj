import { Suspense, lazy, useEffect, type ComponentType, type ReactNode } from "react";
import { Loader2 } from "lucide-react";
import { AppShell, STUDENT_NAV, TEACHER_NAV } from "./components/AppShell";
import { StatusPanel } from "./components/StatusPanel";
import { Button, Logo, Notice } from "./components/ui";
import { useLang } from "./lib/i18n";
import { navigate, usePath } from "./lib/router";
import { homePath, landingPath } from "./lib/routes";
import { SessionProvider, useSession } from "./lib/session";
import { AssignmentPage } from "./pages/Assignment";
import { AssignmentsPage } from "./pages/Assignments";
import { NotReady, StudentHome, TeacherHome } from "./pages/Home";
import { IntakePage } from "./pages/Intake";
import { InboxPage } from "./pages/Inbox";
import { IntakeReviewPage } from "./pages/IntakeReview";
import { JobPackPage } from "./pages/JobPack";
import { LoginPage } from "./pages/Login";
import { MentorPage } from "./pages/Mentor";
import { OpportunitiesPage } from "./pages/Opportunities";
import { PathDetailPage, PathsPage } from "./pages/Paths";
import { ScholarshipsPage } from "./pages/Scholarships";
import { LandingPage } from "./pages/landing/Landing";
import { RolePage } from "./pages/Role";
import { SkillsPage } from "./pages/Skills";
import { StudentProfilePage } from "./pages/StudentProfile";

function PageLoading() {
  return (
    <div className="flex items-center gap-3 pt-2 text-lg text-muted" role="status">
      <Loader2 className="size-6 animate-spin text-accent" aria-hidden="true" />
    </div>
  );
}

/** A page loaded the first time it is opened, so a learner's phone never downloads the mentor's screens. */
function lazyPage(load: () => Promise<{ default: ComponentType }>): ComponentType {
  const Page = lazy(load);
  return function LazyPage() {
    return (
      <Suspense fallback={<PageLoading />}>
        <Page />
      </Suspense>
    );
  };
}

const CallsPage = lazyPage(() => import("./pages/Calls").then((m) => ({ default: m.CallsPage })));
const ConnectPage = lazyPage(() => import("./pages/Connect").then((m) => ({ default: m.ConnectPage })));
const TeacherAssessPage = lazyPage(() => import("./pages/TeacherAssess").then((m) => ({ default: m.TeacherAssessPage })));
const TeacherAssignmentsPage = lazyPage(() => import("./pages/TeacherAssignments").then((m) => ({ default: m.TeacherAssignmentsPage })));
const TeacherCallsPage = lazyPage(() => import("./pages/TeacherCalls").then((m) => ({ default: m.TeacherCallsPage })));
const TeacherProfilePage = lazyPage(() => import("./pages/TeacherProfile").then((m) => ({ default: m.TeacherProfilePage })));
const TeacherRequestsPage = lazyPage(() => import("./pages/TeacherRequests").then((m) => ({ default: m.TeacherRequestsPage })));
const TeacherReviewPage = lazyPage(() => import("./pages/TeacherReview").then((m) => ({ default: m.TeacherReviewPage })));
const TeacherStudentsPage = lazyPage(() => import("./pages/TeacherStudents").then((m) => ({ default: m.TeacherStudentsPage })));

// Screens that later milestones build; until then they show a plain "not ready yet" page.
const TEACHER_PLACEHOLDERS = ["/t/earnings"];
const SETUP_PATHS = ["/role", "/profile/student", "/profile/teacher"];

function Centered({ children }: { children: ReactNode }) {
  return <div className="grid min-h-dvh place-items-center bg-bg p-8">{children}</div>;
}

function Splash() {
  return (
    <Centered>
      <div className="flex flex-col items-center gap-6" role="status">
        <Logo />
        <Loader2 className="size-6 animate-spin text-accent" aria-hidden="true" />
      </div>
    </Centered>
  );
}

function Unavailable({ onRetry }: { onRetry: () => void }) {
  const { t } = useLang();
  return (
    <Centered>
      <div className="flex w-full max-w-sm flex-col gap-5">
        <Logo />
        <Notice>{t("err.network")}</Notice>
        <Button onClick={onRetry}>{t("status.retry")}</Button>
      </div>
    </Centered>
  );
}

/** Decides what to show, and where a visitor must be sent instead. Returns a redirect target or a page. */
function useRoute(): { redirect: string | null; page: ReactNode } {
  const path = usePath();
  const { status, user, profile, retry } = useSession();

  if (path === "/status") {
    return { redirect: null, page: <main className="mx-auto max-w-md p-8"><StatusPanel /></main> };
  }
  if (status === "loading") return { redirect: null, page: <Splash /> };
  if (status === "unavailable") return { redirect: null, page: <Unavailable onRetry={retry} /> };
  if (status === "anonymous" || !user) {
    if (path === "/") return { redirect: null, page: <LandingPage /> };
    return path === "/login" ? { redirect: null, page: <LoginPage /> } : { redirect: "/login", page: null };
  }

  // The logo leads here: a signed-in visitor can read the landing page and stays signed in.
  if (path === "/") return { redirect: null, page: <LandingPage /> };

  if (!user.profile) {
    if (path === "/role") return { redirect: null, page: <RolePage /> };
    if (path === "/profile/student") return { redirect: null, page: <StudentProfilePage /> };
    if (path === "/profile/teacher") return { redirect: null, page: <TeacherProfilePage /> };
    return { redirect: "/role", page: null };
  }
  if (path === "/login" || SETUP_PATHS.includes(path)) return { redirect: landingPath(user), page: null };

  if (!profile) return { redirect: null, page: <Splash /> };

  if (profile.kind === "student") {
    if (path === "/home") return { redirect: null, page: <AppShell items={STUDENT_NAV}><StudentHome /></AppShell> };
    if (path === "/skills") return { redirect: null, page: <AppShell items={STUDENT_NAV}><SkillsPage /></AppShell> };
    if (path === "/intake") return { redirect: null, page: <AppShell items={STUDENT_NAV}><IntakePage /></AppShell> };
    if (path === "/intake/review") return { redirect: null, page: <AppShell items={STUDENT_NAV}><IntakeReviewPage /></AppShell> };
    if (path === "/paths") return { redirect: null, page: <AppShell items={STUDENT_NAV}><PathsPage /></AppShell> };
    if (path.startsWith("/paths/") && path.length > 7) {
      return { redirect: null, page: <AppShell items={STUDENT_NAV}><PathDetailPage careerId={decodeURIComponent(path.slice(7))} /></AppShell> };
    }
    if (path === "/mentor") return { redirect: null, page: <AppShell items={STUDENT_NAV}><MentorPage /></AppShell> };
    if (path === "/scholarships") return { redirect: null, page: <AppShell items={STUDENT_NAV}><ScholarshipsPage /></AppShell> };
    if (path === "/assignments") return { redirect: null, page: <AppShell items={STUDENT_NAV}><AssignmentsPage /></AppShell> };
    if (path.startsWith("/assignments/") && path.length > 13) {
      return { redirect: null, page: <AppShell items={STUDENT_NAV}><AssignmentPage assignmentId={decodeURIComponent(path.slice(13))} /></AppShell> };
    }
    if (path === "/calls") return { redirect: null, page: <AppShell items={STUDENT_NAV}><CallsPage /></AppShell> };
    if (path === "/connect") return { redirect: null, page: <AppShell items={STUDENT_NAV}><ConnectPage /></AppShell> };
    if (path === "/opportunities") return { redirect: null, page: <AppShell items={STUDENT_NAV}><OpportunitiesPage /></AppShell> };
    if (path === "/inbox") return { redirect: null, page: <AppShell items={STUDENT_NAV}><InboxPage /></AppShell> };
    if (path === "/pack") return { redirect: null, page: <AppShell items={STUDENT_NAV}><JobPackPage /></AppShell> };
    if (path.startsWith("/pack/") && path.length > 6) {
      return { redirect: null, page: <AppShell items={STUDENT_NAV}><JobPackPage careerId={decodeURIComponent(path.slice(6))} /></AppShell> };
    }
  } else {
    if (path === "/t/home") return { redirect: null, page: <AppShell items={TEACHER_NAV}><TeacherHome /></AppShell> };
    if (path === "/t/assess") return { redirect: null, page: <AppShell items={TEACHER_NAV}><TeacherAssessPage /></AppShell> };
    if (path === "/t/requests") return { redirect: null, page: <AppShell items={TEACHER_NAV}><TeacherRequestsPage /></AppShell> };
    if (path === "/t/students") return { redirect: null, page: <AppShell items={TEACHER_NAV}><TeacherStudentsPage /></AppShell> };
    if (path === "/t/assignments") return { redirect: null, page: <AppShell items={TEACHER_NAV}><TeacherAssignmentsPage /></AppShell> };
    if (path === "/t/review") return { redirect: null, page: <AppShell items={TEACHER_NAV}><TeacherReviewPage /></AppShell> };
    if (path === "/t/calls") return { redirect: null, page: <AppShell items={TEACHER_NAV}><TeacherCallsPage /></AppShell> };
    if (path === "/t/inbox") return { redirect: null, page: <AppShell items={TEACHER_NAV}><InboxPage /></AppShell> };
    if (TEACHER_PLACEHOLDERS.includes(path)) {
      return { redirect: null, page: <AppShell items={TEACHER_NAV}><NotReady home="/t/home" /></AppShell> };
    }
  }
  return { redirect: homePath(profile.kind), page: null };
}

function Router() {
  const { redirect, page } = useRoute();

  useEffect(() => {
    if (redirect) navigate(redirect, { replace: true });
  }, [redirect]);

  return <>{page}</>;
}

export default function App() {
  return (
    <SessionProvider>
      <Router />
    </SessionProvider>
  );
}
