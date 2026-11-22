import { useEffect, useState } from "react";
import { PageBanner } from "../components/PageBanner";
import {
  Check,
  Clapperboard,
  CircleHelp,
  CookingPot,
  HeartHandshake,
  Landmark,
  Scissors,
  Sprout,
  Store,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import { ListenButton } from "../components/ListenButton";
import { Button, Notice, cx } from "../components/ui";
import { getCategories, startIntake, type Category } from "../lib/api";
import { errorKey } from "../lib/errors";
import { useLang } from "../lib/i18n";
import { navigate } from "../lib/router";
import { useLatestIntake } from "../lib/useIntake";

const ICONS: Record<string, LucideIcon> = {
  scissors: Scissors,
  sprout: Sprout,
  wrench: Wrench,
  "cooking-pot": CookingPot,
  store: Store,
  "heart-handshake": HeartHandshake,
  clapperboard: Clapperboard,
  landmark: Landmark,
};

const MAX_PICKS = 3;

function Tile({ category, selected, onToggle }: { category: Category; selected: boolean; onToggle: () => void }) {
  const { lang } = useLang();
  const Icon = ICONS[category.icon] ?? CircleHelp;
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={selected}
      onClick={onToggle}
      className={cx(
        "relative flex min-h-40 flex-col items-center justify-center gap-3 rounded-2xl border-[1.5px] p-4 text-center transition-colors",
        selected ? "border-accent bg-tint" : "border-line bg-surface hover:border-line-strong",
      )}
    >
      <span
        className={cx("grid size-16 place-items-center rounded-2xl", selected ? "bg-accent text-white" : "bg-tint text-accent")}
        aria-hidden="true"
      >
        <Icon className="size-8" />
      </span>
      <span className="text-lg leading-snug font-semibold text-ink">{category.name[lang]}</span>
      {selected && (
        <span className="absolute top-3 right-3 grid size-7 place-items-center rounded-full bg-accent text-white" aria-hidden="true">
          <Check className="size-4" strokeWidth={3} />
        </span>
      )}
    </button>
  );
}

export function SkillsPage() {
  const { t, lang } = useLang();
  const latest = useLatestIntake();
  const [categories, setCategories] = useState<Category[]>([]);
  const [picked, setPicked] = useState<string[]>([]);
  const [notSure, setNotSure] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getCategories()
      .then((res) => setCategories(res.categories))
      .catch((err: unknown) => setLoadError(t(errorKey(err))));
    // the tile list does not depend on the language; names are picked per language when drawn
  }, []);

  const toggle = (id: string) => {
    setNotSure(false);
    setPicked((cur) => (cur.includes(id) ? cur.filter((c) => c !== id) : cur.length < MAX_PICKS ? [...cur, id] : cur));
  };

  const chooseNotSure = () => {
    setNotSure((v) => !v);
    setPicked([]);
  };

  const start = async () => {
    setStarting(true);
    setError(null);
    try {
      await startIntake({ category_ids: picked, not_sure: notSure, language: lang });
      navigate("/intake");
    } catch (err) {
      setError(t(errorKey(err)));
      setStarting(false);
    }
  };

  const unfinished = latest.state === "ready" && latest.session.status === "in_progress" && latest.session.answers.length > 0 ? latest.session : null;
  const ready = notSure || picked.length > 0;

  return (
    <div className="flex max-w-4xl flex-col gap-8 pt-2">
      <PageBanner title={t("skills.title")} lead={t("skills.lead")} aside={<ListenButton text={`${t("skills.title")} ${t("skills.lead")}`} />} />

      {unfinished && (
        <section className="flex items-center justify-between gap-6 rounded-[28px] border border-line bg-tint p-6" aria-label={t("skills.resume.title")}>
          <div className="flex flex-col gap-1">
            <h2 className="text-xl font-semibold">{t("skills.resume.title")}</h2>
            <p className="text-base text-muted">{t("skills.resume.help", { n: unfinished.answers.length, total: unfinished.total_questions })}</p>
          </div>
          <Button full={false} onClick={() => navigate("/intake")}>
            {t("skills.resume.cta")}
          </Button>
        </section>
      )}

      {loadError && <Notice>{loadError}</Notice>}

      <div role="group" aria-label={t("skills.title")} className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {categories.map((c) => (
          <Tile key={c.id} category={c} selected={picked.includes(c.id)} onToggle={() => toggle(c.id)} />
        ))}
      </div>

      <button
        type="button"
        role="checkbox"
        aria-checked={notSure}
        onClick={chooseNotSure}
        className={cx(
          "flex min-h-[72px] items-center gap-4 rounded-2xl border-[1.5px] px-5 py-3.5 text-left transition-colors",
          notSure ? "border-accent bg-tint" : "border-line bg-surface hover:border-line-strong",
        )}
      >
        <span className={cx("grid size-11 shrink-0 place-items-center rounded-xl", notSure ? "bg-accent text-white" : "bg-tint text-accent")} aria-hidden="true">
          <CircleHelp className="size-6" />
        </span>
        <span className="flex-1">
          <span className="block text-lg font-semibold">{t("skills.notSure")}</span>
          <span className="block text-[15px] text-muted">{t("skills.notSure.help")}</span>
        </span>
        {notSure && (
          <span className="grid size-7 place-items-center rounded-full bg-accent text-white" aria-hidden="true">
            <Check className="size-4" strokeWidth={3} />
          </span>
        )}
      </button>

      {error && <Notice>{error}</Notice>}

      <div className="flex items-center justify-between gap-6">
        <p className="text-base font-medium text-muted" aria-live="polite">
          {t("skills.picked", { n: picked.length })}
        </p>
        <Button full={false} disabled={!ready} loading={starting} onClick={start}>
          {t("skills.continue")}
        </Button>
      </div>
    </div>
  );
}
