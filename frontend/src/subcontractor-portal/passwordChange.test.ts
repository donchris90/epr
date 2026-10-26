import { describe, it, expect, vi, beforeEach } from "vitest";
import { changeSubcontractorPassword } from "./hooks";
import { subcontractorPortalClient } from "./api/client";
import { getPortalAccessToken, getPortalRefreshToken, setPortalTokens } from "./lib/auth";

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("changeSubcontractorPassword", () => {
  it("keeps this browser signed in with the fresh tokens the server returns", async () => {
    setPortalTokens("old-access", "old-refresh");
    const post = vi.spyOn(subcontractorPortalClient, "post").mockResolvedValue({ data: { status: "password updated", access_token: "new-access", refresh_token: "new-refresh" } });
    await changeSubcontractorPassword("old pass", "new pass 123");
    expect(post).toHaveBeenCalledWith("/scp/auth/me/password", { current_password: "old pass", new_password: "new pass 123" });
    expect(getPortalAccessToken()).toBe("new-access");
    expect(getPortalRefreshToken()).toBe("new-refresh");
  });

  it("leaves the stored tokens alone when the response has none", async () => {
    setPortalTokens("old-access", "old-refresh");
    vi.spyOn(subcontractorPortalClient, "post").mockResolvedValue({ data: { status: "password updated" } });
    await changeSubcontractorPassword("a", "b");
    expect(getPortalAccessToken()).toBe("old-access");
  });

  it("does not touch tokens when the change is refused", async () => {
    setPortalTokens("old-access", "old-refresh");
    vi.spyOn(subcontractorPortalClient, "post").mockRejectedValue({ response: { status: 401 } });
    await expect(changeSubcontractorPassword("wrong", "new pass 123")).rejects.toBeTruthy();
    expect(getPortalAccessToken()).toBe("old-access");
  });
});
