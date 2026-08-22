import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import OpportunityDetailPage from "./OpportunityDetailPage";
import { apiClient } from "../../api/client";
import { ToastProvider } from "../../lib/toast";

vi.mock("../../api/client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
  getErrorMessage: (err: any) => err?.response?.data?.detail || "Something went wrong.",
}));

function renderWithProviders(opportunityId: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/business-development/opportunities/${opportunityId}`]}>
          <Routes>
            <Route path="/business-development/opportunities/:opportunityId" element={<OpportunityDetailPage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>
  );
}

const OPPORTUNITY = {
  id: "opp-1",
  lead_id: null,
  client_id: "client-1",
  name: "New Highway Extension",
  stage: "bid_no_bid",
  estimated_value: "1000000",
  currency: "NGN",
  submission_deadline: null,
  bid_no_bid_decision: null,
  contract_id: null,
  created_at: "2026-01-01T00:00:00Z",
};

const CLIENT = { id: "client-1", name: "Lagos State Ministry of Works", billing_address: null, billing_email: null, notes: null, created_at: "2026-01-01T00:00:00Z" };

beforeEach(() => {
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === "/bdc/opportunities") return Promise.resolve({ data: { data: [OPPORTUNITY] } });
    if (url === "/bdc/clients") return Promise.resolve({ data: { data: [CLIENT] } });
    if (url === "/bdc/leads") return Promise.resolve({ data: { data: [] } });
    if (url === "/tbm/tenders") return Promise.resolve({ data: { data: [] } });
    return Promise.resolve({ data: { data: [] } });
  });
});

describe("OpportunityDetailPage", () => {
  it("shows the pipeline stage and related client", async () => {
    renderWithProviders("opp-1");
    expect(await screen.findByText("New Highway Extension")).toBeInTheDocument();
    expect(await screen.findByText("Lagos State Ministry of Works")).toBeInTheDocument();
  });

  it("submits a real scorecard (not an empty object) when recording a Bid decision", async () => {
    const user = userEvent.setup();
    vi.mocked(apiClient.post).mockResolvedValue({ data: { ...OPPORTUNITY, stage: "submitted" } });
    renderWithProviders("opp-1");

    await user.click(await screen.findByRole("button", { name: /record bid\/no-bid decision/i }));
    await user.type(screen.getByLabelText(/rationale/i), "Strong capability fit and healthy margin.");
    await user.click(screen.getByRole("button", { name: /save decision/i }));

    await waitFor(() => expect(apiClient.post).toHaveBeenCalledWith(
      "/bdc/opportunities/opp-1/bid-no-bid",
      expect.objectContaining({
        decision: "bid",
        rationale: "Strong capability fit and healthy margin.",
        scorecard: { capability_fit: 3, profitability: 3, strategic_value: 3 },
      })
    ));
  });

  it("surfaces the backend's real error message when a stage transition is rejected (e.g. won requires a contract)", async () => {
    const user = userEvent.setup();
    const submittedOpp = { ...OPPORTUNITY, stage: "submitted" };
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === "/bdc/opportunities") return Promise.resolve({ data: { data: [submittedOpp] } });
      if (url === "/bdc/clients") return Promise.resolve({ data: { data: [CLIENT] } });
      if (url === "/bdc/leads") return Promise.resolve({ data: { data: [] } });
      if (url === "/tbm/tenders") return Promise.resolve({ data: { data: [] } });
      return Promise.resolve({ data: { data: [] } });
    });
    vi.mocked(apiClient.post).mockRejectedValue({
      response: { status: 409, data: { detail: "A linked Contract record is required before marking an Opportunity 'won'." } },
    });

    renderWithProviders("opp-1");
    await user.click(await screen.findByRole("button", { name: /advance to won/i }));

    await waitFor(() => expect(screen.getByText(/linked contract record is required/i)).toBeInTheDocument());
  });
});
