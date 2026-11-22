import { useEffect, useState } from "react";
import { Loader2, X } from "lucide-react";
import { fetchWorkPhoto } from "../lib/api";
import { useLang } from "../lib/i18n";

/** A photo of a learner's work. The bytes need the sign-in header, so they are fetched and shown from a local URL. */
export function WorkPhoto({ submissionId, photoId, onRemove, size = "small" }: { submissionId: string; photoId: string; onRemove?: () => void; size?: "small" | "large" }) {
  const { t } = useLang();
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    let url: string | null = null;
    let alive = true;
    fetchWorkPhoto(submissionId, photoId)
      .then((blob) => {
        if (!alive) return;
        url = URL.createObjectURL(blob);
        setSrc(url);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [submissionId, photoId]);

  return (
    <li className={size === "large" ? "w-full max-w-[360px]" : "w-[132px]"}>
      <div className="relative aspect-[4/3] overflow-hidden rounded-xl bg-bg ring-1 ring-line">
        {src ? (
          size === "large" ? (
            <a href={src} target="_blank" rel="noreferrer" className="block size-full">
              <img src={src} alt="" className="size-full object-cover" />
            </a>
          ) : (
            <img src={src} alt="" className="size-full object-cover" />
          )
        ) : (
          <Loader2 className="absolute inset-0 m-auto size-5 animate-spin text-muted" aria-hidden="true" />
        )}
        {onRemove && (
          <button
            type="button"
            onClick={onRemove}
            aria-label={t("assess.photo.remove")}
            title={t("assess.photo.remove")}
            className="absolute top-1 right-1 grid size-8 place-items-center rounded-full bg-ink/70 text-white hover:bg-ink"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        )}
      </div>
    </li>
  );
}
