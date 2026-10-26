import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { apiClient } from "../../api/client";
import { useScpStore } from "./store";
import ClaimsPage from "./ClaimsPage";
import ProgressPage from "./ProgressPage";
import CertificatesPage from "./CertificatesPage";

vi.mock("../../api/client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn() },
  getErrorMessage: (e: any) => e?.response?.data?.detail || "Something went wrong.",
}));

const SUB = "11111111-1111-1111-1111-111111111111";
const USER = "22222222-2222-2222-2222-222222222222";
const AGR = "33333333-3333-3333-3333-333333333333";

const agreement = {
  id: AGR, subcontractor_id: SUB, agreement_number: "SC-001", value: "1000000", currency: "NGN",
  retention_percentage: "5", status: "active",
};

function renderPage(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  );
}

function mockApi(extra: Record<string, unknown[]> = {}) {
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === "/sub/agreements") {
      return Promise.resolve({ data: { data: [agreement, { ...agreement, id: "other", subcontractor_id: "someone-else" }] } });
    }
    for (const key of Object.keys(extra)) {
      if (url.includes(key)) return Promise.resolve({ data: { data: extra[key] } });
    }
    return Promise.resolve({ data: { data: [] } });
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  useScpStore.setState({ session: { id: USER, subcontractor_id: SUB }, agreementId: AGR });
  vi.mocked(apiClient.post).mockResolvedValue({ data: {} });
});

describe("ClaimsPage", () => {
  it("rejects a claim with neither an amount nor days, without calling the API", async () => {
    mockApi();
    const user = userEvent.setup();
    renderPage(<ClaimsPage />);

    await user.type(await screen.findByLabelText(/description/i), "Access blocked for 3 days");
    await user.click(screen.getByRole("button", { name: /submit claim/i }));

    expect(await screen.findByText(/claimed amount, claimed days, or both/i)).toBeInTheDocument();
    expect(apiClient.post).not.toHaveBeenCalled();
  });

  it("posts to the portal user's claims endpoint with nulls (not empty strings) for blank fields", async () => {
    mockApi();
    const user = userEvent.setup();
    renderPage(<ClaimsPage />);

    await user.type(await screen.findByLabelText(/claimed days/i), "4");
    await user.type(screen.getByLabelText(/description/i), "Access blocked");
    await user.click(screen.getByRole("button", { name: /submit claim/i }));

    await waitFor(() => expect(apiClient.post).toHaveBeenCalledTimes(1));
    expect(apiClient.post).toHaveBeenCalledWith(`/scp/portal-users/${USER}/claims`, {
      agreement_id: AGR,
      claim_type: "delay",
      description: "Access blocked",
      claimed_amount: null,
      claimed_days: 4,
    });
  });

  it("only offers claim types the backend accepts", async () => {
    mockApi();
    renderPage(<ClaimsPage />);
    const select = await screen.findByLabelText(/claim type/i);
    const values = Array.from(select.querySelectorAll("option")).map((o) => (o as HTMLOptionElement).value);
    expect(values).toEqual(["delay", "additional_scope", "other"]);
  });
});

describe("ProgressPage", () => {
  it("blocks zero/negative quantities client-side", async () => {
    mockApi();
    const user = userEvent.setup();
    renderPage(<ProgressPage />);

    await user.type(await screen.findByLabelText(/quantity/i), "0");
    await user.click(screen.getByRole("button", { name: /^submit$/i }));

    expect(await screen.findByText(/greater than zero/i)).toBeInTheDocument();
    expect(apiClient.post).not.toHaveBeenCalled();
  });

  it("submits scope_item_id as null when 'general' is chosen", async () => {
    mockApi();
    const user = userEvent.setup();
    renderPage(<ProgressPage />);

    await user.type(await screen.findByLabelText(/quantity/i), "12.5");
    await user.click(screen.getByRole("button", { name: /^submit$/i }));

    await waitFor(() => expect(apiClient.post).toHaveBeenCalled());
    expect(apiClient.post).toHaveBeenCalledWith(`/scp/portal-users/${USER}/progress-entries`, {
      agreement_id: AGR,
      scope_item_id: null,
      submitted_quantity: "12.5",
    });
  });

  it("shows the server's rejection message when the API refuses", async () => {
    mockApi();
    vi.mocked(apiClient.post).mockRejectedValue({ response: { data: { detail: "This agreement does not belong to your organization" } } });
    const user = userEvent.setup();
    renderPage(<ProgressPage />);

    await user.type(await screen.findByLabelText(/quantity/i), "5");
    await user.click(screen.getByRole("button", { name: /^submit$/i }));

    expect(await screen.findByText(/does not belong to your organization/i)).toBeInTheDocument();
  });
});

describe("CertificatesPage", () => {
  const cert = (over: object) => ({
    id: "c", agreement_id: AGR, certificate_number: "PC-1", period_start: "2026-09-01", period_end: "2026-09-30",
    gross_certified_amount: "1000", retention_withheld: "50", back_charges_total: "10", net_payable: "940",
    status: "issued", issued_at: "2026-10-01T00:00:00Z", ...over,
  });

  it("never shows draft certificates to the subcontractor", async () => {
    mockApi({ "payment-certificates": [cert({ id: "a", certificate_number: "PC-ISSUED" }), cert({ id: "b", certificate_number: "PC-DRAFT", status: "draft" })] });
    renderPage(<CertificatesPage />);

    expect(await screen.findByText(/PC-ISSUED/)).toBeInTheDocument();
    expect(screen.queryByText(/PC-DRAFT/)).not.toBeInTheDocument();
  });

  it("flags a certificate whose components don't reconcile to net payable", async () => {
    mockApi({ "payment-certificates": [cert({ net_payable: "999" })] });
    const user = userEvent.setup();
    renderPage(<CertificatesPage />);

    await user.click(await screen.findByText(/PC-1/));
    expect(await screen.findByText(/don't add up/i)).toBeInTheDocument();
  });
});
