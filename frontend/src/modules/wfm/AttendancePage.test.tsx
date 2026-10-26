import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import AttendancePage from "./AttendancePage";
import { apiClient } from "../../api/client";

vi.mock("../../api/client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn() },
  getErrorMessage: vi.fn((err: any) => err?.response?.data?.title || "Something went wrong."),
}));

const emp = (id: string, name: string, projects: string[] = ["p1"]) => ({ id, name, status: "active", assigned_project_ids: projects });
let attendance: any[] = [];

function render_() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <AttendancePage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  attendance = [];
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === "/projects") return Promise.resolve({ data: { data: [{ id: "p1", name: "Lekki Tower", status: "active" }] } } as any);
    if (url === "/wfm/employees") return Promise.resolve({ data: { data: [emp("e1", "Ada Eze"), emp("e2", "Bayo Ade"), emp("e3", "Other Site", ["p9"])] } } as any);
    if (url === "/wfm/casual-workers") return Promise.resolve({ data: { data: [{ id: "c1", name: "Chuka", status: "active" }] } } as any);
    if (url === "/wfm/attendance") return Promise.resolve({ data: { data: attendance } } as any);
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
});

async function pickProject(user: ReturnType<typeof userEvent.setup>) {
  const select = await screen.findByRole("combobox", { name: /project/i });
  await waitFor(() => expect(select).not.toBeDisabled());
  await user.selectOptions(select, "p1");
}

describe("AttendancePage", () => {
  it("asks for a project first", async () => {
    render_();
    expect(await screen.findByText("Choose a project")).toBeInTheDocument();
  });

  it("lists assigned employees plus casual workers, hiding other sites' staff", async () => {
    const user = userEvent.setup();
    render_();
    await pickProject(user);
    expect(await screen.findByText("Ada Eze")).toBeInTheDocument();
    expect(screen.getByText("Chuka")).toBeInTheDocument();
    expect(screen.queryByText("Other Site")).not.toBeInTheDocument();
  });

  it("marks everyone present and saves them in one request", async () => {
    const user = userEvent.setup();
    vi.mocked(apiClient.post).mockResolvedValue({ data: { created: 3, skipped: 0, error: 0, results: [] } } as any);
    render_();
    await pickProject(user);
    await screen.findByText("Ada Eze");

    await user.click(screen.getByRole("button", { name: "Mark all present" }));
    await user.selectOptions(screen.getByLabelText("Attendance for Bayo Ade"), "absent");
    await user.click(screen.getByRole("button", { name: /Save attendance \(3\)/ }));

    await waitFor(() => expect(apiClient.post).toHaveBeenCalledTimes(1));
    const [url, body] = vi.mocked(apiClient.post).mock.calls[0] as any;
    expect(url).toBe("/wfm/attendance/bulk");
    expect(body.project_id).toBe("p1");
    expect(body.rows).toHaveLength(3);
    expect(body.rows).toContainEqual({ employee_id: "e2" });
    expect(body.rows.find((r: any) => r.employee_id === "e1").check_in_at).toMatch(/T07:00:00$/);
    expect(await screen.findByText(/Saved 3/)).toBeInTheDocument();
  });

  it("shows people already recorded today as recorded and leaves them out of the save", async () => {
    const user = userEvent.setup();
    attendance = [{ id: "a1", employee_id: "e1", casual_worker_id: null }];
    vi.mocked(apiClient.post).mockResolvedValue({ data: { created: 2, skipped: 0, error: 0, results: [] } } as any);
    render_();
    await pickProject(user);
    expect(await screen.findByText("Recorded")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Mark all present" }));
    await user.click(screen.getByRole("button", { name: /Save attendance \(2\)/ }));
    await waitFor(() => expect(apiClient.post).toHaveBeenCalled());
    const body = (vi.mocked(apiClient.post).mock.calls[0] as any)[1];
    expect(body.rows.map((r: any) => r.employee_id ?? r.casual_worker_id).sort()).toEqual(["c1", "e2"]);
  });

  it("reports rows the server rejected", async () => {
    const user = userEvent.setup();
    vi.mocked(apiClient.post).mockResolvedValue({
      data: { created: 1, skipped: 0, error: 1, results: [{ index: 0, status: "created" }, { index: 1, status: "error", error: "Worker not found" }] },
    } as any);
    render_();
    await pickProject(user);
    await screen.findByText("Ada Eze");
    await user.click(screen.getByRole("button", { name: "Mark all present" }));
    await user.click(screen.getByRole("button", { name: /Save attendance/ }));
    expect(await screen.findByText(/1 failed/)).toBeInTheDocument();
    expect(screen.getByText(/Row 2: Worker not found/)).toBeInTheDocument();
  });
});
