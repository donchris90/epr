import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import WorkflowDetailPage from "./WorkflowDetailPage";
import { apiClient } from "../../api/client";
import * as permissions from "../../lib/permissions";

vi.mock("../../api/client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn() },
}));

vi.mock("../../lib/permissions", () => ({
  hasPermission: vi.fn(),
}));

const REAL_DEFINITION = {
  id: "wf-1",
  module_name: "prc",
  entity_type: "purchase_request",
  workflow_name: "Purchase Request Approval",
  description: "For large purchases",
  active: false,
  version: 1,
  created_at: "2026-01-01T00:00:00Z",
  created_by: "user-1",
  updated_at: "2026-01-01T00:00:00Z",
  updated_by: null,
  steps: [
    {
      id: "step-1",
      step_number: 1,
      name: "Finance Approval",
      approver_type: "specific_role",
      required_role_id: "role-1",
      auto_escalate: false,
      allow_skip: false,
      parallel: false,
    },
  ],
};

function renderDetail() {
  return render(
    <MemoryRouter initialEntries={["/workflows/wf-1"]}>
      <Routes>
        <Route path="/workflows/:id" element={<WorkflowDetailPage />} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.mocked(permissions.hasPermission).mockReturnValue(true);
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === "/workflow/definitions/wf-1") return Promise.resolve({ data: REAL_DEFINITION });
    if (url === "/workflow/definitions") return Promise.resolve({ data: { data: [REAL_DEFINITION] } });
    if (url === "/org/members") return Promise.resolve({ data: { users: [{ id: "user-1", email: "pm@example.com" }] } });
    if (url === "/org/roles") return Promise.resolve({ data: { data: [{ id: "role-1", name: "Finance" }] } });
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
});

describe("WorkflowDetailPage", () => {
  it("shows real workflow information, trigger, and steps", async () => {
    renderDetail();
    await waitFor(() => {
      expect(screen.getByText("Purchase Request Approval")).toBeInTheDocument();
      expect(screen.getByText("Finance Approval")).toBeInTheDocument();
      expect(screen.getAllByText(/purchase_request/).length).toBeGreaterThan(0);
    });
  });

  it("resolves created_by to a real name for audit display", async () => {
    renderDetail();
    await waitFor(() => {
      expect(screen.getByText("pm@example.com")).toBeInTheDocument();
    });
  });

  it("resolves the real approver role name for a step", async () => {
    renderDetail();
    await waitFor(() => {
      expect(screen.getByText(/Role — Finance/)).toBeInTheDocument();
    });
  });

  it("shows real version history from the backend", async () => {
    renderDetail();
    await waitFor(() => {
      expect(screen.getAllByText(/v1/).length).toBeGreaterThan(0);
      expect(screen.getByText("Viewing")).toBeInTheDocument();
    });
  });

  it("calls the real activate endpoint when publishing a draft", async () => {
    const user = userEvent.setup();
    vi.mocked(apiClient.post).mockResolvedValue({ data: { ...REAL_DEFINITION, active: true } });
    renderDetail();
    await waitFor(() => screen.getByText("Purchase Request Approval"));

    await user.click(screen.getByRole("button", { name: /publish/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/workflow/definitions/wf-1/activate");
    });
  });

  it("hides activate/deactivate/new-version actions for a user without workflow:admin", async () => {
    vi.mocked(permissions.hasPermission).mockReturnValue(false);
    renderDetail();
    await waitFor(() => screen.getByText("Purchase Request Approval"));

    expect(screen.queryByRole("button", { name: /publish/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /new version/i })).not.toBeInTheDocument();
  });

  it("shows the real deactivate action for an active workflow", async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === "/workflow/definitions/wf-1") return Promise.resolve({ data: { ...REAL_DEFINITION, active: true } });
      if (url === "/workflow/definitions") return Promise.resolve({ data: { data: [{ ...REAL_DEFINITION, active: true }] } });
      if (url === "/org/members") return Promise.resolve({ data: { users: [] } });
      if (url === "/org/roles") return Promise.resolve({ data: { data: [] } });
      return Promise.reject(new Error(`unexpected GET ${url}`));
    });
    renderDetail();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /deactivate/i })).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /publish/i })).not.toBeInTheDocument();
    });
  });
});
