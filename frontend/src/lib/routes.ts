import type { User } from "./api";

export function homePath(profile: "student" | "teacher"): string {
  return profile === "teacher" ? "/t/home" : "/home";
}

/** Where a signed-in user belongs right now: finish the profile, then home. */
export function landingPath(user: User): string {
  if (!user.profile) return "/role";
  return homePath(user.profile);
}

/** Where the landing page's buttons lead: the signed-in learner or mentor goes back to their own home, anyone else to sign-in. */
export function entryPath(user: User | null): string {
  return user ? landingPath(user) : "/login";
}
