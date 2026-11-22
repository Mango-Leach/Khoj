import { describe, expect, it } from "vitest";
import en from "../i18n/en.json";
import hi from "../i18n/hi.json";
import mr from "../i18n/mr.json";
import { interpolate, translate } from "./i18n";

describe("i18n dictionaries", () => {
  const keys = Object.keys(en).sort();

  it("Hindi has exactly the same keys as English", () => {
    expect(Object.keys(hi).sort()).toEqual(keys);
  });

  it("Marathi has exactly the same keys as English", () => {
    expect(Object.keys(mr).sort()).toEqual(keys);
  });

  it("no translation is empty", () => {
    for (const dict of [en, hi, mr]) {
      for (const [key, value] of Object.entries(dict)) {
        expect(value.trim(), key).not.toBe("");
      }
    }
  });

  it("translates per language", () => {
    expect(translate("en", "status.ok")).toBe("Working");
    expect(translate("hi", "status.ok")).toBe("चालू है");
    expect(translate("mr", "status.ok")).toBe("सुरू आहे");
  });

  it("every translation keeps the same {placeholders} as English", () => {
    const names = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
    for (const [key, value] of Object.entries(en)) {
      expect(names(hi[key as keyof typeof hi]), `hi ${key}`).toEqual(names(value));
      expect(names(mr[key as keyof typeof mr]), `mr ${key}`).toEqual(names(value));
    }
  });
});

describe("interpolate", () => {
  it("fills named placeholders", () => {
    expect(interpolate("Step {current} of {total}", { current: 2, total: 4 })).toBe("Step 2 of 4");
  });

  it("leaves an unknown placeholder visible instead of hiding it", () => {
    expect(interpolate("Hello, {name}", {})).toBe("Hello, {name}");
  });
});
