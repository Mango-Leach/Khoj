import { ArrowUpRight } from "lucide-react";
import { LanguageSwitch } from "../../components/LanguageSwitch";
import { Link } from "../../components/Link";
import { Logo, cx } from "../../components/ui";
import { useLang, type MessageKey } from "../../lib/i18n";
import { entryPath } from "../../lib/routes";
import { useSession } from "../../lib/session";
import { useScrolled } from "./hooks";

const LINKS: { href: string; label: MessageKey }[] = [
  { href: "#how", label: "lp.nav.how" },
  { href: "#who", label: "lp.nav.who" },
  { href: "#trust", label: "lp.nav.trust" },
];

/**
 * Always-visible navigation: the language menu and the way in never scroll away. It sits clear
 * over the blue opening and turns white once the page moves.
 */
export function Nav() {
  const { t } = useLang();
  const scrolled = useScrolled();
  const { user } = useSession();
  const onBlue = !scrolled;
  return (
    <header
      className={cx(
        "fixed inset-x-0 top-0 z-50 transition-[background-color,border-color,box-shadow] duration-300",
        scrolled ? "border-b border-line bg-white/92 shadow-(--shadow-soft) backdrop-blur-md" : "border-b border-transparent bg-transparent",
      )}
    >
      <a
        href="#main"
        className="sr-only rounded-lg bg-night px-4 py-2 font-semibold text-white focus:not-sr-only focus:absolute focus:top-3 focus:left-3"
      >
        {t("lp.skip")}
      </a>
      <div className="mx-auto flex h-[68px] w-full max-w-[1840px] items-center gap-4 px-[clamp(20px,3vw,56px)] sm:gap-6 lg:h-[84px] lg:gap-8">
        <Link to="/" aria-label="KHOJ" className="shrink-0">
          <Logo inverse={onBlue} large />
        </Link>
        <nav aria-label={t("nav.main")} className="hidden flex-1 items-center gap-1.5 lg:flex">
          {LINKS.map(({ href, label }) => (
            <a
              key={href}
              href={href}
              className={cx(
                "rounded-full px-4 py-2 text-[17px] font-medium transition-colors",
                onBlue ? "text-white/80 hover:bg-white/10 hover:text-white" : "text-muted hover:bg-tint hover:text-accent",
              )}
            >
              {t(label)}
            </a>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-3 sm:gap-4">
          <LanguageSwitch tone={onBlue ? "dark" : "light"} />
          {!user && (
            <Link
              to="/login"
              className={cx(
                "hidden h-11 items-center rounded-full px-4 text-[17px] font-semibold transition-colors md:inline-flex",
                onBlue ? "text-white hover:bg-white/10" : "text-ink hover:bg-tint hover:text-accent",
              )}
            >
              {t("lp.nav.signin")}
            </Link>
          )}
          <Link
            to={entryPath(user)}
            className="group hidden h-11 items-center gap-3 rounded-full bg-night pr-1.5 pl-5 text-[16px] font-semibold text-white transition-colors hover:bg-black sm:inline-flex lg:h-12 lg:text-[17px]"
          >
            {user ? t("lp.nav.open") : t("lp.cta.start")}
            <span className="grid size-9 place-items-center rounded-full bg-lime text-night transition-transform group-hover:translate-x-0.5 lg:size-10" aria-hidden="true">
              <ArrowUpRight className="size-5" />
            </span>
          </Link>
        </div>
      </div>
    </header>
  );
}
