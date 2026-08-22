import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import EstimatePage from "./EstimatePage";
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
        <MemoryRouter initialEntries={[`/tenders/${tenderId}/estimate`]}>
          <Routes>
            <Route path="/tenders/:tenderId/estimate" element={<EstimatePage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>
  );
}

const VERSION = { id: "v1", tender_id: "tender-1", version_number: 1, label: "Base case", status: "draft", notes: null, created_at: "2026-01-01T00:00:00Z" };

beforeEach(() => {
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === "/est/tenders/tender-1/estimate-versions") return Promise.resolve({ data: { data: [VERSION] } });
    if (url === "/est/estimate-versions/v1/boq-items") return Promise.resolve({ data: { data: [] } });
    // Real backend totals: direct cost (engineers-estimate) is
    // distinct from items_total (tender-price), which already has
    // per-item markup baked in.
    if (url === "/est/estimate-versions/v1/engineers-estimate") return Promise.resolve({ data: { estimate_version_id: "v1", cost_only_total: "100000.00" } });
    if (url === "/est/estimate-versions/v1/tender-price")
      return Promise.resolve({ data: { line_items: [], items_total: "112000.00", contingency_total: "5600.00", grand_total: "117600.00" } });
    return Promise.resolve({ data: { data: [] } });
  });
});

describe("EstimatePage cost breakdown", () => {
  it("shows direct cost and grand total exactly as the backend returns them, never recomputed", async () => {
    renderWithProviders("tender-1");
    await userEvent.setup().click(await screen.findByRole("button", { name: /cost breakdown/i }));

    // Direct cost = engineers-estimate.cost_only_total, verbatim.
    expect(await screen.findByText(/100,000/)).toBeInTheDocument();
    // Grand total = tender-price.grand_total, verbatim.
    expect(screen.getByText(/117,600/)).toBeInTheDocument();
    // Contingency = tender-price.contingency_total, verbatim.
    expect(screen.getByText(/5,600/)).toBeInTheDocument();
  });

  it("derives the markup line as the difference between two real backend totals (12,000 = 112,000 - 100,000), not a re-implemented markup formula", async () => {
    renderWithProviders("tender-1");
    await userEvent.setup().click(await screen.findByRole("button", { name: /cost breakdown/i }));

    expect(await screen.findByText(/12,000/)).toBeInTheDocument();
  });

  it("explains why whole-tender markup records aren't reflected in the total (a real backend gap, not hidden from the user)", async () => {
    renderWithProviders("tender-1");
    await userEvent.setup().click(await screen.findByRole("button", { name: /cost breakdown/i }));

    expect(await screen.findByText(/not currently applied to the Total Estimate/i)).toBeInTheDocument();
  });
});
