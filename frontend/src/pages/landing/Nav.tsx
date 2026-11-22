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
  { href: "#faq", label: "lp.nav.faq" },
];

/** Always-visible navigation: the language switch and the two ways in never scroll away. */
export function Nav() {
  const { t } = useLang();
  const scrolled = useScrolled();
  const { user } = useSession();
  return (
    <header
      className={cx(
        "fixed inset-x-0 top-0 z-50 transition-[background-color,border-color,box-shadow] duration-300",
        scrolled ? "border-b border-line bg-white/90 shadow-(--shadow-soft) backdrop-blur-md" : "border-b border-transparent bg-transparent",
      )}
    >
      <a
        href="#main"
        className="sr-only rounded-lg bg-ink px-4 py-2 font-semibold text-white focus:not-sr-only focus:absolute focus:top-3 focus:left-3"
      >
        {t("lp.skip")}
      </a>
      <div className="mx-auto flex h-[76px] w-full max-w-[1240px] items-center gap-6 px-8">
        <Link to="/" aria-label="KHOJ">
          <Logo />
        </Link>
        <nav aria-label={t("nav.main")} className="hidden flex-1 items-center gap-1 pl-4 lg:flex">
          {LINKS.map(({ href, label }) => (
            <a key={href} href={href} className="rounded-lg px-4 py-2 text-[17px] font-semibold text-muted transition-colors hover:bg-tint hover:text-accent">
              {t(label)}
            </a>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-3">
          <LanguageSwitch />
          {!user && (
            <Link
              to="/login"
              className="hidden h-11 items-center rounded-xl px-4 text-[17px] font-semibold text-ink transition-colors hover:bg-tint hover:text-accent md:inline-flex"
            >
              {t("lp.nav.signin")}
            </Link>
          )}
          <Link
            to={entryPath(user)}
            className="inline-flex h-11 items-center rounded-xl bg-accent px-5 text-[17px] font-semibold text-white transition-colors hover:bg-accent-hover"
          >
            {user ? t("lp.nav.open") : t("lp.cta.start")}
          </Link>
        </div>
      </div>
    </header>
  );
}
