import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { fetchPublicSpeech, fetchSpeech, getPublicVoiceStatus, getVoiceStatus, isApiFailure, transcribeAudio, type VoiceStatus } from "./api";
import type { Lang, MessageKey } from "./i18n";
import { MAX_CLIP_MS, Recorder, recordingSupported } from "./recorder";

export { MAX_CLIP_MS };

// Two ways to listen and to speak, tried in this order:
//   1. our server, which calls Gnani (works in every browser, Hindi and Marathi voices, needs credit)
//   2. the browser's own recogniser and voices (Chrome and Edge only, needs internet)
// and typing always works.

export const SPEECH_TAG: Record<Lang, string> = { en: "en-IN", hi: "hi-IN", mr: "mr-IN" };

// ---------------------------------------------------------------------------
// What the server can do right now
// ---------------------------------------------------------------------------

const STATUS_TTL_MS = 60_000;
let status: VoiceStatus | null = null;
let fetchedAt = 0;
let fetching = false;
const listeners = new Set<() => void>();

function publish(next: VoiceStatus | null): void {
  status = next;
  listeners.forEach((l) => l());
}

/** Asks the server, at most once a minute. Any failure means "not available" and the browser is used. */
function refreshStatus(): void {
  if (fetching || Date.now() - fetchedAt < STATUS_TTL_MS) return;
  fetching = true;
  getVoiceStatus()
    .then((s) => publish(s))
    .catch(() => publish({ asr: false, tts: false }))
    .finally(() => {
      fetching = false;
      fetchedAt = Date.now();
    });
}

/** After a failure, stop trying the server for a while, so one tap does not wait on a dead service twice. */
function markDown(service: keyof VoiceStatus, forMs: number): void {
  publish({ ...(status ?? { asr: false, tts: false }), [service]: false });
  fetchedAt = Date.now() - STATUS_TTL_MS + forMs; // re-check once the pause is over
}

/** For tests and sign-out: forget what was learned. */
export function resetVoiceStatus(): void {
  fetchedAt = 0;
  publish(null);
}

/** null while unknown. A visitor (not signed in) has no use for the signed-in status, so it is not asked for. */
export function useVoiceStatus(skip = false): VoiceStatus | null {
  const value = useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => status,
    () => null,
  );
  useEffect(() => {
    if (!skip) refreshStatus();
  }, [skip]);
  return value;
}

// ---------------------------------------------------------------------------
// The browser's own recogniser (the second choice)
// ---------------------------------------------------------------------------

// The lib.dom typings for the recogniser are not in every TypeScript version, so the small
// part used here is declared locally.
interface RecResult {
  isFinal: boolean;
  0: { transcript: string };
}
interface RecEvent {
  resultIndex: number;
  results: ArrayLike<RecResult>;
}
interface Recogniser {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((e: RecEvent) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
}
type RecogniserCtor = new () => Recogniser;

function ctor(): RecogniserCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: RecogniserCtor; webkitSpeechRecognition?: RecogniserCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export const recognitionSupported = (): boolean => ctor() !== null;

export type SpeechProblem = "denied" | "nothing" | "network" | "service" | "failed";

/** What to tell the learner for each problem. Every screen that listens shows one of these, so a failure is never silent. */
export const PROBLEM_TEXT: Record<SpeechProblem, MessageKey> = {
  denied: "intake.problem.denied",
  nothing: "intake.problem.nothing",
  network: "intake.problem.network",
  service: "intake.problem.service",
  failed: "intake.problem.failed",
};

/** Maps the browser recogniser's error names to the few problems a learner can act on. */
export function problemFor(error: string): SpeechProblem | null {
  switch (error) {
    case "not-allowed":
    case "service-not-allowed":
      return "denied";
    case "no-speech":
      return "nothing";
    case "network":
      return "network";
    case "aborted":
      return null; // we stopped it ourselves
    default:
      return "failed";
  }
}

/** The same, for a failed call to our own server. */
export function problemForServer(err: unknown): SpeechProblem {
  if (isApiFailure(err)) {
    if (err.code === "network" || err.status === 0) return "network";
    if (err.code === "speech_unavailable" || err.code === "speech_busy") return "service";
    if (err.code === "bad_audio") return "nothing";
  }
  return "failed";
}

/** Joins finished and in-progress pieces of a recognition result into one line. */
export function joinResults(results: ArrayLike<RecResult>): { final: string; interim: string } {
  let final = "";
  let interim = "";
  for (let i = 0; i < results.length; i++) {
    const piece = results[i][0].transcript;
    if (results[i].isFinal) final += piece;
    else interim += piece;
  }
  return { final: final.trim(), interim: interim.trim() };
}

// ---------------------------------------------------------------------------
// Listening
// ---------------------------------------------------------------------------

export interface Listener {
  /** Which engine will listen: our server, the browser, or none (type instead). */
  mode: "server" | "browser" | null;
  supported: boolean;
  listening: boolean;
  /** The recording has stopped and is being turned into words. */
  busy: boolean;
  /** Text heard so far (browser mode only; the server answers once, at the end). */
  heard: string;
  /** Loudness 0..1 while recording (server mode), for the moving bars. */
  level: number;
  problem: SpeechProblem | null;
  start: () => void;
  stop: () => void;
}

function isPermissionError(err: unknown): boolean {
  return err instanceof DOMException && (err.name === "NotAllowedError" || err.name === "SecurityError");
}

/** Records one short answer. `onDone` receives the final text once the learner stops or time runs out. */
export function useListener(lang: Lang, onDone: (text: string, via: "server" | "browser") => void): Listener {
  const voice = useVoiceStatus();
  const serverOk = voice?.asr === true && recordingSupported();
  const browserOk = recognitionSupported();
  const mode: Listener["mode"] = serverOk ? "server" : browserOk ? "browser" : null;

  const [listening, setListening] = useState(false);
  const [busy, setBusy] = useState(false);
  const [heard, setHeard] = useState("");
  const [level, setLevel] = useState(0);
  const [problem, setProblem] = useState<SpeechProblem | null>(null);

  const rec = useRef<Recogniser | null>(null);
  const recorder = useRef<Recorder | null>(null);
  const finalText = useRef("");
  const timer = useRef<number | undefined>(undefined);
  const spokenLang = useRef<Lang>(lang);
  const alive = useRef(true);
  const done = useRef(onDone);
  done.current = onDone;

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      window.clearTimeout(timer.current);
      const r = rec.current;
      if (r) {
        r.onend = null; // leaving the screen must not submit a half answer
        r.abort();
      }
      rec.current = null;
      recorder.current?.cancel();
      recorder.current = null;
    };
  }, []);

  // --- our server -------------------------------------------------------------

  const stopServer = useCallback(async () => {
    window.clearTimeout(timer.current);
    const r = recorder.current;
    if (!r) return;
    recorder.current = null;
    setListening(false);
    setLevel(0);
    const clip = await r.stop();
    if (!alive.current) return;
    if (clip.silent || clip.seconds < 0.4) return setProblem("nothing"); // no voice in it: spend no credit
    setBusy(true);
    try {
      const res = await transcribeAudio(clip.wav, spokenLang.current);
      if (!alive.current) return;
      if (res.transcript) done.current(res.transcript, "server");
      else setProblem("nothing");
    } catch (err) {
      if (!alive.current) return;
      const p = problemForServer(err);
      if (p === "service") markDown("asr", isApiFailure(err) && err.code === "speech_busy" ? 20_000 : 5 * 60_000);
      setProblem(p);
    } finally {
      if (alive.current) setBusy(false);
    }
  }, []);

  const startServer = useCallback(async () => {
    if (recorder.current) return;
    spokenLang.current = lang;
    setHeard("");
    setProblem(null);
    const r = new Recorder();
    try {
      await r.start(setLevel);
    } catch (err) {
      r.cancel();
      setProblem(isPermissionError(err) ? "denied" : "failed");
      return;
    }
    if (!alive.current) return r.cancel();
    recorder.current = r;
    setListening(true);
    timer.current = window.setTimeout(() => void stopServer(), MAX_CLIP_MS);
  }, [lang, stopServer]);

  // --- the browser ------------------------------------------------------------

  const startBrowser = useCallback(() => {
    const Ctor = ctor();
    if (!Ctor || rec.current) return;
    const r = new Ctor();
    r.lang = SPEECH_TAG[lang];
    r.continuous = true;
    r.interimResults = true;
    r.maxAlternatives = 1;
    finalText.current = "";
    setHeard("");
    setProblem(null);
    r.onresult = (e) => {
      const { final, interim } = joinResults(e.results);
      finalText.current = [final, interim].filter(Boolean).join(" ");
      setHeard(finalText.current);
    };
    r.onerror = (e) => setProblem(problemFor(e.error));
    r.onend = () => {
      window.clearTimeout(timer.current);
      rec.current = null;
      setListening(false);
      if (finalText.current) done.current(finalText.current, "browser");
    };
    rec.current = r;
    try {
      r.start();
      setListening(true);
      timer.current = window.setTimeout(() => r.stop(), MAX_CLIP_MS);
    } catch {
      rec.current = null;
      setProblem("failed");
    }
  }, [lang]);

  const start = useCallback(() => {
    if (busy) return;
    if (mode === "server") void startServer();
    else if (mode === "browser") startBrowser();
  }, [busy, mode, startServer, startBrowser]);

  const stop = useCallback(() => {
    if (recorder.current) void stopServer();
    else rec.current?.stop();
  }, [stopServer]);

  return { mode, supported: mode !== null, listening, busy, heard, level, problem, start, stop };
}

// ---------------------------------------------------------------------------
// Reading aloud
// ---------------------------------------------------------------------------

export const synthesisSupported = (): boolean => typeof window !== "undefined" && "speechSynthesis" in window;

/** Reads text in the learner's language with the browser's own voice. Returns a function that stops it. */
export function speak(text: string, lang: Lang, onEnd?: () => void): () => void {
  if (!synthesisSupported()) {
    onEnd?.();
    return () => undefined;
  }
  const synth = window.speechSynthesis;
  synth.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = SPEECH_TAG[lang];
  const prefix = u.lang.slice(0, 2).toLowerCase();
  const voice = synth.getVoices().find((v) => v.lang.toLowerCase().startsWith(prefix));
  if (voice) u.voice = voice;
  u.onend = () => onEnd?.();
  u.onerror = () => onEnd?.();
  synth.speak(u);
  return () => synth.cancel();
}

// Spoken lines already fetched in this visit, so a repeat tap plays at once and costs nothing.
const audioCache = new Map<string, Blob>();
export const clearSpeechCache = (): void => audioCache.clear();

export interface Speaker {
  available: boolean;
  speaking: boolean;
  /** Fetching the audio from the server. */
  loading: boolean;
  toggle: (text: string) => void;
  stop: () => void;
}

/**
 * A Listen button's state: server voice first, then the browser's voice.
 * `visitor` is for the public page, where nobody is signed in: it asks the public voice
 * endpoints, which give the same voice but only for new lines within a small allowance.
 */
export function useSpeaker(lang: Lang, visitor = false): Speaker {
  const voice = useVoiceStatus(visitor);
  const [visitorTts, setVisitorTts] = useState<boolean | null>(null);
  useEffect(() => {
    if (!visitor) return;
    let live = true;
    getPublicVoiceStatus()
      .then((s) => live && setVisitorTts(s.tts))
      .catch(() => live && setVisitorTts(false));
    return () => {
      live = false;
    };
  }, [visitor]);
  const serverTts = visitor ? visitorTts === true : voice?.tts === true;
  const available = serverTts || synthesisSupported();
  const [speaking, setSpeaking] = useState(false);
  const [loading, setLoading] = useState(false);
  const cancel = useRef<(() => void) | null>(null);
  const ticket = useRef(0); // a stop while the audio is still loading must not start it afterwards

  const stop = useCallback(() => {
    ticket.current++;
    cancel.current?.();
    cancel.current = null;
    setSpeaking(false);
    setLoading(false);
  }, []);

  const playBrowser = useCallback(
    (text: string) => {
      setSpeaking(true);
      cancel.current = speak(text, lang, () => setSpeaking(false));
    },
    [lang],
  );

  const toggle = useCallback(
    (text: string) => {
      if (speaking || loading) return stop();
      if (!serverTts) return playBrowser(text);
      const mine = ++ticket.current;
      const key = `${lang}|${text}`;
      setLoading(true);
      void (async () => {
        try {
          let blob = audioCache.get(key);
          if (!blob) {
            blob = await (visitor ? fetchPublicSpeech(text, lang) : fetchSpeech(text, lang));
            audioCache.set(key, blob);
          }
          if (ticket.current !== mine) return;
          const url = URL.createObjectURL(blob);
          const audio = new Audio(url);
          const finish = () => {
            URL.revokeObjectURL(url);
            if (ticket.current === mine) setSpeaking(false);
          };
          audio.onended = finish;
          audio.onerror = finish;
          cancel.current = () => {
            audio.pause();
            finish();
          };
          setLoading(false);
          setSpeaking(true);
          await audio.play();
        } catch (err) {
          if (ticket.current !== mine) return;
          setLoading(false);
          setSpeaking(false);
          if (isApiFailure(err) && (err.code === "speech_unavailable" || err.code === "speech_busy" || err.code === "too_many_requests")) {
            if (visitor) setVisitorTts(false);
            else markDown("tts", 5 * 60_000);
          }
          if (synthesisSupported()) playBrowser(text); // the server could not speak; the browser can
        }
      })();
    },
    [lang, loading, playBrowser, serverTts, speaking, stop, visitor],
  );

  useEffect(() => stop, [stop]);
  useEffect(() => stop(), [lang, stop]);

  return { available, speaking, loading, toggle, stop };
}
