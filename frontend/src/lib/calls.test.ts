import { describe, expect, it } from "vitest";
import { contactHref, dayKey, spacedPhone, timeLabel, todayIst, toIso } from "./calls";

describe("career call times", () => {
  it("turns a date and time in Indian time into the UTC moment", () => {
    expect(toIso("2099-01-02", "11:00")).toBe("2099-01-02T05:30:00.000Z");
    expect(toIso("2099-01-02", "00:15")).toBe("2099-01-01T18:45:00.000Z");
  });

  it("groups by the Indian day, not the UTC day", () => {
    expect(dayKey("2099-01-01T18:45:00.000Z")).toBe("2099-01-02");
    expect(dayKey("2099-01-02T05:30:00.000Z")).toBe("2099-01-02");
  });

  it("knows today in Indian time", () => {
    expect(todayIst(Date.parse("2099-01-01T19:00:00Z"))).toBe("2099-01-02");
  });

  it("shows the time with Latin digits in every language", () => {
    for (const lang of ["en", "hi", "mr"] as const) expect(timeLabel("2099-01-02T05:30:00.000Z", lang)).toMatch(/11[:.]00/);
  });

  it("opens a link as it is and a phone number as a call", () => {
    expect(contactHref("link", "https://meet.google.com/abc")).toBe("https://meet.google.com/abc");
    expect(contactHref("phone", "9876543210")).toBe("tel:+919876543210");
    expect(spacedPhone("9876543210")).toBe("98765 43210");
  });
});
