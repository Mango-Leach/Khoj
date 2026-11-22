import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Node has no localStorage; give the client an in-memory one.
const store = new Map<string, string>();
vi.stubGlobal("localStorage", {
  getItem: (k: string) => store.get(k) ?? null,
  setItem: (k: string, v: string) => void store.set(k, v),
  removeItem: (k: string) => void store.delete(k),
});

const { ApiFailure, clearTokens, getMe, setSessionLostHandler, storeTokens } = await import("./api");

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const tokens = (n: number) => ({
  access_token: `access-${n}`,
  refresh_token: `refresh-${n}`,
  expires_in: 900,
  user: { id: "u1", roles: ["student"], language: "en", profile: "student" },
});

describe("api client", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    store.clear();
    clearTokens();
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });
  afterEach(() => setSessionLostHandler(null));

  it("turns the server's error shape into an ApiFailure", async () => {
    fetchMock.mockResolvedValueOnce(json(401, { code: "invalid_token", message: "m", hint: "h", attempts_left: 2 }));
    await expect(getMe()).rejects.toMatchObject({ status: 401, code: "invalid_token", hint: "h", extra: { attempts_left: 2 } });
  });

  it("reports a lost connection as code 'network'", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    await expect(getMe()).rejects.toBeInstanceOf(ApiFailure);
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    await expect(getMe()).rejects.toMatchObject({ code: "network", status: 0 });
  });

  it("refreshes once on 401 and retries with the new token", async () => {
    storeTokens(tokens(1));
    fetchMock
      .mockResolvedValueOnce(json(401, { code: "invalid_token" }))
      .mockResolvedValueOnce(json(200, tokens(2)))
      .mockResolvedValueOnce(json(200, tokens(2).user));
    const me = await getMe();
    expect(me.id).toBe("u1");
    expect(fetchMock).toHaveBeenCalledTimes(3);
    const retry = fetchMock.mock.calls[2][1] as RequestInit;
    expect((retry.headers as Record<string, string>).Authorization).toBe("Bearer access-2");
    expect(store.get("khoj.refresh")).toBe("refresh-2");
  });

  it("shares one refresh between parallel requests", async () => {
    storeTokens(tokens(1));
    let refreshCalls = 0;
    fetchMock.mockImplementation(async (url: string, init: RequestInit) => {
      if (url.endsWith("/auth/refresh")) {
        refreshCalls += 1;
        return json(200, tokens(2));
      }
      const auth = (init.headers as Record<string, string>).Authorization;
      return auth === "Bearer access-2" ? json(200, tokens(2).user) : json(401, { code: "invalid_token" });
    });
    await Promise.all([getMe(), getMe(), getMe()]);
    expect(refreshCalls).toBe(1);
  });

  it("ends the session when the refresh token is rejected", async () => {
    const lost = vi.fn();
    setSessionLostHandler(lost);
    storeTokens(tokens(1));
    fetchMock
      .mockResolvedValueOnce(json(401, { code: "invalid_token" }))
      .mockResolvedValueOnce(json(401, { code: "invalid_refresh_token" }));
    await expect(getMe()).rejects.toMatchObject({ code: "invalid_refresh_token" });
    expect(lost).toHaveBeenCalledOnce();
    expect(store.has("khoj.refresh")).toBe(false);
  });

  it("keeps the refresh token when the server is merely down", async () => {
    storeTokens(tokens(1));
    fetchMock
      .mockResolvedValueOnce(json(401, { code: "invalid_token" }))
      .mockResolvedValueOnce(json(503, { code: "db_unavailable" }));
    await expect(getMe()).rejects.toMatchObject({ code: "db_unavailable" });
    expect(store.get("khoj.refresh")).toBe("refresh-1");
  });
});
