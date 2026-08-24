import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import AgreementDetailPage from "./AgreementDetailPage";
import { apiClient } from "../../api/client";

vi.mock("../../api/client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn() },
  getErrorMessage: vi.fn((err: any) => err?.response?.data?.title || "Something went wrong."),
}));

const AGREEMENT = {
  id: "ag-1",
  subcontractor_id: "sub-1",
  contract_id: null,
  agreement_number: "AG-2026-001",
  value: "5000000",
  currency: "NGN",
  payment_terms_summary: "Net 30",
  retention_percentage: "5.00",
  status: "active",
};

const emptyEndpoints = [
  "/sub/agreements/ag-1/scope-items",
  "/sub/agreements/ag-1/progress-entries",
  "/sub/agreements/ag-1/measurement-sheets",
  "/sub/agreements/ag-1/payment-certificates",
  "/sub/agreements/ag-1/back-charges",
  "/sub/agreements/ag-1/retention",
  "/sub/agreements/ag-1/claims",
  "/sub/subcontractors/sub-1/compliance-documents",
  "/sub/subcontractors/sub-1/ratings",
];

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/subcontractors/agreements/ag-1"]}>
        <Routes>
          <Route path="/subcontractors/agreements/:agreementId" element={<AgreementDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === "/sub/agreements/ag-1") return Promise.resolve({ data: AGREEMENT });
    if (emptyEndpoints.includes(url)) return Promise.resolve({ data: { data: [] } });
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
  vi.mocked(apiClient.post).mockResolvedValue({ data: {} });
});

describe("AgreementDetailPage", () => {
  it("loads and shows the real agreement number and status", async () => {
    renderPage();
    expect(await screen.findByText("AG-2026-001")).toBeInTheDocument();
    expect(screen.getAllByText("active").length).toBeGreaterThan(0);
  });

  it("shows every real required tab", async () => {
    renderPage();
    await screen.findByText("AG-2026-001");
    for (const tab of ["Overview", "Scope", "Progress", "Measurements", "Certificates", "Retention", "Back Charges", "Claims", "Compliance", "Performance"]) {
      expect(screen.getByRole("button", { name: tab })).toBeInTheDocument();
    }
  });

  it("shows the real agreement's overview fields", async () => {
    renderPage();
    await screen.findByText("AG-2026-001");
    expect(screen.getByText("Net 30")).toBeInTheDocument();
    expect(screen.getByText(/5\.00%/)).toBeInTheDocument();
  });

  it("adds a real scope item via the real endpoint", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("AG-2026-001");

    await user.click(screen.getByRole("button", { name: "Scope" }));
    await user.type(await screen.findByPlaceholderText("Description"), "Steel fabrication");
    await user.click(screen.getByRole("button", { name: /^add$/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/sub/agreements/ag-1/scope-items", expect.objectContaining({ description: "Steel fabrication" }));
    });
  });

  it("submits real progress via the real endpoint", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("AG-2026-001");

    await user.click(screen.getByRole("button", { name: "Progress" }));
    await user.type(await screen.findByPlaceholderText("Submitted quantity"), "50");
    await user.click(screen.getByRole("button", { name: /^submit$/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/sub/agreements/ag-1/progress-entries", expect.objectContaining({ submitted_quantity: "50" }));
    });
  });

  it("shows a real, honest empty state when there are no measurement sheets", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("AG-2026-001");

    await user.click(screen.getByRole("button", { name: "Measurements" }));

    expect(await screen.findByText("No measurement sheets yet.")).toBeInTheDocument();
  });

  it("shows a real, honest empty state on Certificates when there are no verified sheets available", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("AG-2026-001");

    await user.click(screen.getByRole("button", { name: "Certificates" }));

    expect(await screen.findByText("No verified measurement sheets available yet.")).toBeInTheDocument();
  });

  it("sets retention at the real agreement rate via the real endpoint", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("AG-2026-001");

    await user.click(screen.getByRole("button", { name: "Retention" }));
    await user.click(await screen.findByRole("button", { name: /set at agreement rate/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/sub/agreements/ag-1/retention", { percentage: "5.00" });
    });
  });

  it("adds a real back charge via the real endpoint", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("AG-2026-001");

    await user.click(screen.getByRole("button", { name: "Back Charges" }));
    await user.type(await screen.findByPlaceholderText("Description"), "Damaged materials");
    await user.type(screen.getByPlaceholderText("Amount"), "50000");
    await user.click(screen.getByRole("button", { name: /^add$/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/sub/agreements/ag-1/back-charges", expect.objectContaining({ description: "Damaged materials", amount: "50000" }));
    });
  });

  it("submits a real claim via the real endpoint", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("AG-2026-001");

    await user.click(screen.getByRole("button", { name: "Claims" }));
    await user.type(await screen.findByPlaceholderText("Description"), "Late drawings");
    await user.click(screen.getByRole("button", { name: /^submit$/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/sub/agreements/ag-1/claims", expect.objectContaining({ description: "Late drawings" }));
    });
  });

  it("uploads a real compliance record via the real subcontractor-scoped endpoint", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("AG-2026-001");

    await user.click(screen.getByRole("button", { name: "Compliance" }));
    await user.click(await screen.findByRole("button", { name: /^add$/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/sub/subcontractors/sub-1/compliance-documents", expect.objectContaining({ doc_type: "insurance" }));
    });
  });

  it("rates the contractor via the real subcontractor-scoped endpoint", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("AG-2026-001");

    await user.click(screen.getByRole("button", { name: "Performance" }));
    await user.type(await screen.findByPlaceholderText("Quality"), "8");
    await user.type(screen.getByPlaceholderText("Schedule"), "7");
    await user.type(screen.getByPlaceholderText("Safety"), "9");
    await user.type(screen.getByPlaceholderText("Responsiveness"), "8");
    await user.click(screen.getByRole("button", { name: /^rate$/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/sub/subcontractors/sub-1/ratings", expect.objectContaining({ quality_score: "8" }));
    });
  });

  it("shows a real error banner when the agreement fails to load", async () => {
    vi.mocked(apiClient.get).mockRejectedValue({ response: { data: { title: "Agreement not found" } } });
    renderPage();

    expect(await screen.findByText("Agreement not found")).toBeInTheDocument();
  });
});
