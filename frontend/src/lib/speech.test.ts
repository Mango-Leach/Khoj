import { describe, expect, it } from "vitest";
import { joinResults, problemFor, SPEECH_TAG } from "./speech";

const part = (transcript: string, isFinal: boolean) => Object.assign([{ transcript }], { isFinal }) as unknown as { isFinal: boolean; 0: { transcript: string } };

describe("problemFor", () => {
  it("names the problems a learner can act on", () => {
    expect(problemFor("not-allowed")).toBe("denied");
    expect(problemFor("service-not-allowed")).toBe("denied");
    expect(problemFor("no-speech")).toBe("nothing");
    expect(problemFor("network")).toBe("network");
    expect(problemFor("audio-capture")).toBe("failed");
  });

  it("ignores an abort we caused ourselves", () => {
    expect(problemFor("aborted")).toBeNull();
  });
});

describe("joinResults", () => {
  it("keeps finished and in-progress text apart", () => {
    const out = joinResults([part("मला शिवणकाम ", true), part("आवडतं", false)]);
    expect(out).toEqual({ final: "मला शिवणकाम", interim: "आवडतं" });
  });

  it("is empty when nothing was heard", () => {
    expect(joinResults([])).toEqual({ final: "", interim: "" });
  });
});

describe("SPEECH_TAG", () => {
  it("uses Indian locales for all three languages", () => {
    expect(SPEECH_TAG).toEqual({ en: "en-IN", hi: "hi-IN", mr: "mr-IN" });
  });
});
