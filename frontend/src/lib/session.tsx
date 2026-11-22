import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  clearTokens,
  getStudent,
  getTeacher,
  isApiFailure,
  readRefreshToken,
  refreshSession,
  saveLanguage,
  setSessionLostHandler,
  signOut as apiSignOut,
  type StudentProfile,
  type TeacherProfile,
  type Tokens,
  type User,
} from "./api";
import { isLang, setLang } from "./i18n";

export type Profile = { kind: "student"; data: StudentProfile } | { kind: "teacher"; data: TeacherProfile } | null;
type Status = "loading" | "anonymous" | "ready" | "unavailable";

interface SessionValue {
  status: Status;
  user: User | null;
  profile: Profile;
  /** Called after a successful code check. */
  signIn: (tokens: Tokens) => Promise<void>;
  /** Re-reads the user and profile (after saving a profile). */
  reload: () => Promise<void>;
  signOut: () => Promise<void>;
  retry: () => void;
}

const SessionContext = createContext<SessionValue | null>(null);

async function loadProfile(user: User): Promise<Profile> {
  if (user.profile === "student") return { kind: "student", data: await getStudent() };
  if (user.profile === "teacher") return { kind: "teacher", data: await getTeacher() };
  return null;
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>("loading");
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<Profile>(null);

  const adopt = useCallback(async (next: User) => {
    setUser(next);
    if (isLang(next.language)) setLang(next.language);
    setProfile(await loadProfile(next));
    setStatus("ready");
  }, []);

  const end = useCallback(() => {
    clearTokens();
    setUser(null);
    setProfile(null);
    setStatus("anonymous");
  }, []);

  const boot = useCallback(async () => {
    if (!readRefreshToken()) {
      setStatus("anonymous");
      return;
    }
    setStatus("loading");
    try {
      const tokens = await refreshSession();
      await adopt(tokens.user);
    } catch (err) {
      if (isApiFailure(err) && err.status === 401) end();
      else setStatus("unavailable");
    }
  }, [adopt, end]);

  useEffect(() => {
    void boot();
  }, [boot]);

  useEffect(() => {
    setSessionLostHandler(end);
    return () => setSessionLostHandler(null);
  }, [end]);

  const signIn = useCallback(async (tokens: Tokens) => adopt(tokens.user), [adopt]);

  const reload = useCallback(async () => {
    const tokens = await refreshSession();
    setUser(tokens.user);
    setProfile(await loadProfile(tokens.user));
  }, []);

  const signOut = useCallback(async () => {
    await apiSignOut();
    end();
  }, [end]);

  // Keep the server's language in step with the switch, once signed in.
  useEffect(() => {
    if (status !== "ready" || !user) return;
    let last = document.documentElement.lang;
    const observer = new MutationObserver(() => {
      const lang = document.documentElement.lang;
      if (lang !== last && isLang(lang)) {
        last = lang;
        void saveLanguage(lang).catch(() => undefined);
      }
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["lang"] });
    return () => observer.disconnect();
  }, [status, user]);

  const value = useMemo<SessionValue>(
    () => ({ status, user, profile, signIn, reload, signOut, retry: () => void boot() }),
    [status, user, profile, signIn, reload, signOut, boot],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside SessionProvider");
  return ctx;
}

