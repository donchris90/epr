import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useChangeClientPassword } from "./hooks";
import { clientPortalClient } from "./api/client";
import { getClientAccessToken, getClientRefreshToken, setClientTokens } from "./lib/auth";

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}>{children}</QueryClientProvider>
);

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("useChangeClientPassword", () => {
  it("stores the fresh tokens so this session survives the change", async () => {
    setClientTokens("old-access", "old-refresh");
    const post = vi.spyOn(clientPortalClient, "post").mockResolvedValue({ data: { status: "password updated", access_token: "new-access", refresh_token: "new-refresh" } });
    const { result } = renderHook(() => useChangeClientPassword(), { wrapper });
    result.current.mutate({ current_password: "a", new_password: "b" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(post).toHaveBeenCalledWith("/clp/auth/me/password", { current_password: "a", new_password: "b" });
    expect(getClientAccessToken()).toBe("new-access");
    expect(getClientRefreshToken()).toBe("new-refresh");
  });

  it("keeps the old tokens when the change fails", async () => {
    setClientTokens("old-access", "old-refresh");
    vi.spyOn(clientPortalClient, "post").mockRejectedValue({ response: { status: 401 } });
    const { result } = renderHook(() => useChangeClientPassword(), { wrapper });
    result.current.mutate({ current_password: "x", new_password: "yyyyyyyy" });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(getClientAccessToken()).toBe("old-access");
  });
});
