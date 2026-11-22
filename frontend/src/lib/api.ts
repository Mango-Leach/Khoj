import { getLang, type Lang } from "./i18n";

const API_BASE = "/api/v1";
const REFRESH_KEY = "khoj.refresh";

// ---------------------------------------------------------------------------
// Types (mirror backend/app/models)
// ---------------------------------------------------------------------------

export interface Health {
  status: string;
  env: string;
  demo_mode: boolean;
  db: { configured: boolean; ok: boolean; detail: string };
  llm: {
    mode: "cache_only" | "live";
    routes: Record<string, "ollama" | "gemini">;
    vision_order: string[];
    ollama: { host: string; reachable: boolean; text_model_set: boolean; vision_model_set: boolean };
    gemini: { configured: boolean };
  };
}

export interface User {
  id: string;
  roles: string[];
  language: Lang;
  profile: "student" | "teacher" | null;
  /** The signed-in person's own number, shown only on their own Home screen. */
  phone?: string | null;
}

export interface Tokens {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  user: User;
}

export interface District {
  id: string;
  en: string;
  hi: string;
  mr: string;
}

export interface StudentProfile {
  name: string;
  age: number;
  age_band: string;
  grade: number;
  state: string;
  district: string;
  block: string;
  guardian_consent: boolean;
}

export type TeacherRole = "teacher" | "mentor" | "facilitator" | "expert";

export interface TeacherProfile {
  name: string;
  roles: TeacherRole[];
  languages: Lang[];
  district: string;
  block: string;
  weekly_hours: number;
  /** 0: not verified, cannot be matched. 1: skill check passed and evidence approved. 2: proven by outcomes. */
  tier: number;
  skills: { tag: string; level: number | null; verified: boolean }[];
  capacity: { limit: number; free: number };
  evidence: { status: EvidenceStatus; /** A review of new proof is running right now (the status can stay approved meanwhile). */ reviewing: boolean; note: string; /** Stable codes for what to fix; each has a translated message. */ reasons: string[] };
  credentials: Credential[];
  passed_areas: string[];
  /** Skill areas with a passed test and approved proof. Empty until both are in place. */
  verified_areas: { id: string; name: Localised }[];
}

/** pending: something was added and nobody has looked at it yet. reviewing: the photos are being checked right now. */
export type EvidenceStatus = "none" | "pending" | "reviewing" | "verified" | "rejected";
export type CredentialKind = "certificate" | "work_sample" | "experience" | "reference";

export interface ProofPhoto {
  id: string;
  /** true or false once the photo has been checked, null before. */
  good: boolean | null;
  reasons: string[];
}

export interface Credential {
  id: string;
  kind: CredentialKind;
  title: string;
  note: string;
  added_at: string;
  photos: ProofPhoto[];
  /** `approved` proofs are saved under the skills they prove and cannot be changed. */
  state: "new" | "approved";
  areas: { id: string; name: Localised; test_passed: boolean }[];
}

export interface StudentProfileInput {
  name: string;
  age: number;
  grade: number;
  district: string;
  block: string;
  guardian_consent: boolean;
}

export interface TeacherProfileInput {
  name: string;
  roles: TeacherRole[];
  languages: Lang[];
  district: string;
  block: string;
  weekly_hours: number;
}

// ---------------------------------------------------------------------------
// Errors: the server always answers { code, message, hint }
// ---------------------------------------------------------------------------

export class ApiFailure extends Error {
  readonly status: number;
  readonly code: string;
  readonly hint: string;
  readonly extra: Record<string, unknown>;

  constructor(status: number, code: string, message = "", hint = "", extra: Record<string, unknown> = {}) {
    super(message || code);
    this.status = status;
    this.code = code;
    this.hint = hint;
    this.extra = extra;
  }
}

export function isApiFailure(err: unknown): err is ApiFailure {
  return err instanceof ApiFailure;
}

// ---------------------------------------------------------------------------
// Token storage: the access token lives in memory; the refresh token persists so a
// reload keeps the learner signed in. Storage can throw, so it is only a convenience.
// ---------------------------------------------------------------------------

let accessToken: string | null = null;
let onSessionLost: (() => void) | null = null;

export function readRefreshToken(): string | null {
  try {
    return localStorage.getItem(REFRESH_KEY);
  } catch {
    return null;
  }
}

function writeRefreshToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(REFRESH_KEY, token);
    else localStorage.removeItem(REFRESH_KEY);
  } catch {
    /* not persisted */
  }
}

export function storeTokens(tokens: Pick<Tokens, "access_token" | "refresh_token">): void {
  accessToken = tokens.access_token;
  writeRefreshToken(tokens.refresh_token);
}

export function clearTokens(): void {
  accessToken = null;
  writeRefreshToken(null);
}

/** Called when a refresh fails for good, so the app can send the learner to sign in. */
export function setSessionLostHandler(handler: (() => void) | null): void {
  onSessionLost = handler;
}

// ---------------------------------------------------------------------------
// Core request
// ---------------------------------------------------------------------------

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  auth?: boolean;
  signal?: AbortSignal;
  accept?: string;
}

async function parseFailure(res: Response): Promise<ApiFailure> {
  try {
    const data = (await res.json()) as Record<string, unknown>;
    const { code, message, hint, ...extra } = data;
    return new ApiFailure(res.status, String(code ?? "generic"), String(message ?? ""), String(hint ?? ""), extra);
  } catch {
    return new ApiFailure(res.status, "generic");
  }
}

async function send(path: string, opts: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = { Accept: opts.accept ?? "application/json", "Accept-Language": getLang() };
  const isForm = typeof FormData !== "undefined" && opts.body instanceof FormData;
  // A form sets its own multipart boundary, so no Content-Type is given for it.
  if (opts.body !== undefined && !isForm) headers["Content-Type"] = "application/json";
  if (opts.auth !== false && accessToken) headers.Authorization = `Bearer ${accessToken}`;
  try {
    return await fetch(`${API_BASE}${path}`, {
      method: opts.method ?? "GET",
      headers,
      body: opts.body === undefined ? undefined : isForm ? (opts.body as FormData) : JSON.stringify(opts.body),
      signal: opts.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiFailure(0, "network");
  }
}

// One refresh at a time: parallel 401s must not each spend (and rotate away) the same token.
let refreshing: Promise<Tokens> | null = null;

export function refreshSession(): Promise<Tokens> {
  if (refreshing) return refreshing;
  const token = readRefreshToken();
  if (!token) return Promise.reject(new ApiFailure(401, "invalid_refresh_token"));
  refreshing = (async () => {
    const res = await send("/auth/refresh", { method: "POST", body: { refresh_token: token }, auth: false });
    if (!res.ok) {
      const failure = await parseFailure(res);
      // Only a definite rejection ends the session; a server error keeps the token for later.
      if (failure.status === 401) {
        clearTokens();
        onSessionLost?.();
      }
      throw failure;
    }
    const tokens = (await res.json()) as Tokens;
    storeTokens(tokens);
    return tokens;
  })().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

async function requestRaw(path: string, opts: RequestOptions = {}): Promise<Response> {
  let res = await send(path, opts);
  if (res.status === 401 && opts.auth !== false && readRefreshToken()) {
    await refreshSession();
    res = await send(path, opts);
  }
  if (!res.ok) throw await parseFailure(res);
  return res;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const res = await requestRaw(path, opts);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------

export const getHealth = (signal?: AbortSignal) => request<Health>("/health", { auth: false, signal });

export const requestOtp = (phone: string) =>
  request<{ expires_in: number; resend_after: number }>("/auth/otp/request", { method: "POST", body: { phone }, auth: false });

export async function verifyOtp(phone: string, otp: string): Promise<Tokens> {
  const tokens = await request<Tokens>("/auth/otp/verify", { method: "POST", body: { phone, otp }, auth: false });
  storeTokens(tokens);
  return tokens;
}

export async function signOut(): Promise<void> {
  const token = readRefreshToken();
  clearTokens();
  if (!token) return;
  try {
    await request<void>("/auth/logout", { method: "POST", body: { refresh_token: token }, auth: false });
  } catch {
    /* the token is already gone locally; the server copy expires by itself */
  }
}

export const getMe = () => request<User>("/me");
export const saveLanguage = (language: Lang) => request<User>("/me/preferences", { method: "PATCH", body: { language } });

export const getDistricts = () => request<{ state: string; districts: District[] }>("/catalog/districts", { auth: false });

export const createStudent = (body: StudentProfileInput) => request<StudentProfile>("/students/profile", { method: "POST", body });
export const getStudent = () => request<StudentProfile>("/students/me");
export const createTeacher = (body: TeacherProfileInput) => request<TeacherProfile>("/teachers/profile", { method: "POST", body });
export const getTeacher = () => request<TeacherProfile>("/teachers/me");

// ---------------------------------------------------------------------------
// Intake (M2)
// ---------------------------------------------------------------------------

export type Localised = Record<Lang, string>;

export interface Category {
  id: string;
  icon: string;
  name: Localised;
}

export interface SkillInfo {
  id: string;
  family: string;
  name: Localised;
}

export interface IntakeChoice {
  id: string;
  label: Localised;
}

export interface IntakeQuestion {
  id: string;
  kind: "open" | "choice";
  text: Localised;
  /** An example answer, shown under open questions so people know how much to say. */
  example?: Localised;
  choices?: IntakeChoice[];
}

export type AnswerSource = "typed" | "browser_asr" | "gnani" | "bhashini" | "tap";

export interface IntakeAnswer {
  question_id: string;
  transcript: string;
  transcript_en: string;
  translation: "ok" | "failed" | "not_needed" | "pending";
  source: AnswerSource;
  choice_id: string | null;
}

export interface Extracted {
  skills: string[];
  /** Skills the learner added themselves from the list (a subset of `skills`). */
  learner_added?: string[];
  other_skills: string[];
  interests: string[];
  goal: string | null;
  constraints: {
    budget: "none" | "low" | "medium" | "unknown";
    can_move_away: "yes" | "no" | "unknown";
    hours_per_week: number | null;
    earned_before: "earned" | "helped" | "no" | "unknown";
    priority: "earn_soon" | "earn_more" | "near_home" | "govt_job" | "own_business" | "unknown";
  };
}

export type IntakeStatus = "in_progress" | "review" | "done" | "abandoned";

export interface IntakeSession {
  id: string;
  status: IntakeStatus;
  category_ids: string[];
  not_sure: boolean;
  language: Lang;
  answers: IntakeAnswer[];
  next_question_id: string | null;
  total_questions: number;
  extracted: Extracted | null;
  extraction_source: "ollama" | "gemini" | "cache" | "fallback" | null;
}

export interface AcceptInput {
  skills: string[];
  other_skills: string[];
  interests: string[];
  goal: string | null;
}

export const getCategories = () => request<{ categories: Category[] }>("/catalog/categories", { auth: false });
export const getSkills = () => request<{ skills: SkillInfo[] }>("/catalog/skills", { auth: false });
export const getIntakeQuestions = () => request<{ questions: IntakeQuestion[] }>("/intake/questions");
export const startIntake = (body: { category_ids: string[]; not_sure: boolean; language: Lang }) =>
  request<IntakeSession>("/intake/sessions", { method: "POST", body });
export const getLatestIntake = () => request<IntakeSession>("/intake/sessions/latest");
export const confirmAnswer = (
  sessionId: string,
  body: { question_id: string; transcript?: string; choice_id?: string; source: AnswerSource; language: Lang },
) => request<IntakeSession>(`/intake/sessions/${sessionId}/confirm`, { method: "POST", body });
export const completeIntake = (sessionId: string) => request<IntakeSession>(`/intake/sessions/${sessionId}/complete`, { method: "POST" });
export const acceptIntake = (sessionId: string, body: AcceptInput) =>
  request<IntakeSession>(`/intake/sessions/${sessionId}/accept`, { method: "POST", body });

// ---------------------------------------------------------------------------
// Voice (Gnani, through our server: the browser never holds a key)
// ---------------------------------------------------------------------------

export interface VoiceStatus {
  asr: boolean;
  tts: boolean;
}

export const getVoiceStatus = () => request<VoiceStatus>("/voice/status");

/** For the public page, where nobody is signed in: can the server voice be used? */
export const getPublicVoiceStatus = () => request<{ tts: boolean }>("/voice/public/status", { auth: false });

/** Sends one recorded answer (WAV) and returns the words in it. The server does not keep the audio. */
export function transcribeAudio(audio: Blob, language: Lang): Promise<{ transcript: string; language: Lang }> {
  const form = new FormData();
  form.append("audio", audio, "answer.wav");
  form.append("language", language);
  return request("/voice/asr", { method: "POST", body: form });
}

/** Spoken audio for a line of text (repeated lines are cached on the server). */
export async function fetchSpeech(text: string, language: Lang): Promise<Blob> {
  const res = await requestRaw("/voice/tts", { method: "POST", body: { text, language }, accept: "audio/*" });
  return res.blob();
}

/** The same spoken audio, for a visitor who has not signed in (new lines are rate limited on the server). */
export async function fetchPublicSpeech(text: string, language: Lang): Promise<Blob> {
  const res = await requestRaw("/voice/public/tts", { method: "POST", body: { text, language }, accept: "audio/*", auth: false });
  return res.blob();
}

// ---------------------------------------------------------------------------
// Careers, assessments and choosing a path (M3)
// ---------------------------------------------------------------------------

export type ReasonSource = "template" | "ai" | "ai_translated";

export interface CareerCard {
  career_id: string;
  name: Localised;
  family: string;
  depth: "full" | "card";
  is_stem: boolean;
  summary: Localised;
  first_income_step: Localised;
  safety_class: "low" | "medium" | "high";
  under18_theory_only: boolean;
  source_count: number;
}

export interface PathItem extends CareerCard {
  rank: number;
  reason: Localised;
  reason_source: Record<Lang, ReasonSource>;
  matched_skills: string[];
  related_skills: string[];
  starter: boolean;
  /** best: one of the top fits; also: somewhat related; starter: a starting point, not a match. */
  tier: "best" | "also" | "starter";
}

export interface Assessment {
  id: string;
  status: "ready";
  intake_id: string;
  enrichment: "pending" | "done" | "failed" | "none";
  paths: PathItem[];
}

export interface CareerSource {
  title: string;
  url: string;
  note: string;
  entered_on: string;
  verified_on: string | null;
}

export interface LadderRung {
  rung: number;
  key: "explore" | "learn" | "practise" | "certify" | "earn";
  title: Partial<Localised> & { en: string };
  detail: Partial<Localised> & { en: string };
}

export interface Resource {
  id: string;
  title: string;
  provider: string;
  kind: "mooc" | "course" | "curriculum";
  url: string;
  level: "school" | "diploma" | "college" | null;
  duration_weeks: number | null;
  /** Only languages the listing states. Empty means: check the course page. */
  languages: Lang[];
  cost: "free" | "free_certificate_fee" | null;
  entry: "school_entry_below_secondary" | null;
  found_on: string;
  verified_on: string | null;
  awaiting_verification: boolean;
}

export interface CareerDetail extends CareerCard {
  ladder: LadderRung[];
  machine_translated: Lang[];
  traits: { startup_cost: "none" | "low" | "medium"; min_hours_per_week: number; needs_travel: boolean; self_employment: boolean };
  safety: { class: string; under18_theory_only: boolean; under18_note: Localised };
  /** Real courses and material, linked out. Empty for careers with no specific course found yet. */
  learn: Resource[];
  /** Provider home pages, a fallback when `learn` is empty. */
  portals: { title: string; provider: string; url: string; language: string }[];
  sources: CareerSource[];
}

export type JourneyState = "path_selected" | "mentor_pending" | "in_progress" | "stalled" | "completed" | "opportunities_open" | "enrolled" | "abandoned";

export interface Journey {
  id: string;
  state: JourneyState;
  career: CareerCard;
  assessment_id: string;
  /** Present on `GET /journeys/me`: the mentor holding or asked for this journey, and the latest request. */
  mentor?: Mentor | null;
  request?: MentorRequest | null;
}

export const createAssessment = () => request<Assessment>("/assessments", { method: "POST" });
export const getLatestAssessment = () => request<Assessment>("/assessments/latest");
export const getAssessment = (id: string) => request<Assessment>(`/assessments/${id}`);
export const getCareer = (id: string) => request<CareerDetail>(`/careers/${id}`);
export const selectCareer = (id: string) => request<Journey>(`/careers/${id}/select`, { method: "POST" });
export const getMyJourney = () => request<Journey>("/journeys/me");

// ---------------------------------------------------------------------------
// Scholarships and schemes (M4)
// ---------------------------------------------------------------------------

/** Text that always has English and may have a machine translation in Hindi or Marathi. */
export type PartialLocalised = { en: string } & Partial<Record<Lang, string>>;

export type SchemeStatus = "eligible" | "check_with_office" | "not_eligible";

export type SchemeFactKey =
  | "annual_income_inr"
  | "social_category"
  | "school_type"
  | "in_professional_course"
  | "qualification"
  | "works_in_listed_trade"
  | "govt_service_in_family"
  | "took_similar_loan_5y";

/** The few answers a learner may give for one check. Nothing here is stored by the server. */
export type SchemeFacts = Partial<{
  annual_income_inr: number;
  social_category: "sc" | "st" | "obc" | "dnt" | "ebc" | "general";
  school_type: "government" | "government_aided" | "local_body" | "private" | "central_residential";
  in_professional_course: boolean;
  qualification: "none" | "diploma" | "vocational_certificate" | "graduate";
  works_in_listed_trade: boolean;
  govt_service_in_family: boolean;
  took_similar_loan_5y: boolean;
}>;

export interface SchemeCondition {
  fact: string;
  label: PartialLocalised;
}

export interface SchemeSource {
  title: string;
  url: string;
  entered_on: string;
  verified_on: string | null;
  awaiting_verification: boolean;
}

export interface SchemeResult {
  id: string;
  name: PartialLocalised;
  summary: PartialLocalised;
  note: Partial<Record<Lang, string>>;
  level: string;
  apply_url: string | null;
  needs: SchemeFactKey[];
  machine_translated: Lang[];
  source: SchemeSource;
  status: SchemeStatus;
  passed: SchemeCondition[];
  failed: SchemeCondition[];
  missing: SchemeCondition[];
  unresolved: SchemeCondition[];
  opens_at: { fact: "age" | "grade"; value: number }[];
  docs: string[];
  stale: boolean;
  expired: boolean;
}

export interface SchemeCheck {
  results: SchemeResult[];
  ask: SchemeFactKey[];
  counts: Record<SchemeStatus, number>;
}

export const checkSchemes = (facts: SchemeFacts, schemeIds?: string[]) =>
  request<SchemeCheck>("/scholarships/check", { method: "POST", body: { facts, scheme_ids: schemeIds } });

// ---------------------------------------------------------------------------
// Teachers, mentor matching and requests (M5)
// ---------------------------------------------------------------------------

export interface Mentor {
  teacher_id: string;
  name: string;
  roles: TeacherRole[];
  languages: Lang[];
  district: string;
  block: string;
  tier: number;
}

export interface MentorRequest {
  id: string;
  journey_id: string;
  status: "pending" | "accepted" | "declined" | "expired" | "cancelled";
  created_at: string;
  expires_at: string;
  decided_at: string | null;
}

export interface Candidate extends Omit<Mentor, "teacher_id"> {
  teacher_id: string;
  /** The skill checks the mentor passed, by name. One check proves a bundle of skills, so skills are not listed one by one. */
  verified_in: { id: string; name: Localised }[];
  speaks_your_language: boolean;
  same_block: boolean;
  same_district: boolean;
  free_places: number;
}

export interface LearnerCard {
  name: string;
  age_band: string | null;
  grade: number | null;
  district: string | null;
  block: string | null;
  language: Lang;
  guardian_consent: boolean;
  career: Partial<CareerCard> & { career_id: string };
  skills: { id: string; name: Localised }[];
  /** A learner under 18 on a hazardous path: theory and a training board only. */
  theory_only: boolean;
}

export interface IncomingRequest extends MentorRequest {
  student: LearnerCard;
}

export interface Mentee {
  journey_id: string;
  state: JourneyState;
  since: string | null;
  student: LearnerCard;
}

export interface TestAreaSummary {
  id: string;
  name: Localised;
  career_ids: string[];
  passed: boolean;
  attempts_left: number;
}

export interface TestArea {
  id: string;
  name: Localised;
  scale: Record<"1" | "2" | "3" | "4", string>;
  items: { id: string; work: string }[];
  pass_rule: { needed: number; of: number; within: number };
  passed: boolean;
  attempts_left: number;
}

export interface TestResult {
  passed: boolean;
  close: number;
  needed: number;
  of: number;
  attempts_left: number;
  tier: number;
  awaiting_evidence: boolean;
}

export const getMentorCandidates = (journeyId: string) =>
  request<{ journey_id: string; career_id: string; candidates: Candidate[] }>(`/journeys/${journeyId}/match-mentor`);
export const requestMentor = (journeyId: string, teacherId: string) =>
  request<MentorRequest>(`/journeys/${journeyId}/mentor-request`, { method: "POST", body: { teacher_id: teacherId } });
export const cancelMentorRequest = (journeyId: string) =>
  request<MentorRequest>(`/journeys/${journeyId}/mentor-request/cancel`, { method: "POST" });

export const getTeacherRequests = () =>
  request<{ capacity: { limit: number; free: number }; pending: IncomingRequest[]; recent: IncomingRequest[] }>("/teachers/me/requests");
export const answerRequest = (id: string, accept: boolean) =>
  request<IncomingRequest>(`/requests/${id}/${accept ? "accept" : "decline"}`, { method: "POST" });
export const getMentees = () => request<{ students: Mentee[] }>("/teachers/me/students");

export const getTestAreas = () => request<{ areas: TestAreaSummary[] }>("/teachers/me/assessments");
export const getTestArea = (id: string) => request<TestArea>(`/teachers/me/assessments/${id}`);
export const submitTest = (id: string, scores: Record<string, number>) =>
  request<TestResult>(`/teachers/me/assessments/${id}/submit`, { method: "POST", body: { scores } });
export const addCredential = (body: { kind: CredentialKind; title: string; note: string }) =>
  request<{ credentials: Omit<Credential, "photos">[]; evidence_status: EvidenceStatus }>("/teachers/me/credentials", { method: "POST", body });
export const uploadProofPhoto = (credentialId: string, photo: Blob) => {
  const form = new FormData();
  form.append("file", photo, "proof.jpg");
  return request<{ id: string }>(`/teachers/me/credentials/${credentialId}/photos`, { method: "POST", body: form });
};
export const deleteProofPhoto = (credentialId: string, photoId: string) =>
  request<void>(`/teachers/me/credentials/${credentialId}/photos/${photoId}`, { method: "DELETE" });
/** The photo bytes, fetched with the sign-in header (an <img> tag cannot send it). */
export const fetchProofPhoto = async (credentialId: string, photoId: string): Promise<Blob> =>
  (await requestRaw(`/teachers/me/credentials/${credentialId}/photos/${photoId}`, { accept: "image/jpeg" })).blob();
export const startProofReview = () => request<{ status: "reviewing" }>("/teachers/me/proof/review", { method: "POST" });

// ---------------------------------------------------------------------------
// M6: milestones, assignments, the learner's work and the mentor's review
// ---------------------------------------------------------------------------

export type MilestoneKey = "explore" | "learn" | "practise";
export type SubmissionStatus = "draft" | "submitted" | "approved" | "returned" | "ai_passed" | "ai_returned";
/** Text in the languages it was written in. Default assignments have all three; a mentor's own may have one. */
export type TextMap = Partial<Record<Lang, string>>;

export interface Criterion {
  id: string;
  text: TextMap;
}

export interface AssignmentDoc {
  id: string;
  journey_id: string;
  milestone: MilestoneKey;
  title: TextMap;
  instructions: TextMap;
  criteria: Criterion[];
  source: "template" | "ai" | "teacher";
  status: "draft" | "approved" | "retired";
}

export interface MilestoneAssignment {
  id: string;
  title: TextMap;
  source: AssignmentDoc["source"];
  status: AssignmentDoc["status"];
  /** A piece of work for this assignment has been approved. */
  approved: boolean;
  submission: { id: string; attempt: number; status: SubmissionStatus; call_needed: boolean } | null;
}

export interface Milestone {
  key: MilestoneKey;
  title: TextMap;
  detail: TextMap;
  assignments: MilestoneAssignment[];
  done: number;
  total: number;
  state: "open" | "active" | "done";
}

export interface MilestonesView {
  journey_id: string;
  career: CareerCard;
  journey_state: JourneyState;
  has_mentor: boolean;
  side: "student" | "teacher";
  /** Pieces of work waiting for the mentor (mentor's view). */
  waiting: number;
  milestones: Milestone[];
}

export interface WorkReview {
  /** `pass`, `return` and `feedback` come from the AI (a learner with no mentor); `approve` is a mentor's. */
  decision: "approve" | "return" | "pass" | "feedback";
  /** true when the AI reviewed it. Practice feedback only: it never counts as a mentor's approval. */
  by_ai: boolean;
  /** null: the AI could not judge that criterion from the written answer. */
  scores: Record<string, number | null>;
  feedback: string;
  /** After two returns the mentor is asked to call the learner. */
  call_needed: boolean;
  reviewed_at: string;
}

export interface AiScoreDraft {
  /** null: the AI could not judge that criterion from the written answer. */
  scores: Record<string, number | null>;
  feedback: string;
  source: string;
  model: string;
  /** Always false: the draft is made from the written answer only. */
  photos_seen: boolean;
}

export interface Submission {
  id: string;
  assignment_id: string;
  attempt: number;
  status: SubmissionStatus;
  text: string;
  via: "typed" | "voice";
  photos: string[];
  created_at: string;
  sent_at: string | null;
  review: WorkReview | null;
  ack: "yes" | "no" | null;
  /** Mentor's view only. An audit sample never shows the AI draft. */
  audit_sample?: boolean;
  ai_draft?: AiScoreDraft | null;
}

export interface AssignmentDetail {
  assignment: AssignmentDoc;
  side: "student" | "teacher";
  has_mentor: boolean;
  journey_state: JourneyState;
  career: { career_id: string; safety_class: "low" | "medium" | "high" };
  submissions: Submission[];
  /** The learner may save or start work now. */
  can_work: boolean;
  approved: boolean;
  ai_passed: boolean;
}

export interface QueueItem {
  id: string;
  attempt: number;
  sent_at: string;
  milestone: MilestoneKey;
  photos: number;
  assignment: { id: string; title: TextMap };
  student: { name: string; age_band: string | null; grade: number | null };
}

export interface SubmissionDetail {
  submission: Submission;
  assignment: AssignmentDoc;
  side: "student" | "teacher";
  career: { career_id: string; safety_class: "low" | "medium" | "high" };
}

export interface AssignmentWrite {
  lang: Lang;
  title: string;
  instructions: string;
  criteria: string[];
}

export const getMilestones = (journeyId: string) => request<MilestonesView>(`/journeys/${journeyId}/milestones`);
export const draftAssignments = (journeyId: string, key: MilestoneKey) =>
  request<{ assignments: AssignmentDoc[] }>(`/journeys/${journeyId}/milestones/${key}/assignments:draft`, { method: "POST" });
export const createAssignment = (journeyId: string, key: MilestoneKey, body: AssignmentWrite) =>
  request<AssignmentDoc>(`/journeys/${journeyId}/milestones/${key}/assignments`, { method: "POST", body });
export const patchAssignment = (id: string, body: Partial<AssignmentWrite> & { status?: "approved" | "retired" }) =>
  request<AssignmentDoc>(`/assignments/${id}`, { method: "PATCH", body });
export const getAssignmentDetail = (id: string) => request<AssignmentDetail>(`/assignments/${id}`);

export const saveWork = (assignmentId: string, text: string, via: "typed" | "voice") =>
  request<Submission>(`/assignments/${assignmentId}/submissions`, { method: "POST", body: { text, via } });
export const uploadWorkPhoto = (submissionId: string, photo: Blob) => {
  const form = new FormData();
  form.append("file", photo, "work.jpg");
  return request<{ id: string }>(`/submissions/${submissionId}/photos`, { method: "POST", body: form });
};
export const deleteWorkPhoto = (submissionId: string, photoId: string) =>
  request<void>(`/submissions/${submissionId}/photos/${photoId}`, { method: "DELETE" });
export const fetchWorkPhoto = async (submissionId: string, photoId: string): Promise<Blob> =>
  (await requestRaw(`/submissions/${submissionId}/photos/${photoId}`, { accept: "image/jpeg" })).blob();
export const sendWork = (submissionId: string) => request<Submission>(`/submissions/${submissionId}/send`, { method: "POST" });
export const ackWork = (submissionId: string, answer: "yes" | "no") =>
  request<Submission>(`/submissions/${submissionId}/ack`, { method: "POST", body: { answer } });

export const getReviewQueue = () => request<{ items: QueueItem[] }>("/teachers/me/review-queue");
export const getSubmissionDetail = (id: string) => request<SubmissionDetail>(`/submissions/${id}`);
export const aiScoreDraft = (id: string) => request<AiScoreDraft>(`/submissions/${id}/ai-draft`, { method: "POST" });
export const reviewWork = (id: string, body: { decision: "approve" | "return"; scores: Record<string, number>; feedback: string }) =>
  request<{ submission: Submission }>(`/submissions/${id}/review`, { method: "POST", body });

// ---------------------------------------------------------------------------
// Finishing a path, opportunities, applications, the job pack and the inbox (M8)
// ---------------------------------------------------------------------------

export type OpportunityKind = "apprenticeship" | "training" | "enterprise" | "exam" | "portal" | "internship";
/** How clearly the programme says it pays. Only the kind is known, never an amount. */
export type OpportunityIncome = "stipend" | "support" | "none" | "unknown";
export type OpportunityReason =
  | "your_path"
  | "any_path"
  | "in_district"
  | "other_district"
  | "in_state"
  | "other_state"
  | "anywhere"
  | "pays_stipend"
  | "gives_support"
  | "eligible"
  | "check_office";
/** interested and mentor_assisted are set by the learner asking or the mentor helping. Only the learner sets applied and confirmed. */
export type ApplicationStatus = "interested" | "mentor_assisted" | "applied" | "confirmed" | "withdrawn";

export interface OpportunityEligibility {
  status: SchemeStatus;
  passed: SchemeCondition[];
  failed: SchemeCondition[];
  missing: SchemeCondition[];
  unresolved: SchemeCondition[];
  opens_at: { fact: "age" | "grade"; value: number }[];
  stale: boolean;
  expired: boolean;
}

export interface OpportunityCard {
  id: string;
  kind: OpportunityKind;
  title: PartialLocalised;
  summary: PartialLocalised;
  how: PartialLocalised;
  scope: "national" | "state";
  income: OpportunityIncome;
  apply_url: string;
  docs: string[];
  needs: SchemeFactKey[];
  machine_translated: Lang[];
  score: number;
  factors: Record<string, number>;
  reasons: OpportunityReason[];
  eligibility: OpportunityEligibility;
  source: SchemeSource;
  application: { id: string; status: ApplicationStatus } | null;
}

export interface OpportunityList {
  journey: { id: string; state: JourneyState; career_id: string };
  top: OpportunityCard[];
  more: OpportunityCard[];
  not_yet: OpportunityCard[];
  ask: SchemeFactKey[];
  weights: Record<string, number>;
  /** A high-risk trade: a qualified assessor must check the work in person. KHOJ does not certify. */
  in_person_check_needed: boolean;
  /** Before the path is finished only a few are sent. `locked` counts the ones held back, never their names. */
  unlock: { finished: boolean; approved: number; total: number; locked: number; has_mentor: boolean };
}

export interface Application {
  id: string;
  opportunity_id: string;
  status: ApplicationStatus;
  mentor_helped: boolean;
  created_at: string;
  updated_at: string;
  title?: PartialLocalised;
  apply_url?: string;
  kind?: OpportunityKind;
}

export interface TeacherApplication extends Application {
  student: { name: string; age_band: string | null };
}

export interface Completion {
  journey_id: string;
  state: JourneyState;
  career_id: string;
  in_person_check_needed: boolean;
}

export interface JobPack {
  career_id: string;
  documents: { asked: string[]; usual: string[] };
  steps: { opportunity_id: string; title: PartialLocalised; how: PartialLocalised; apply_url: string; source: { title: string; url: string; verified_on: string | null } }[];
  pitch: string[];
  courses: { id: string; title: string; provider: string; url: string; rung: string | null; verified_on: string | null }[];
  learn_links: { title: string; provider: string; url: string; language: string }[];
  safety: { class: "low" | "medium" | "high"; in_person_check_needed: boolean };
  machine_translated: Lang[];
}

export type NotificationKind = "mentor_request" | "mentor_accepted" | "mentor_declined" | "work_sent" | "review_ready" | "path_complete" | "help_apply" | "mentor_helped";

export interface AppNotification {
  id: string;
  kind: NotificationKind;
  params: Record<string, string>;
  link: string;
  read: boolean;
  created_at: string;
}

export const completeJourney = (journeyId: string) => request<Completion>(`/journeys/${journeyId}/complete`, { method: "POST" });
export const getOpportunities = () => request<OpportunityList>("/opportunities");
export const checkOpportunities = (facts: SchemeFacts) => request<OpportunityList>("/opportunities/check", { method: "POST", body: { facts } });
export const applyTo = (opportunityId: string) => request<{ application: Application }>(`/opportunities/${opportunityId}/apply`, { method: "POST" });
export const getMyApplications = () => request<{ applications: Application[] }>("/applications/me");
export const setApplicationStatus = (id: string, status: "applied" | "confirmed" | "withdrawn") =>
  request<{ application: Application }>(`/applications/${id}`, { method: "PATCH", body: { status } });
export const getTeacherApplications = () => request<{ applications: TeacherApplication[] }>("/teachers/me/applications");
export const assistApplication = (id: string) => request<{ application: Application }>(`/applications/${id}/assist`, { method: "POST" });
export const getJobPack = (careerId: string) => request<JobPack>(`/careers/${careerId}/pack`);

export const getNotifications = () => request<{ items: AppNotification[]; unread: number }>("/notifications");
export const getUnreadCount = () => request<{ unread: number }>("/notifications/unread");
export const markNotificationRead = (id: string) => request<{ notification: AppNotification; unread: number }>(`/notifications/${id}/read`, { method: "POST" });
export const markAllNotificationsRead = () => request<{ unread: number }>("/notifications/read-all", { method: "POST" });

// ---------------------------------------------------------------------------
// A day in the life: career calls between a learner and a mentor verified in the skill
// ---------------------------------------------------------------------------

export type CallContactKind = "link" | "phone";
export type CallOutcome = "held" | "missed";

export interface CallHost {
  teacher_id: string;
  name: string;
  roles: TeacherRole[];
  languages: Lang[];
  district: string;
  block: string;
  /** Skills the mentor has verified that this career needs. It is skill, not employment. */
  verified_in: { id: string; name: Localised }[];
  speaks_your_language: boolean | null;
}

export interface CallTime {
  id: string;
  career_id: string;
  starts_at: string;
  minutes: 30 | 45;
  ended: boolean;
}

export interface OpenCall extends CallTime {
  host: CallHost;
}

/** A call the learner booked. Only here does the contact appear. */
export interface MyCall extends CallTime {
  career_name: Localised;
  host: CallHost | null;
  contact_kind: CallContactKind;
  contact: string;
  outcome: CallOutcome | null;
  rating: number | null;
}

export interface CallsOverview {
  career_id: string;
  career_name: Localised;
  needs_guardian: boolean;
  can_book: boolean;
  slots: OpenCall[];
  upcoming: MyCall[];
  past: MyCall[];
}

export interface HostSlot extends CallTime {
  career_name: Localised;
  status: "open" | "booked" | "cancelled";
  contact_kind: CallContactKind;
  contact: string;
  learner: { first_name: string; age_band: string | null; language: Lang; guardian_near: boolean } | null;
  outcome: CallOutcome | null;
  rating: number | null;
}

export interface HostCalls {
  offers_calls: boolean;
  can_host: boolean;
  careers: { career_id: string; name: Localised; verified_in: { id: string; name: Localised }[] }[];
  upcoming: HostSlot[];
  past: HostSlot[];
  limits: { max_open: number; minutes: number[] };
}

export interface NewCallSlot {
  career_id: string;
  starts_at: string;
  minutes: 30 | 45;
  contact_kind: CallContactKind;
  contact: string;
}

export const getCalls = () => request<CallsOverview>("/calls");
export const bookCall = (id: string, body: { agreed: boolean; guardian_near: boolean }) => request<MyCall>(`/calls/${id}/book`, { method: "POST", body });
export const cancelCall = (id: string) => request<{ cancelled: true }>(`/calls/${id}/cancel`, { method: "POST" });
export const sendCallFeedback = (id: string, body: { took_place: boolean; rating?: number }) => request<MyCall>(`/calls/${id}/feedback`, { method: "POST", body });

export const getHostCalls = () => request<HostCalls>("/teachers/me/calls");
export const setOfferingCalls = (offers_calls: boolean) => request<HostCalls>("/teachers/me/calls", { method: "PATCH", body: { offers_calls } });
export const addCallSlot = (body: NewCallSlot) => request<HostSlot>("/teachers/me/calls/slots", { method: "POST", body });
export const cancelCallSlot = (id: string) => request<HostSlot>(`/teachers/me/calls/slots/${id}/cancel`, { method: "POST" });

// ---------------------------------------------------------------------------
// Connect: adult learners with similar goals introduce themselves, then talk outside KHOJ
// ---------------------------------------------------------------------------

/** What another learner sees: a first name, the state, the path and the skills. No surname, place or contact. */
export interface PeerCard {
  card_id: string;
  first_name: string;
  state: string | null;
  career_id: string | null;
  career_name: Localised | null;
  skills: { id: string; name: Localised }[];
  shared_skills: string[];
  same_path: boolean;
}

export interface MyCard {
  visible: boolean;
  reach_kind: CallContactKind;
  reach: string;
}

export interface PeerConnection {
  id: string;
  card: PeerCard;
  /** Only while the other person's card is on. */
  reach_kind: CallContactKind | null;
  reach: string | null;
}

export type ConnectOverview =
  | { eligible: false; opens_at: number }
  | {
      eligible: true;
      career_id: string;
      career_name: Localised;
      me: MyCard;
      my_skills: { id: string; name: Localised }[];
      suggestions: PeerCard[];
      incoming: { id: string; card: PeerCard }[];
      outgoing: { id: string; card: PeerCard }[];
      connections: PeerConnection[];
      requests_left: number;
      limits: { per_day: number };
    };

export type ReportReason = "pressure" | "unsafe" | "spam" | "other";

export const getConnect = () => request<ConnectOverview>("/connect");
export const setMyCard = (body: MyCard & { agreed: boolean }) => request<ConnectOverview>("/connect/me", { method: "PUT", body });
export const requestConnect = (cardId: string) => request<{ id: string; status: string }>(`/connect/${cardId}/request`, { method: "POST" });
export const answerConnect = (id: string, action: "accept" | "decline" | "cancel") => request<{ id: string; status: string }>(`/connect/requests/${id}/${action}`, { method: "POST" });
export const removeConnection = (id: string) => request<{ id: string; status: string }>(`/connect/connections/${id}/remove`, { method: "POST" });
export const blockPerson = (cardId: string) => request<{ blocked: true }>(`/connect/${cardId}/block`, { method: "POST" });
export const reportPerson = (cardId: string, reason: ReportReason) => request<{ blocked: true; reported: true }>(`/connect/${cardId}/report`, { method: "POST", body: { reason } });
