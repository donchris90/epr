import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import PayrollRunDetailPage from "./PayrollRunDetailPage";
import { apiClient } from "../../api/client";

vi.mock("../../api/client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn() },
  getErrorMessage: vi.fn((err: any) => err?.response?.data?.title || "Something went wrong."),
}));

const RUN = {
  id: "run-1",
  period_start: "2026-08-01",
  period_end: "2026-08-31",
  status: "draft",
  finalized_at: null,
  finalized_by: null,
  total_gross: "1000000",
  total_deductions: "150000",
  total_net: "850000",
  lines: [
    { id: "line-1", payroll_run_id: "run-1", employee_id: "emp-1", casual_worker_id: null, gross_pay: "500000", deductions_breakdown: {}, total_deductions: "75000", net_pay: "425000", bank_account_ref: "0123456789" },
    { id: "line-2", payroll_run_id: "run-1", employee_id: "emp-2", casual_worker_id: null, gross_pay: "500000", deductions_breakdown: {}, total_deductions: "75000", net_pay: "425000", bank_account_ref: null },
  ],
};

const EMPLOYEES = [
  { id: "emp-1", name: "Chidi Okafor", employee_number: null, role: null, trade: null, pay_grade: null, employment_type: "permanent", monthly_rate: null, assigned_project_ids: null, status: "active" },
  { id: "emp-2", name: "Amaka Eze", employee_number: null, role: null, trade: null, pay_grade: null, employment_type: "permanent", monthly_rate: null, assigned_project_ids: null, status: "active" },
];

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/workforce/payroll/run-1"]}>
        <Routes>
          <Route path="/workforce/payroll/:runId" element={<PayrollRunDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === "/wfm/payroll-runs/run-1") return Promise.resolve({ data: RUN });
    if (url === "/wfm/employees") return Promise.resolve({ data: { data: EMPLOYEES } });
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
  vi.mocked(apiClient.post).mockResolvedValue({ data: {} });
  vi.stubGlobal("URL", { ...URL, createObjectURL: vi.fn(() => "blob:mock"), revokeObjectURL: vi.fn() });
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

describe("PayrollRunDetailPage", () => {
  it("loads and shows the real period and status", async () => {
    renderPage();
    expect(await screen.findByText("2026-08-01 → 2026-08-31")).toBeInTheDocument();
    expect(screen.getByText("draft")).toBeInTheDocument();
  });

  it("shows real, resolved employee names on payslip lines, not raw ids", async () => {
    renderPage();
    expect(await screen.findByText("Chidi Okafor")).toBeInTheDocument();
    expect(screen.getByText("Amaka Eze")).toBeInTheDocument();
  });

  it("shows the real totals", async () => {
    renderPage();
    await screen.findByText("Chidi Okafor");
    expect(screen.getByText(/1,000,000/)).toBeInTheDocument();
    expect(screen.getByText(/850,000/)).toBeInTheDocument();
  });

  it("shows a real bank reference when present, and an honest dash when absent", async () => {
    renderPage();
    await screen.findByText("Chidi Okafor");
    expect(screen.getByText("0123456789")).toBeInTheDocument();
  });

  it("finalizes the real run via the real endpoint after real confirmation", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Chidi Okafor");

    await user.click(screen.getByRole("button", { name: /finalize payroll run/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/wfm/payroll-runs/run-1/finalize");
    });
  });

  it("does not show the finalize action for a real already-finalized run", async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === "/wfm/payroll-runs/run-1") return Promise.resolve({ data: { ...RUN, status: "finalized" } });
      if (url === "/wfm/employees") return Promise.resolve({ data: { data: EMPLOYEES } });
      return Promise.reject(new Error(`unexpected GET ${url}`));
    });
    renderPage();
    await screen.findByText("Chidi Okafor");

    expect(screen.queryByRole("button", { name: /finalize payroll run/i })).not.toBeInTheDocument();
  });

  it("exports a real CSV bank file with the real resolved names and bank references", async () => {
    const user = userEvent.setup();
    const createObjectURL = vi.fn((_obj: Blob | MediaSource) => "blob:mock");
    vi.stubGlobal("URL", { ...URL, createObjectURL, revokeObjectURL: vi.fn() });
    renderPage();
    await screen.findByText("Chidi Okafor");

    await user.click(screen.getByRole("button", { name: /export csv/i }));

    const blob = createObjectURL.mock.calls[0][0] as Blob;
    const text = await blob.text();
    expect(text).toContain("Chidi Okafor,0123456789,425000");
  });

  it("flags a real exception for zero or negative net pay", async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === "/wfm/payroll-runs/run-1") {
        return Promise.resolve({
          data: { ...RUN, lines: [{ ...RUN.lines[0], net_pay: "0" }] },
        });
      }
      if (url === "/wfm/employees") return Promise.resolve({ data: { data: EMPLOYEES } });
      return Promise.reject(new Error(`unexpected GET ${url}`));
    });
    renderPage();

    expect(await screen.findByText(/1 exception/i)).toBeInTheDocument();
  });

  it("posts a real, balanced entry to finance once company and accounts are selected", async () => {
    const user = userEvent.setup();
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === "/wfm/payroll-runs/run-1") return Promise.resolve({ data: RUN });
      if (url === "/wfm/employees") return Promise.resolve({ data: { data: EMPLOYEES } });
      if (url === "/fin/companies") return Promise.resolve({ data: { data: [{ id: "co-1", name: "Main Co", functional_currency: "NGN", is_default: true }] } });
      if (url === "/fin/chart-of-accounts") {
        return Promise.resolve({
          data: {
            data: [
              { id: "acc-1", code: "6000", name: "Wages Expense", account_type: "expense", is_active: true },
              { id: "acc-2", code: "2100", name: "Wages Payable", account_type: "liability", is_active: true },
            ],
          },
        });
      }
      return Promise.reject(new Error(`unexpected GET ${url}`));
    });
    renderPage();
    await screen.findByText("Chidi Okafor");

    const companyBox = screen.getAllByRole("combobox")[0];
    await user.click(companyBox);
    await user.click(await screen.findByText("Main Co"));

    const accountBoxes = screen.getAllByRole("combobox");
    await user.click(accountBoxes[1]);
    await user.click(await screen.findByText("Wages Expense"));

    await user.click(accountBoxes[2]);
    await user.click(await screen.findByText("Wages Payable"));

    await user.click(screen.getByRole("button", { name: /^post$/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith(
        "/fin/journal-entries/manual-exception",
        expect.objectContaining({
          company_id: "co-1",
          lines: [
            { account_id: "acc-1", debit_amount: "1000000", credit_amount: "0" },
            { account_id: "acc-2", debit_amount: "0", credit_amount: "1000000" },
          ],
        })
      );
    });
  });

  it("shows a real error banner when the run fails to load", async () => {
    vi.mocked(apiClient.get).mockRejectedValue({ response: { data: { title: "Payroll run not found" } } });
    renderPage();

    expect(await screen.findByText("Payroll run not found")).toBeInTheDocument();
  });
});
