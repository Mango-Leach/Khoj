// Records one short answer from the microphone and encodes it as 16 kHz mono WAV.
//
// Why WAV and not MediaRecorder: Chrome and Edge record WebM, which Gnani's speech-to-text does not
// accept (it takes WAV, MP3, OGG, FLAC, AAC, M4A), and Safari records MP4. Capturing raw samples and
// encoding them here works the same in every browser. A 10-second answer is about 320 KB.

export const TARGET_RATE = 16_000;
export const MAX_CLIP_MS = 29_000; // Gnani accepts at most 30 s per clip
const SILENCE_PEAK = 0.012; // a clip that never rises above this has no voice in it

export function recordingSupported(): boolean {
  return (
    typeof navigator !== "undefined" &&
    Boolean(navigator.mediaDevices?.getUserMedia) &&
    (typeof AudioContext !== "undefined" || "webkitAudioContext" in globalThis)
  );
}

/** Lowers the sample rate by averaging, which also acts as a simple low-pass filter. */
export function downsample(input: Float32Array, fromRate: number, toRate: number): Float32Array {
  if (toRate >= fromRate) return input;
  const ratio = fromRate / toRate;
  const out = new Float32Array(Math.floor(input.length / ratio));
  for (let i = 0; i < out.length; i++) {
    const start = Math.floor(i * ratio);
    const end = Math.min(input.length, Math.floor((i + 1) * ratio));
    let sum = 0;
    for (let j = start; j < end; j++) sum += input[j];
    out[i] = end > start ? sum / (end - start) : 0;
  }
  return out;
}

export function peakOf(samples: Float32Array): number {
  let peak = 0;
  for (let i = 0; i < samples.length; i++) {
    const v = Math.abs(samples[i]);
    if (v > peak) peak = v;
  }
  return peak;
}

export function isSilent(samples: Float32Array): boolean {
  return peakOf(samples) < SILENCE_PEAK;
}

/** 16-bit PCM WAV with a standard 44-byte header. */
export function encodeWav(samples: Float32Array, sampleRate: number): Blob {
  const bytes = samples.length * 2;
  const buffer = new ArrayBuffer(44 + bytes);
  const view = new DataView(buffer);
  const text = (offset: number, value: string) => {
    for (let i = 0; i < value.length; i++) view.setUint8(offset + i, value.charCodeAt(i));
  };
  text(0, "RIFF");
  view.setUint32(4, 36 + bytes, true);
  text(8, "WAVE");
  text(12, "fmt ");
  view.setUint32(16, 16, true); // size of the fmt block
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // bytes per second
  view.setUint16(32, 2, true); // bytes per sample frame
  view.setUint16(34, 16, true); // bits per sample
  text(36, "data");
  view.setUint32(40, bytes, true);
  for (let i = 0; i < samples.length; i++) {
    const v = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(44 + i * 2, v < 0 ? v * 0x8000 : v * 0x7fff, true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}

export interface Clip {
  wav: Blob;
  silent: boolean;
  seconds: number;
}

type AudioContextCtor = typeof AudioContext;

export class Recorder {
  private stream: MediaStream | null = null;
  private ctx: AudioContext | null = null;
  private node: ScriptProcessorNode | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private chunks: Float32Array[] = [];

  /** Starts listening. `onLevel` gets a 0..1 loudness about ten times a second, for the moving bars. */
  async start(onLevel: (level: number) => void): Promise<void> {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
    const Ctor: AudioContextCtor = (globalThis as { AudioContext?: AudioContextCtor }).AudioContext ?? (globalThis as unknown as { webkitAudioContext: AudioContextCtor }).webkitAudioContext;
    this.ctx = new Ctor();
    if (this.ctx.state === "suspended") await this.ctx.resume();
    this.source = this.ctx.createMediaStreamSource(this.stream);
    this.node = this.ctx.createScriptProcessor(4096, 1, 1);
    this.chunks = [];
    this.node.onaudioprocess = (e) => {
      const data = e.inputBuffer.getChannelData(0);
      this.chunks.push(new Float32Array(data));
      let sum = 0;
      for (let i = 0; i < data.length; i += 8) sum += data[i] * data[i];
      onLevel(Math.min(1, Math.sqrt(sum / (data.length / 8)) * 6));
    };
    this.source.connect(this.node);
    this.node.connect(this.ctx.destination); // some browsers only run the node when it is connected; it outputs silence
  }

  /** Stops, releases the microphone and returns the clip. */
  async stop(): Promise<Clip> {
    const rate = this.ctx?.sampleRate ?? TARGET_RATE;
    this.release();
    const total = this.chunks.reduce((n, c) => n + c.length, 0);
    const all = new Float32Array(total);
    let offset = 0;
    for (const c of this.chunks) {
      all.set(c, offset);
      offset += c.length;
    }
    this.chunks = [];
    const samples = downsample(all, rate, TARGET_RATE);
    return { wav: encodeWav(samples, TARGET_RATE), silent: isSilent(samples), seconds: samples.length / TARGET_RATE };
  }

  /** Throws the recording away (the learner left the screen). */
  cancel(): void {
    this.release();
    this.chunks = [];
  }

  private release(): void {
    if (this.node) this.node.onaudioprocess = null;
    this.source?.disconnect();
    this.node?.disconnect();
    this.stream?.getTracks().forEach((t) => t.stop()); // turns the microphone light off
    void this.ctx?.close();
    this.stream = this.ctx = this.node = this.source = null;
  }
}
