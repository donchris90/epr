import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import SubcontractorDashboardPage from "./SubcontractorDashboardPage";
import { apiClient } from "../../api/client";

vi.mock("../../api/client", () => ({
  apiClient: { get: vi.fn() },
}));

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <SubcontractorDashboardPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function mockGet(subcontractors: unknown[] = [], agreements: unknown[] = []) {
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === "/sub/subcontractors") return Promise.resolve({ data: { data: subcontractors } });
    if (url === "/sub/agreements") return Promise.resolve({ data: { data: agreements } });
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe("SubcontractorDashboardPage", () => {
  it("shows real active subcontractor and agreement counts", async () => {
    mockGet(
      [
        { id: "s1", name: "A", trade_specialty: null, tax_registration_number: null, status: "active" },
        { id: "s2", name: "B", trade_specialty: null, tax_registration_number: null, status: "inactive" },
      ],
      [
        { id: "a1", subcontractor_id: "s1", contract_id: null, agreement_number: "AG-1", value: "1000000", currency: "NGN", payment_terms_summary: null, retention_percentage: "5", status: "active" },
      ]
    );
    renderPage();

    await waitFor(() => {
      expect(screen.getAllByText("1").length).toBeGreaterThanOrEqual(2);
    });
    expect(screen.getByText(/2 total on file/)).toBeInTheDocument();
  });

  it("shows a real, computed total value summed only across active agreements", async () => {
    mockGet(
      [],
      [
        { id: "a1", subcontractor_id: "s1", contract_id: null, agreement_number: "AG-1", value: "1000000", currency: "NGN", payment_terms_summary: null, retention_percentage: "5", status: "active" },
        { id: "a2", subcontractor_id: "s1", contract_id: null, agreement_number: "AG-2", value: "500000", currency: "NGN", payment_terms_summary: null, retention_percentage: "5", status: "active" },
        { id: "a3", subcontractor_id: "s1", contract_id: null, agreement_number: "AG-3", value: "999999999", currency: "NGN", payment_terms_summary: null, retention_percentage: "5", status: "terminated" },
      ]
    );
    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/1,500,000/)).toBeInTheDocument();
    });
  });

  it("shows a real breakdown of agreements by status", async () => {
    mockGet(
      [],
      [
        { id: "a1", subcontractor_id: "s1", contract_id: null, agreement_number: "AG-1", value: "1000", currency: "NGN", payment_terms_summary: null, retention_percentage: "5", status: "active" },
        { id: "a2", subcontractor_id: "s1", contract_id: null, agreement_number: "AG-2", value: "1000", currency: "NGN", payment_terms_summary: null, retention_percentage: "5", status: "terminated" },
      ]
    );
    renderPage();

    expect(await screen.findByText("active")).toBeInTheDocument();
    expect(screen.getByText("terminated")).toBeInTheDocument();
  });

  it("shows a real, honest empty state when there are no agreements at all", async () => {
    mockGet([], []);
    renderPage();

    expect(await screen.findByText("No agreements yet.")).toBeInTheDocument();
  });

  it("links to the real subcontractors list", async () => {
    mockGet();
    renderPage();
    await waitFor(() => screen.getByText("Subcontractor Dashboard"));

    expect(screen.getByRole("link", { name: /subcontractors & agreements/i })).toHaveAttribute("href", "/subcontractors/list");
  });
});
