import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import WorkforceDashboardPage from "./WorkforceDashboardPage";
import { apiClient } from "../../api/client";

vi.mock("../../api/client", () => ({
  apiClient: { get: vi.fn() },
}));

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <WorkforceDashboardPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function mockGet(overrides: Record<string, unknown> = {}) {
  const responses: Record<string, unknown> = {
    "/wfm/employees": [],
    "/wfm/casual-workers": [],
    "/wfm/leave-requests": [],
    "/wfm/certifications/expiring": [],
    "/wfm/training-records/expiring": [],
    ...overrides,
  };
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    const key = Object.keys(responses).find((k) => url.startsWith(k));
    if (key) return Promise.resolve({ data: { data: responses[key] } });
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe("WorkforceDashboardPage", () => {
  it("shows real active headcount split by employment type", async () => {
    mockGet({
      "/wfm/employees": [
        { id: "e1", name: "A", employee_number: null, role: null, trade: null, pay_grade: null, employment_type: "permanent", monthly_rate: null, assigned_project_ids: null, status: "active" },
        { id: "e2", name: "B", employee_number: null, role: null, trade: null, pay_grade: null, employment_type: "contract", monthly_rate: null, assigned_project_ids: null, status: "active" },
        { id: "e3", name: "C", employee_number: null, role: null, trade: null, pay_grade: null, employment_type: "permanent", monthly_rate: null, assigned_project_ids: null, status: "inactive" },
      ],
    });
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("2")).toBeInTheDocument();
    });
    expect(screen.getByText(/1 permanent · 1 contract/)).toBeInTheDocument();
  });

  it("shows real pending timesheet and leave counts", async () => {
    mockGet({
      "/wfm/timesheets": [{ id: "t1", employee_id: "e1", casual_worker_id: null, project_id: null, activity_id: null, period_start: "2026-08-01", period_end: "2026-08-31", pay_basis: "time_based", hours_or_units: "10", rate_applied: "100", gross_amount: "1000", status: "pending_approval", approved_by: null, approved_at: null, payroll_run_id: null }],
      "/wfm/leave-requests": [{ id: "l1", employee_id: "e1", leave_type: "annual", start_date: "2026-09-01", end_date: "2026-09-02", reason: null, status: "pending", approved_by: null, approved_at: null }],
    });
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Pending approvals")).toBeInTheDocument();
    });
  });

  it("shows real expiring certifications, per this batch's own explicit requirement", async () => {
    mockGet({
      "/wfm/certifications/expiring": [
        { id: "c1", employee_id: "e1", certification_type: "Rigger License", certificate_number: null, issued_at: null, expiry_date: "2026-09-10", issuing_body: null },
      ],
    });
    renderPage();

    expect(await screen.findByText("Rigger License")).toBeInTheDocument();
    expect(screen.getByText("2026-09-10")).toBeInTheDocument();
  });

  it("shows a real, honest empty state when nothing is expiring", async () => {
    mockGet();
    renderPage();

    expect(await screen.findByText("No certifications expiring soon.")).toBeInTheDocument();
    expect(screen.getByText("No training records expiring soon.")).toBeInTheDocument();
  });

  it("shows real expiring training records", async () => {
    mockGet({
      "/wfm/training-records/expiring": [
        { id: "tr1", employee_id: "e1", course_name: "Working at Heights", provider: null, completion_date: null, expiry_date: "2026-09-15" },
      ],
    });
    renderPage();

    expect(await screen.findByText("Working at Heights")).toBeInTheDocument();
  });

  it("shows real navigation links to the other real workforce screens", async () => {
    mockGet();
    renderPage();
    await waitFor(() => screen.getByText("Workforce Dashboard"));

    expect(screen.getByRole("link", { name: /employees/i })).toHaveAttribute("href", "/workforce/employees");
    expect(screen.getByRole("link", { name: /timesheets & leave/i })).toHaveAttribute("href", "/workforce/timesheets");
    expect(screen.getByRole("link", { name: /payroll/i })).toHaveAttribute("href", "/workforce/payroll");
  });
});
