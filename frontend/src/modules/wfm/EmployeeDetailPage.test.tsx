import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import EmployeeDetailPage from "./EmployeeDetailPage";
import { apiClient } from "../../api/client";

vi.mock("../../api/client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn() },
  getErrorMessage: vi.fn((err: any) => err?.response?.data?.title || "Something went wrong."),
}));

const EMPLOYEE = {
  id: "emp-1",
  name: "Chidi Okafor",
  employee_number: "EMP-042",
  role: "Site Engineer",
  trade: "Civil",
  pay_grade: "G3",
  employment_type: "permanent",
  monthly_rate: "500000",
  assigned_project_ids: ["proj-1"],
  status: "active",
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/workforce/employees/emp-1"]}>
        <Routes>
          <Route path="/workforce/employees/:employeeId" element={<EmployeeDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === "/wfm/employees/emp-1") return Promise.resolve({ data: EMPLOYEE });
    if (url === "/wfm/attendance") return Promise.resolve({ data: { data: [] } });
    if (url === "/wfm/timesheets") return Promise.resolve({ data: { data: [] } });
    if (url === "/wfm/leave-requests") return Promise.resolve({ data: { data: [] } });
    if (url === "/wfm/employees/emp-1/leave-balance") return Promise.resolve({ data: { days_taken_this_year_by_type: {} } });
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
  vi.mocked(apiClient.post).mockResolvedValue({ data: {} });
  vi.mocked(apiClient.put).mockResolvedValue({ data: {} });
});

describe("EmployeeDetailPage", () => {
  it("loads and shows the real employee's name and status", async () => {
    renderPage();
    expect(await screen.findByText("Chidi Okafor")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
  });

  it("shows every real required tab", async () => {
    renderPage();
    await screen.findByText("Chidi Okafor");
    for (const tab of ["Overview", "Employment", "Project Assignments", "Attendance", "Timesheets", "Leave", "Training", "Certifications", "Competencies"]) {
      expect(screen.getByRole("button", { name: tab })).toBeInTheDocument();
    }
  });

  it("shows the real employee's overview fields", async () => {
    renderPage();
    await screen.findByText("Chidi Okafor");
    expect(screen.getByText("Site Engineer")).toBeInTheDocument();
    expect(screen.getByText("Civil")).toBeInTheDocument();
  });

  it("terminates a real active employee via the real endpoint", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Chidi Okafor");

    await user.click(screen.getByRole("button", { name: /^terminate$/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/wfm/employees/emp-1/terminate");
    });
  });

  it("does not terminate when the real confirmation is declined", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Chidi Okafor");

    await user.click(screen.getByRole("button", { name: /^terminate$/i }));

    expect(apiClient.post).not.toHaveBeenCalled();
  });

  it("saves real employment field edits via the real update endpoint", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Chidi Okafor");

    await user.click(screen.getByRole("button", { name: "Employment" }));
    const roleInput = await screen.findByDisplayValue("Site Engineer");
    await user.clear(roleInput);
    await user.type(roleInput, "Lead Engineer");
    await user.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() => {
      expect(apiClient.put).toHaveBeenCalledWith("/wfm/employees/emp-1", expect.objectContaining({ role: "Lead Engineer" }));
    });
  });

  it("shows a real, honest empty state when there are no attendance records", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Chidi Okafor");

    await user.click(screen.getByRole("button", { name: "Attendance" }));

    expect(await screen.findByText("No attendance records yet.")).toBeInTheDocument();
  });

  it("corrects a real attendance record via the real, newly-wired endpoint", async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === "/wfm/employees/emp-1") return Promise.resolve({ data: EMPLOYEE });
      if (url === "/wfm/attendance") {
        return Promise.resolve({
          data: { data: [{ id: "att-1", project_id: "proj-1", employee_id: "emp-1", casual_worker_id: null, attendance_date: "2026-08-24", check_in_at: null, check_out_at: null, capture_method: "manual" }] },
        });
      }
      if (url === "/wfm/timesheets") return Promise.resolve({ data: { data: [] } });
      if (url === "/wfm/leave-requests") return Promise.resolve({ data: { data: [] } });
      if (url === "/wfm/employees/emp-1/leave-balance") return Promise.resolve({ data: { days_taken_this_year_by_type: {} } });
      return Promise.reject(new Error(`unexpected GET ${url}`));
    });
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Chidi Okafor");

    await user.click(screen.getByRole("button", { name: "Attendance" }));
    await user.click(await screen.findByRole("button", { name: /^correct$/i }));

    const inputs = screen.getAllByDisplayValue("");
    const datetimeInputs = inputs.filter((el) => (el as HTMLInputElement).type === "datetime-local");
    await user.type(datetimeInputs[0], "2026-08-24T07:00");

    await user.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() => {
      expect(apiClient.put).toHaveBeenCalledWith("/wfm/attendance/att-1", expect.objectContaining({ check_in_at: "2026-08-24T07:00" }));
    });
  });

  it("shows a real, honest empty state when there is no leave taken this year", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Chidi Okafor");

    await user.click(screen.getByRole("button", { name: "Leave" }));

    expect(await screen.findByText("No approved leave taken this year.")).toBeInTheDocument();
  });

  it("submits a real leave request via the real endpoint", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Chidi Okafor");

    await user.click(screen.getByRole("button", { name: "Leave" }));
    const dateInputs = (await screen.findAllByDisplayValue("")).filter((el) => (el as HTMLInputElement).type === "date");
    await user.type(dateInputs[0], "2026-09-01");
    await user.type(dateInputs[1], "2026-09-05");

    await user.click(screen.getByRole("button", { name: /^request$/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/wfm/leave-requests", expect.objectContaining({ employee_id: "emp-1" }));
    });
  });

  it("adds a real training record via the real endpoint", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Chidi Okafor");

    await user.click(screen.getByRole("button", { name: "Training" }));
    await user.type(await screen.findByPlaceholderText("Course name"), "Working at Heights");
    await user.click(screen.getByRole("button", { name: /^add$/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/wfm/employees/emp-1/training-records", expect.objectContaining({ course_name: "Working at Heights" }));
    });
  });

  it("shows a real error banner when the employee fails to load", async () => {
    vi.mocked(apiClient.get).mockRejectedValue({ response: { data: { title: "Employee not found" } } });
    renderPage();

    expect(await screen.findByText("Employee not found")).toBeInTheDocument();
  });
});
