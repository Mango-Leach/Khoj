import type { ReactNode } from "react";

/**
 * Illustrated people for the landing page. They are drawings, never photos, and they stand for
 * no real learner or mentor: the page that uses them says so in words.
 */

export type PersonName = "asha" | "arjun" | "ravi" | "kiran" | "meena" | "dev";
type Style = "long" | "short" | "bun" | "bob";

interface Look {
  skin: string;
  hair: string;
  shirt: string;
  style: Style;
  bindi?: boolean;
  mustache?: boolean;
  glasses?: boolean;
  dupatta?: string;
  /** Background colour behind the face in a round avatar. */
  tile: string;
}

const LOOKS: Record<PersonName, Look> = {
  asha: { skin: "#b87a4b", hair: "#1a1020", shirt: "#dcf53f", style: "long", bindi: true, tile: "#7d8be8" },
  arjun: { skin: "#c68642", hair: "#15101a", shirt: "#ff7a59", style: "short", tile: "#f5d3c8" },
  ravi: { skin: "#8d5524", hair: "#15101a", shirt: "#ffffff", style: "short", mustache: true, tile: "#dcf53f" },
  kiran: { skin: "#a9714b", hair: "#2a1a14", shirt: "#8be0b0", style: "bob", tile: "#ffd9a8" },
  meena: { skin: "#c68642", hair: "#2a1a14", shirt: "#f7c948", style: "bun", dupatta: "#e0507a", bindi: true, tile: "#c9b8f5" },
  dev: { skin: "#e0ac69", hair: "#1b1b22", shirt: "#7cc4ff", style: "short", glasses: true, tile: "#bfe7ff" },
};

const FRONT: Record<Style, string> = {
  long: "M56 108C50 30 150 30 144 108C138 88 120 78 100 78C80 78 62 88 56 108Z",
  short: "M57 102C52 34 148 34 143 102C138 82 124 72 100 72C76 72 62 82 57 102Z",
  bun: "M57 102C52 36 148 36 143 102C138 84 122 74 100 74C78 74 62 84 57 102Z",
  bob: "M55 110C48 32 152 32 145 110C140 88 122 76 100 76C78 76 60 88 55 110Z",
};

const BACK: Partial<Record<Style, string>> = {
  long: "M54 108C46 40 154 40 146 108C150 150 154 190 150 220L50 220C46 190 50 150 54 108Z",
  bob: "M52 114C46 40 154 40 148 114L152 162Q100 180 48 162Z",
};

function Figure({ look, halo }: { look: Look; halo?: "light" | "lime" }): ReactNode {
  const { skin, hair, shirt, style } = look;
  return (
    <>
      {halo === "lime" && <circle cx="100" cy="128" r="92" fill="rgba(220,245,63,0.16)" />}
      {halo === "light" && <circle cx="100" cy="128" r="92" fill="rgba(255,255,255,0.12)" />}
      {BACK[style] && <path d={BACK[style]} fill={hair} />}
      {style === "bun" && <circle cx="100" cy="40" r="20" fill={hair} />}
      <path d="M4 240C4 192 44 172 100 172C156 172 196 192 196 240Z" fill={shirt} />
      {look.dupatta && (
        <>
          <path d="M118 172C160 178 196 198 196 240L146 240C146 216 128 200 98 196Z" fill={look.dupatta} />
          <path d="M132 178C160 190 176 208 178 240" stroke="rgba(255,255,255,0.45)" strokeWidth="3" strokeDasharray="2 7" strokeLinecap="round" fill="none" />
        </>
      )}
      <circle cx="59" cy="114" r="7" fill={skin} />
      <circle cx="141" cy="114" r="7" fill={skin} />
      <path d="M84 148H116V176Q100 194 84 176Z" fill={skin} />
      <path d="M84 166H116V176Q100 190 84 176Z" fill="rgba(0,0,0,0.14)" />
      <ellipse cx="100" cy="110" rx="41" ry="48" fill={skin} />
      <circle cx="76" cy="124" r="7" fill="rgba(220,60,60,0.13)" />
      <circle cx="124" cy="124" r="7" fill="rgba(220,60,60,0.13)" />
      <path d="M74 99Q84 94 94 98M106 98Q116 94 126 99" stroke={hair} strokeWidth="3.4" strokeLinecap="round" fill="none" />
      <ellipse cx="84" cy="111" rx="3.6" ry="4.4" fill="#1b1020" />
      <ellipse cx="116" cy="111" rx="3.6" ry="4.4" fill="#1b1020" />
      <path d="M100 114Q96 124 100 127" stroke="rgba(0,0,0,0.22)" strokeWidth="2.4" strokeLinecap="round" fill="none" />
      <path d="M87 135Q100 147 113 135" stroke="#6b2d2d" strokeWidth="3" strokeLinecap="round" fill="none" />
      {look.mustache && <path d="M84 130Q100 122 116 130Q100 135 84 130Z" fill={hair} />}
      {look.bindi && <circle cx="100" cy="93" r="3.4" fill="#d1242f" />}
      {look.glasses && (
        <>
          <circle cx="84" cy="111" r="14" fill="rgba(255,255,255,0.14)" stroke="#1b1b22" strokeWidth="3" />
          <circle cx="116" cy="111" r="14" fill="rgba(255,255,255,0.14)" stroke="#1b1b22" strokeWidth="3" />
          <path d="M98 110H102" stroke="#1b1b22" strokeWidth="3" />
        </>
      )}
      <path d={FRONT[style]} fill={hair} />
    </>
  );
}

/** Head and shoulders, bottom-aligned inside whatever box it is given. */
export function Person({ name, halo, className }: { name: PersonName; halo?: "light" | "lime"; className?: string }) {
  return (
    <svg className={className} viewBox="0 0 200 240" preserveAspectRatio="xMidYMax meet" aria-hidden="true" focusable="false">
      <Figure look={LOOKS[name]} halo={halo} />
    </svg>
  );
}

/** A round face on a coloured tile, for a row of small avatars. */
export function Avatar({ name, className }: { name: PersonName; className?: string }) {
  const look = LOOKS[name];
  return (
    <span className={className} style={{ background: look.tile }} aria-hidden="true">
      <svg className="block size-full" viewBox="22 40 156 156" preserveAspectRatio="xMidYMid slice" focusable="false">
        <Figure look={look} />
      </svg>
    </span>
  );
}
