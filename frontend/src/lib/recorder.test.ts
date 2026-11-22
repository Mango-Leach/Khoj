import { describe, expect, it } from "vitest";
import { downsample, encodeWav, isSilent, peakOf, TARGET_RATE } from "./recorder";

const sine = (seconds: number, rate: number, hz = 440, amp = 0.5) =>
  Float32Array.from({ length: Math.floor(seconds * rate) }, (_, i) => amp * Math.sin((2 * Math.PI * hz * i) / rate));

describe("downsample", () => {
  it("brings 48 kHz down to 16 kHz with a third of the samples", () => {
    const out = downsample(sine(1, 48_000), 48_000, TARGET_RATE);
    expect(out.length).toBe(16_000);
  });

  it("handles 44.1 kHz, which does not divide evenly", () => {
    const out = downsample(sine(1, 44_100), 44_100, TARGET_RATE);
    expect(Math.abs(out.length - 16_000)).toBeLessThanOrEqual(1);
  });

  it("leaves audio that is already slow enough alone", () => {
    const input = sine(0.5, 8_000);
    expect(downsample(input, 8_000, TARGET_RATE)).toBe(input);
  });

  it("keeps a voice-range tone at about the same loudness", () => {
    const out = downsample(sine(1, 48_000, 300, 0.5), 48_000, TARGET_RATE);
    expect(peakOf(out)).toBeGreaterThan(0.4);
  });
});

describe("encodeWav", () => {
  it("writes a standard 16-bit mono header", async () => {
    const wav = encodeWav(sine(0.25, TARGET_RATE), TARGET_RATE);
    expect(wav.type).toBe("audio/wav");
    const view = new DataView(await wav.arrayBuffer());
    const tag = (at: number) => String.fromCharCode(...[0, 1, 2, 3].map((i) => view.getUint8(at + i)));
    expect([tag(0), tag(8), tag(12), tag(36)]).toEqual(["RIFF", "WAVE", "fmt ", "data"]);
    expect(view.getUint16(20, true)).toBe(1); // PCM
    expect(view.getUint16(22, true)).toBe(1); // mono
    expect(view.getUint32(24, true)).toBe(TARGET_RATE);
    expect(view.getUint16(34, true)).toBe(16);
    const samples = Math.floor(0.25 * TARGET_RATE);
    expect(view.getUint32(40, true)).toBe(samples * 2);
    expect(view.getUint32(4, true)).toBe(36 + samples * 2);
    expect(view.byteLength).toBe(44 + samples * 2);
  });

  it("clips out-of-range samples instead of wrapping around", async () => {
    const view = new DataView(await encodeWav(Float32Array.from([2, -2, 0]), TARGET_RATE).arrayBuffer());
    expect(view.getInt16(44, true)).toBe(32767);
    expect(view.getInt16(46, true)).toBe(-32768);
    expect(view.getInt16(48, true)).toBe(0);
  });

  it("keeps a 30-second clip well under the server's size limit", () => {
    const wav = encodeWav(new Float32Array(30 * TARGET_RATE), TARGET_RATE);
    expect(wav.size).toBeLessThan(1_000_000);
  });
});

describe("isSilent", () => {
  it("spots a clip with no voice, so no credit is spent on it", () => {
    expect(isSilent(new Float32Array(16_000))).toBe(true);
    expect(isSilent(Float32Array.from({ length: 16_000 }, () => 0.003))).toBe(true);
  });

  it("lets quiet speech through", () => {
    expect(isSilent(sine(1, TARGET_RATE, 200, 0.05))).toBe(false);
  });
});
