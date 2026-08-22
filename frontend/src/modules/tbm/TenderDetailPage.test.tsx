import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import TenderDetailPage from "./TenderDetailPage";
import { apiClient } from "../../api/client";
import { ToastProvider } from "../../lib/toast";

vi.mock("../../api/client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
  getErrorMessage: (err: any) => err?.response?.data?.detail || "Something went wrong.",
}));

function renderWithProviders(tenderId: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/tenders/${tenderId}`]}>
          <Routes>
            <Route path="/tenders/:tenderId" element={<TenderDetailPage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>
  );
}

const DRAFT_TENDER = {
  id: "tender-1",
  opportunity_id: "opp-1",
  reference_number: "TND-2026-001",
  client_id: null,
  consultant_id: null,
  submission_deadline: null,
  bid_bond_required: false,
  bid_bond_amount: null,
  tender_fee: null,
  currency: "NGN",
  status: "draft",
  is_joint_venture: false,
  estimate_locked: false,
  reopen_count: 0,
  created_at: "2026-01-01T00:00:00Z",
};

function mockGet(tender = DRAFT_TENDER) {
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === "/tbm/tenders/tender-1") return Promise.resolve({ data: tender });
    if (url === "/bdc/opportunities") return Promise.resolve({ data: { data: [] } });
    if (url.includes("submission-readiness")) return Promise.resolve({ data: { can_submit: false, blockers: ["Bid bond not uploaded"] } });
    // boq-items, bid-documents, approval-steps, jv-partners all shaped as { data: [...] }
    return Promise.resolve({ data: { data: [] } });
  });
}

beforeEach(() => {
  mockGet();
});

describe("TenderDetailPage approval workflow", () => {
  it("shows an initiate-approval form for a draft tender with no approval steps yet", async () => {
    renderWithProviders("tender-1");
    expect(await screen.findByText("TND-2026-001")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /initiate approval workflow/i })).toBeInTheDocument();
  });

  it("initiates the approval workflow with the roles entered, locking the estimate", async () => {
    const user = userEvent.setup();
    vi.mocked(apiClient.post).mockImplementation((url: string) => {
      if (url.includes("approval-workflow/initiate")) return Promise.resolve({ data: { ...DRAFT_TENDER, status: "in_approval", estimate_locked: true } });
      return Promise.resolve({ data: {} });
    });
    renderWithProviders("tender-1");

    await screen.findByText("TND-2026-001");
    await user.type(screen.getByLabelText(/approver roles/i), "estimating_manager, finance_director");
    await user.click(screen.getByRole("button", { name: /initiate approval workflow/i }));

    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith("/tbm/tenders/tender-1/approval-workflow/initiate", {
        steps: [{ role_required: "estimating_manager" }, { role_required: "finance_director" }],
      })
    );
  });

  it("blocks BOQ editing once the estimate is locked (in_approval)", async () => {
    mockGet({ ...DRAFT_TENDER, status: "in_approval", estimate_locked: true });
    renderWithProviders("tender-1");

    await screen.findByText("TND-2026-001");
    expect(screen.getAllByPlaceholderText("Description")[0]).toBeDisabled();
    expect(screen.getByText(/estimate is locked/i)).toBeInTheDocument();
  });

  it("requires a reason and confirmation before reopening a tender for revision", async () => {
    const user = userEvent.setup();
    vi.mocked(apiClient.post).mockResolvedValue({ data: { ...DRAFT_TENDER, status: "in_estimate", reopen_count: 1 } });
    mockGet({ ...DRAFT_TENDER, status: "in_approval", estimate_locked: true });
    renderWithProviders("tender-1");

    await screen.findByText("TND-2026-001");
    await user.click(screen.getByRole("button", { name: /reopen for revision/i }));
    // Confirm button should be disabled with no reason typed yet.
    expect(screen.getByRole("button", { name: /confirm reopen/i })).toBeDisabled();

    await user.type(screen.getByLabelText(/reason for reopening/i), "Client raised a scope query.");
    await user.click(screen.getByRole("button", { name: /confirm reopen/i }));

    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith("/tbm/tenders/tender-1/reopen-for-revision", {
        reason: "Client raised a scope query.",
      })
    );
  });
});
