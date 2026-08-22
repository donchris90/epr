import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ClientPortalApp from "./index";
import { clientPortalClient } from "./api/client";
import { clearClientSession } from "./lib/auth";

/**
 * E2E-style walk through the real client portal build, per the
 * brief's own sequence: login -> dashboard -> project -> progress ->
 * document -> certificate -> approval. Mocks only the HTTP boundary
 * (clientPortalClient) -- everything else (routing, auth guard,
 * localStorage token storage, react-query, the actual page
 * components) is real, exercised exactly as a browser would.
 */
vi.mock("./api/client", () => ({
  clientPortalClient: { get: vi.fn(), post: vi.fn() },
  getClientPortalErrorMessage: vi.fn(),
}));

const PROJECT = {
  id: "proj-1",
  name: "Lekki Tower",
  status: "active",
  start_date: "2026-01-01",
  end_date: null,
};

const PROJECT_DETAIL = { ...PROJECT, contract_value: "1000000.00", currency: "NGN" };

const DOCUMENT = {
  id: "doc-1",
  original_filename: "Signed Contract.pdf",
  doc_type: "contract",
  status: "uploaded",
  created_at: "2026-01-05T00:00:00Z",
};

const CERTIFICATE = {
  id: "cert-1",
  certificate_number: "PC-001",
  period_start: "2026-01-01",
  period_end: "2026-01-31",
  gross_certified_amount: "500000.00",
  retention_withheld: "25000.00",
  net_payable: "475000.00",
  status: "submitted",
};

// A structurally-real (if not cryptographically real) JWT so
// hooks.ts:meId() can decode a user_id out of it exactly as it would
// from a real backend-issued token.
function fakeJwt(payload: Record<string, unknown>) {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const body = btoa(JSON.stringify(payload));
  return `${header}.${body}.fake-signature`;
}

const ACCESS_TOKEN = fakeJwt({ user_id: "client-1", tenant_id: "tenant-1", is_client: true });

function mockGet(url: string) {
  if (url === "/clp/auth/me") {
    return Promise.resolve({ data: { id: "client-1", client_organization_name: "Acme Developments", email: "client@example.com" } });
  }
  if (url === "/clp/client-users/client-1/projects") {
    return Promise.resolve({ data: { data: [PROJECT] } });
  }
  if (url === "/clp/client-users/client-1/projects/proj-1") {
    return Promise.resolve({ data: PROJECT_DETAIL });
  }
  if (url === "/clp/client-users/client-1/projects/proj-1/progress") {
    return Promise.resolve({ data: { overall_percent_complete: 42.5, activity_count: 10, critical_activity_count: 2 } });
  }
  if (url === "/clp/client-users/client-1/projects/proj-1/documents") {
    return Promise.resolve({ data: { data: [DOCUMENT] } });
  }
  if (url === "/clp/client-users/client-1/projects/proj-1/certificates") {
    return Promise.resolve({ data: { data: [CERTIFICATE] } });
  }
  if (url === "/clp/client-users/client-1/projects/proj-1/variation-orders") {
    return Promise.resolve({ data: { data: [] } });
  }
  if (url === "/clp/client-users/client-1/projects/proj-1/requests") {
    return Promise.resolve({ data: { data: [] } });
  }
  if (url === "/clp/client-users/client-1/projects/proj-1/site-media") {
    return Promise.resolve({ data: { diary_summaries: [], media: [] } });
  }
  if (url === "/clp/client-users/client-1/approval-actions") {
    return Promise.resolve({ data: { data: [] } });
  }
  if (url === "/clp/client-users/client-1/projects/proj-1/documents/doc-1/download") {
    return Promise.resolve({ data: { download_url: "https://files.example.com/doc-1.pdf" } });
  }
  return Promise.reject(new Error(`Unmocked GET ${url}`));
}

function renderApp(initialPath = "/portal/login") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/portal/*" element={<ClientPortalApp />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  clearClientSession();
  vi.mocked(clientPortalClient.get).mockImplementation(mockGet as any);
  vi.mocked(clientPortalClient.post).mockImplementation((url: string, body?: any) => {
    if (url === "/clp/auth/login") {
      return Promise.resolve({ data: { access_token: ACCESS_TOKEN, refresh_token: "fake-refresh-token" } });
    }
    if (url === "/clp/client-users/client-1/certificates/cert-1/decide") {
      return Promise.resolve({
        data: { id: "action-1", action_type: "progress_certificate", target_id: "cert-1", decision: body?.decision ?? "approved", decided_at: "2026-02-01T00:00:00Z" },
      });
    }
    return Promise.reject(new Error(`Unmocked POST ${url}`));
  });
  // window.open isn't implemented in jsdom -- the Documents tab calls
  // it to open the downloaded file, so this just needs to exist,
  // same as any real browser API jsdom doesn't provide.
  window.open = vi.fn();
});

describe("Client portal end-to-end flow", () => {
  it("logs in, reaches the dashboard, and shows the assigned project", async () => {
    const user = userEvent.setup();
    renderApp();

    await screen.findByPlaceholderText("you@yourcompany.com");
    await user.type(screen.getByPlaceholderText("you@yourcompany.com"), "client@example.com");
    await user.type(screen.getByPlaceholderText("••••••••"), "correct password");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText("Lekki Tower")).toBeInTheDocument();
    expect(clientPortalClient.post).toHaveBeenCalledWith("/clp/auth/login", {
      email: "client@example.com",
      password: "correct password",
    });
  });

  it("shows an error and does not navigate on invalid credentials", async () => {
    vi.mocked(clientPortalClient.post).mockImplementationOnce(() =>
      Promise.reject({ response: { status: 401, data: { title: "Invalid credentials" } } })
    );
    const user = userEvent.setup();
    renderApp();

    await user.type(await screen.findByPlaceholderText("you@yourcompany.com"), "client@example.com");
    await user.type(screen.getByPlaceholderText("••••••••"), "wrong password");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/could not sign in|invalid credentials/i)).toBeInTheDocument();
    expect(screen.queryByText("Lekki Tower")).not.toBeInTheDocument();
  });

  it("walks project -> progress -> document -> certificate -> approval", async () => {
    const user = userEvent.setup();
    // Skip the login screen itself -- already covered above -- by
    // seeding a real session the same way a successful login would
    // have (localStorage, via lib/auth.ts, not a mock of it).
    const { setClientTokens } = await import("./lib/auth");
    setClientTokens(ACCESS_TOKEN, "fake-refresh-token");
    renderApp("/portal/dashboard");

    // Dashboard -> Project
    await user.click(await screen.findByText("Lekki Tower"));
    expect(await screen.findByRole("heading", { name: "Lekki Tower" })).toBeInTheDocument();

    // Project -> Progress
    await user.click(screen.getByRole("link", { name: "Progress" }));
    expect(await screen.findByText("42.5%")).toBeInTheDocument();

    // Project -> Documents
    await user.click(screen.getByRole("link", { name: "Documents" }));
    expect(await screen.findByText("Signed Contract.pdf")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Download" }));
    await waitFor(() => {
      expect(clientPortalClient.get).toHaveBeenCalledWith("/clp/client-users/client-1/projects/proj-1/documents/doc-1/download");
      expect(window.open).toHaveBeenCalledWith("https://files.example.com/doc-1.pdf", "_blank", "noopener,noreferrer");
    });

    // Project -> Certificates -> Approval
    await user.click(screen.getByRole("link", { name: "Certificates" }));
    expect(await screen.findByText("PC-001")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Approve" }));
    await user.click(screen.getByRole("button", { name: "Confirm approval" }));

    await waitFor(() => {
      expect(clientPortalClient.post).toHaveBeenCalledWith(
        "/clp/client-users/client-1/certificates/cert-1/decide",
        expect.objectContaining({ project_id: "proj-1", decision: "approved" })
      );
    });
  });

  it("redirects an unauthenticated visitor straight to login", async () => {
    renderApp("/portal/dashboard");
    await screen.findByPlaceholderText("you@yourcompany.com");
  });
});
