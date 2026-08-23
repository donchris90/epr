import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import SubcontractorPortalApp from "./index";
import { subcontractorPortalClient } from "./api/client";
import { clearPortalSession } from "./lib/auth";

/**
 * E2E-style walk through the real subcontractor portal build: login,
 * unauthorized redirect, dashboard, agreement detail (progress +
 * claim submission), logout. Mocks only the HTTP boundary
 * (subcontractorPortalClient) -- everything else (routing, auth
 * guard, localStorage token storage, the actual page components) is
 * real, exercised exactly as a browser would. Deliberately mirrors
 * client-portal/ClientPortal.e2e.test.tsx's own established, proven
 * pattern -- including its own real /portal/* nesting fix, applied
 * here from the start (rendering SubcontractorPortalApp directly
 * without the matching /subcontractor/* parent route would reproduce
 * the exact infinite-redirect-loop bug found and fixed in that file
 * earlier this session).
 */
vi.mock("./api/client", () => ({
  subcontractorPortalClient: { get: vi.fn(), post: vi.fn() },
  getSubcontractorPortalErrorMessage: vi.fn((err: any) => err?.response?.data?.title || "Something went wrong."),
}));

const AGREEMENT = {
  id: "agr-1",
  subcontractor_id: "sub-1",
  contract_id: null,
  agreement_number: "SC-001",
  value: "500000.00",
  currency: "NGN",
  payment_terms_summary: "Net 30",
  retention_percentage: "5.00",
  status: "active",
};

function fakeJwt(payload: Record<string, unknown>) {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const body = btoa(JSON.stringify(payload));
  return `${header}.${body}.fake-signature`;
}

const ACCESS_TOKEN = fakeJwt({ user_id: "portal-user-1", tenant_id: "tenant-1", is_portal_user: true });

function mockGet(url: string, config?: any) {
  if (url === "/scp/auth/me") {
    return Promise.resolve({ data: { id: "portal-user-1", subcontractor_id: "sub-1", email: "sub@example.com", is_active: true } });
  }
  if (url === "/scp/portal-users/portal-user-1/agreements" && !config?.params) {
    return Promise.resolve({ data: { data: [AGREEMENT] } });
  }
  if (url === "/scp/portal-users/portal-user-1/agreements/agr-1") {
    return Promise.resolve({ data: AGREEMENT });
  }
  if (url === "/scp/portal-users/portal-user-1/progress-entries") {
    return Promise.resolve({ data: { data: [] } });
  }
  if (url === "/scp/portal-users/portal-user-1/payment-certificates") {
    return Promise.resolve({ data: { data: [] } });
  }
  if (url === "/scp/portal-users/portal-user-1/claims") {
    return Promise.resolve({ data: { data: [] } });
  }
  return Promise.reject(new Error(`unexpected GET ${url}`));
}

function renderApp(initialPath = "/subcontractor/login") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/subcontractor/*" element={<SubcontractorPortalApp />} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  clearPortalSession();
  vi.mocked(subcontractorPortalClient.get).mockImplementation(mockGet as any);
  vi.mocked(subcontractorPortalClient.post).mockImplementation((url: string) => {
    if (url === "/scp/auth/login") {
      return Promise.resolve({ data: { access_token: ACCESS_TOKEN, refresh_token: "fake-refresh-token" } });
    }
    return Promise.reject(new Error(`unexpected POST ${url}`));
  });
});

describe("Subcontractor portal — unauthorized", () => {
  it("redirects an unauthenticated visitor straight to login", async () => {
    renderApp("/subcontractor/dashboard");
    expect(await screen.findByPlaceholderText("you@yourcompany.com")).toBeInTheDocument();
  });
});

describe("Subcontractor portal — login", () => {
  it("logs in and reaches the real dashboard with real agreement data", async () => {
    const user = userEvent.setup();
    renderApp();

    await user.type(screen.getByPlaceholderText("you@yourcompany.com"), "sub@example.com");
    await user.type(screen.getByPlaceholderText("••••••••"), "realpassword123");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText("SC-001")).toBeInTheDocument();
    expect(subcontractorPortalClient.post).toHaveBeenCalledWith("/scp/auth/login", { email: "sub@example.com", password: "realpassword123" });
  });

  it("shows a real error and does not navigate on invalid credentials", async () => {
    vi.mocked(subcontractorPortalClient.post).mockRejectedValueOnce({ response: { data: { title: "Invalid credentials" } } });
    const user = userEvent.setup();
    renderApp();

    await user.type(screen.getByPlaceholderText("you@yourcompany.com"), "sub@example.com");
    await user.type(screen.getByPlaceholderText("••••••••"), "wrongpassword");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText("Invalid credentials")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("you@yourcompany.com")).toBeInTheDocument();
  });
});

describe("Subcontractor portal — agreement detail and claim submission", () => {
  async function loginAndOpenAgreement(user: ReturnType<typeof userEvent.setup>) {
    renderApp();
    await user.type(screen.getByPlaceholderText("you@yourcompany.com"), "sub@example.com");
    await user.type(screen.getByPlaceholderText("••••••••"), "realpassword123");
    await user.click(screen.getByRole("button", { name: /sign in/i }));
    await user.click(await screen.findByText("SC-001"));
  }

  it("walks dashboard -> agreement detail -> real claim submission", async () => {
    const user = userEvent.setup();
    vi.mocked(subcontractorPortalClient.post).mockImplementation((url: string, body?: any) => {
      if (url === "/scp/auth/login") {
        return Promise.resolve({ data: { access_token: ACCESS_TOKEN, refresh_token: "fake-refresh-token" } });
      }
      if (url === "/scp/portal-users/portal-user-1/claims") {
        return Promise.resolve({
          data: { id: "claim-1", agreement_id: "agr-1", claim_type: body?.claim_type, description: body?.description, claimed_amount: body?.claimed_amount ?? null, claimed_days: null, status: "pending", submitted_at: "2026-08-23T00:00:00Z", response_notes: null },
        });
      }
      return Promise.reject(new Error(`unexpected POST ${url}`));
    });

    await loginAndOpenAgreement(user);
    expect(await screen.findByText(/payment certificates/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /new claim/i }));
    await user.type(screen.getByPlaceholderText("Describe the claim"), "Extra scope requested by site team");
    await user.click(screen.getByRole("button", { name: /submit claim/i }));

    await waitFor(() => {
      expect(subcontractorPortalClient.post).toHaveBeenCalledWith(
        "/scp/portal-users/portal-user-1/claims",
        expect.objectContaining({ agreement_id: "agr-1", description: "Extra scope requested by site team" })
      );
    });
  });

  it("submits real progress with a real quantity", async () => {
    const user = userEvent.setup();
    vi.mocked(subcontractorPortalClient.post).mockImplementation((url: string, body?: any) => {
      if (url === "/scp/auth/login") {
        return Promise.resolve({ data: { access_token: ACCESS_TOKEN, refresh_token: "fake-refresh-token" } });
      }
      if (url === "/scp/portal-users/portal-user-1/progress-entries") {
        return Promise.resolve({
          data: { id: "prog-1", agreement_id: "agr-1", scope_item_id: null, submitted_quantity: body?.submitted_quantity, submitted_at: "2026-08-23T00:00:00Z", status: "pending" },
        });
      }
      return Promise.reject(new Error(`unexpected POST ${url}`));
    });

    await loginAndOpenAgreement(user);
    await user.type(await screen.findByPlaceholderText("0.00"), "125.5");
    await user.click(screen.getByRole("button", { name: /submit progress/i }));

    await waitFor(() => {
      expect(subcontractorPortalClient.post).toHaveBeenCalledWith(
        "/scp/portal-users/portal-user-1/progress-entries",
        expect.objectContaining({ agreement_id: "agr-1", submitted_quantity: "125.5" })
      );
    });
  });
});

describe("Subcontractor portal — logout", () => {
  it("real sign-out clears the session and returns to login", async () => {
    const user = userEvent.setup();
    vi.mocked(subcontractorPortalClient.post).mockImplementation((url: string) => {
      if (url === "/scp/auth/login") {
        return Promise.resolve({ data: { access_token: ACCESS_TOKEN, refresh_token: "fake-refresh-token" } });
      }
      if (url === "/scp/auth/logout") {
        return Promise.resolve({ data: { status: "logged out" } });
      }
      return Promise.reject(new Error(`unexpected POST ${url}`));
    });

    renderApp();
    await user.type(screen.getByPlaceholderText("you@yourcompany.com"), "sub@example.com");
    await user.type(screen.getByPlaceholderText("••••••••"), "realpassword123");
    await user.click(screen.getByRole("button", { name: /sign in/i }));
    await screen.findByText("SC-001");

    await user.click(screen.getByText("Sign out"));

    expect(await screen.findByPlaceholderText("you@yourcompany.com")).toBeInTheDocument();
  });
});
