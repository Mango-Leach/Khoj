import { useEffect, useState, type ReactNode } from "react";
import { BadgeCheck, Bell, Briefcase, ClipboardList, Compass, FileCheck2, GraduationCap, Handshake, Home, LogOut, Menu, UserPlus, Users, Video, Wallet, type LucideIcon } from "lucide-react";
import { useLang, type MessageKey } from "../lib/i18n";
import { usePath } from "../lib/router";
import { useSession } from "../lib/session";
import { useUnread } from "../lib/unread";
import { ConnectionBadge } from "./ConnectionBadge";
import { LanguageSwitch } from "./LanguageSwitch";
import { Link } from "./Link";
import { Button, Logo, cx } from "./ui";

export interface NavItem {
  path: string;
  label: MessageKey;
  icon: LucideIcon;
}

export const STUDENT_NAV: NavItem[] = [
  { path: "/home", label: "nav.home", icon: Home },
  { path: "/paths", label: "nav.paths", icon: Compass },
  { path: "/mentor", label: "nav.mentor", icon: Users },
  { path: "/assignments", label: "nav.assignments", icon: ClipboardList },
  { path: "/calls", label: "nav.calls", icon: Video },
  { path: "/connect", label: "nav.connect", icon: Handshake },
  { path: "/opportunities", label: "nav.opportunities", icon: Briefcase },
  { path: "/scholarships", label: "nav.scholarships", icon: GraduationCap },
];

export const TEACHER_NAV: NavItem[] = [
  { path: "/t/home", label: "nav.home", icon: Home },
  { path: "/t/assess", label: "nav.assess", icon: BadgeCheck },
  { path: "/t/requests", label: "nav.requests", icon: UserPlus },
  { path: "/t/students", label: "nav.students", icon: Users },
  { path: "/t/assignments", label: "nav.assignments", icon: ClipboardList },
  { path: "/t/review", label: "nav.review", icon: FileCheck2 },
  { path: "/t/calls", label: "nav.calls", icon: Video },
  { path: "/t/earnings", label: "nav.earnings", icon: Wallet },
];

export function AppShell({ items, children }: { items: NavItem[]; children: ReactNode }) {
  const { t } = useLang();
  const path = usePath();
  const { profile, signOut } = useSession();
  const name = profile?.data.name ?? "";
  const inbox = profile?.kind === "teacher" ? "/t/inbox" : "/inbox";
  const unread = useUnread(path);
  // On a phone the menu is a slide-in panel. From 768 px up it is the fixed sidebar.
  const [open, setOpen] = useState(false);
  useEffect(() => setOpen(false), [path]);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <div className="grid min-h-dvh grid-cols-1 md:grid-cols-[264px_minmax(0,1fr)]">
      {open && <div className="fixed inset-0 z-30 bg-ink/40 md:hidden" onClick={() => setOpen(false)} aria-hidden="true" />}
      <nav
        id="main-nav"
        aria-label={t("nav.main")}
        className={cx(
          "fixed inset-y-0 left-0 z-40 flex h-dvh w-[280px] max-w-[85vw] flex-col gap-1 overflow-y-auto border-r border-line bg-surface p-4 transition-transform",
          "md:sticky md:top-0 md:z-auto md:w-auto md:max-w-none md:translate-x-0 md:visible",
          open ? "translate-x-0" : "invisible -translate-x-full",
        )}
      >
        <div className="px-2.5 pt-1 pb-6">
          <Link to="/" aria-label={t("nav.landing")} className="inline-flex rounded-lg">
            <Logo />
          </Link>
        </div>
        {items.map(({ path: to, label, icon: Icon }) => {
          const active = path === to || path.startsWith(`${to}/`); // a page inside a section keeps the section lit
          return (
            <Link
              key={to}
              to={to}
              aria-current={active ? "page" : undefined}
              className={cx(
                "flex h-[54px] items-center gap-3.5 rounded-xl px-3.5 text-[17px] font-semibold transition-colors",
                active ? "bg-tint text-accent" : "text-muted hover:bg-bg hover:text-ink",
              )}
            >
              <Icon className="size-[22px] shrink-0" aria-hidden="true" />
              {t(label)}
            </Link>
          );
        })}

        <div className="mt-auto flex flex-col gap-3 border-t border-line pt-4">
          <div className="flex items-center gap-3 px-1.5">
            <span className="grid size-11 shrink-0 place-items-center rounded-full bg-deep text-lg font-bold text-white" aria-hidden="true">
              {name.trim().charAt(0).toUpperCase()}
            </span>
            <span className="min-w-0 truncate text-base font-semibold text-ink">{name}</span>
          </div>
          <div className="flex flex-col gap-2">
            <Button variant="secondary" full onClick={() => void signOut()} icon={<LogOut className="size-[18px]" />} className="h-11 px-3 text-[15px]">
              {t("nav.signOut")}
            </Button>
          </div>
        </div>
      </nav>

      <div className="flex min-w-0 flex-col">
        <header className="flex h-[76px] items-center gap-2 px-4 sm:gap-3 md:px-11">
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-controls="main-nav"
            aria-label={t("nav.menu")}
            className="grid size-11 shrink-0 place-items-center rounded-xl border-[1.5px] border-line-strong bg-surface text-ink md:hidden"
          >
            <Menu className="size-6" aria-hidden="true" />
          </button>
          <div className="ml-auto flex items-center gap-2 sm:gap-3">
            <ConnectionBadge />
            <Link
              to={inbox}
              aria-label={unread > 0 ? `${t("nav.inbox")}, ${t("inbox.unreadCount", { n: unread })}` : t("nav.inbox")}
              aria-current={path === inbox ? "page" : undefined}
              className={cx(
                "relative grid size-11 shrink-0 place-items-center rounded-xl border-[1.5px] bg-surface transition-colors",
                path === inbox ? "border-accent text-accent" : "border-line-strong text-ink hover:border-accent hover:text-accent",
              )}
            >
              <Bell className="size-5" aria-hidden="true" />
              {unread > 0 && (
                <span className="absolute -top-1.5 -right-1.5 grid min-w-5 place-items-center rounded-full bg-accent px-1 text-xs font-bold text-white" aria-hidden="true">
                  {unread > 9 ? "9+" : unread}
                </span>
              )}
            </Link>
            <LanguageSwitch />
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1480px] px-4 pb-14 md:px-11">{children}</main>
      </div>
    </div>
  );
}
