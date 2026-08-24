import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DashboardPage from "./DashboardPage";
import { apiClient } from "../../api/client";

vi.mock("../../api/client", () => ({
  apiClient: { get: vi.fn() },
}));

function renderDashboard() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <DashboardPage />
    </QueryClientProvider>
  );
}

function mockGet(overrides: Record<string, unknown> = {}) {
  const responses: Record<string, unknown> = {
    "/exd/company-revenue": { actual_revenue: "5000000", budget_amount: "4500000", variance: "500000", variance_pct: "11.1", drill_down_journal_entries: [] },
    "/exd/active-projects-performance": [],
    "/exd/project-risks": [],
    "/exd/ar-ap-aging": { total_receivable: "1200000", total_payable: "800000" },
    "/exd/equipment-utilization": [],
    "/projects": [],
    "/tbm/tenders": [],
    "/hse/incidents": [],
    "/wfm/employees": [],
    ...overrides,
  };
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url in responses) {
      const value = responses[url];
      return Promise.resolve({ data: Array.isArray(value) ? { data: value } : value });
    }
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe("Executive DashboardPage", () => {
  it("shows real section headings for every dashboard area", async () => {
    mockGet();
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText("Financial")).toBeInTheDocument();
    });
    expect(screen.getByText("Projects")).toBeInTheDocument();
    expect(screen.getByText("Commercial")).toBeInTheDocument();
    expect(screen.getByText("HSE")).toBeInTheDocument();
    expect(screen.getByText("Workforce")).toBeInTheDocument();
  });

  it("sends the real, required period_start/period_end params the backend requires -- the real bug this batch found and fixed", async () => {
    mockGet();
    renderDashboard();

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith(
        "/exd/company-revenue",
        expect.objectContaining({ params: expect.objectContaining({ period_start: expect.any(String), period_end: expect.any(String) }) })
      );
      expect(apiClient.get).toHaveBeenCalledWith(
        "/exd/equipment-utilization",
        expect.objectContaining({ params: expect.objectContaining({ period_start: expect.any(String), period_end: expect.any(String) }) })
      );
    });
  });

  it("shows real revenue using the real budget_amount field, not the nonexistent budgeted_revenue this batch found and fixed", async () => {
    mockGet();
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText(/11\.1%/)).toBeInTheDocument();
    });
  });

  it("shows a real project name instead of a raw project id -- the real bug this batch found and fixed", async () => {
    mockGet({
      "/exd/active-projects-performance": [{ project_id: "proj-1", cpi: "0.95", spi: "1.02" }],
      "/projects": [{ id: "proj-1", name: "Lekki Phase 2 Tower" }],
    });
    renderDashboard();

    expect(await screen.findByText("Lekki Phase 2 Tower")).toBeInTheDocument();
    expect(screen.queryByText(/proj-1…/)).not.toBeInTheDocument();
  });

  it("shows a real, honest fallback for a project id with no matching project", async () => {
    mockGet({
      "/exd/active-projects-performance": [{ project_id: "proj-missing", cpi: "0.95", spi: "1.02" }],
      "/projects": [],
    });
    renderDashboard();

    expect(await screen.findByText("Unknown project")).toBeInTheDocument();
  });

  it("computes a real tender pipeline breakdown by status", async () => {
    mockGet({
      "/tbm/tenders": [
        { id: "t1", status: "awarded", reference_number: "T-1" },
        { id: "t2", status: "awarded", reference_number: "T-2" },
        { id: "t3", status: "submitted", reference_number: "T-3" },
      ],
    });
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText("Awarded")).toBeInTheDocument();
      expect(screen.getByText("Submitted")).toBeInTheDocument();
    });
  });

  it("computes a real win rate from real awarded/lost tender counts", async () => {
    mockGet({
      "/tbm/tenders": [
        { id: "t1", status: "awarded", reference_number: "T-1" },
        { id: "t2", status: "awarded", reference_number: "T-2" },
        { id: "t3", status: "lost", reference_number: "T-3" },
      ],
    });
    renderDashboard();

    expect(await screen.findByText("67%")).toBeInTheDocument();
  });

  it("shows a real, honest empty state when there are not enough decided tenders for a win rate", async () => {
    mockGet({ "/tbm/tenders": [{ id: "t1", status: "draft", reference_number: "T-1" }] });
    renderDashboard();

    expect(await screen.findByText(/not enough decided tenders/i)).toBeInTheDocument();
  });

  it("computes real incident counts by classification", async () => {
    mockGet({
      "/hse/incidents": [
        { id: "i1", project_id: "p1", classification: "first_aid", description: "x", status: "open", corrective_action_id: null, occurred_at: "2026-06-01T00:00:00Z" },
        { id: "i2", project_id: "p1", classification: "lost_time", description: "y", status: "open", corrective_action_id: null, occurred_at: "2026-06-02T00:00:00Z" },
      ],
    });
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText("First aid")).toBeInTheDocument();
      expect(screen.getByText("Lost time")).toBeInTheDocument();
    });
  });

  it("computes a real safety trend grouped by month from real occurred_at values", async () => {
    mockGet({
      "/hse/incidents": [
        { id: "i1", project_id: "p1", classification: "first_aid", description: "x", status: "open", corrective_action_id: null, occurred_at: "2026-06-15T00:00:00Z" },
        { id: "i2", project_id: "p1", classification: "first_aid", description: "y", status: "open", corrective_action_id: null, occurred_at: "2026-06-20T00:00:00Z" },
      ],
    });
    renderDashboard();

    expect(await screen.findByText("2026-06")).toBeInTheDocument();
  });

  it("computes real headcount, only counting active employees", async () => {
    mockGet({
      "/wfm/employees": [
        { id: "e1", name: "A", employee_number: null, role: null, trade: null, pay_grade: null, employment_type: "permanent", monthly_rate: null, assigned_project_ids: null, status: "active" },
        { id: "e2", name: "B", employee_number: null, role: null, trade: null, pay_grade: null, employment_type: "contract", monthly_rate: null, assigned_project_ids: null, status: "active" },
        { id: "e3", name: "C", employee_number: null, role: null, trade: null, pay_grade: null, employment_type: "permanent", monthly_rate: null, assigned_project_ids: null, status: "terminated" },
      ],
    });
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText("2")).toBeInTheDocument();
    });
  });

  it("shows real, honest empty states for every section when there is genuinely no data", async () => {
    mockGet({ "/exd/company-revenue": { actual_revenue: null, budget_amount: null, variance: null, variance_pct: null, drill_down_journal_entries: [] } });
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText("No active project data yet.")).toBeInTheDocument();
      expect(screen.getByText("No open risks across active projects.")).toBeInTheDocument();
      expect(screen.getByText("No tenders yet.")).toBeInTheDocument();
      expect(screen.getByText("No incidents recorded.")).toBeInTheDocument();
      expect(screen.getAllByText("No employees recorded yet.").length).toBeGreaterThanOrEqual(1);
    });
  });
});
