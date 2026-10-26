import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import WorkflowEditPage from "./WorkflowEditPage";
import { apiClient } from "../../api/client";

vi.mock("../../api/client", () => ({ apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn() } }));
vi.mock("../../lib/permissions", () => ({ hasPermission: vi.fn().mockReturnValue(true) }));

function def(over: object) {
  return { id: "wf1", module_name: "prc", entity_type: "purchase_request", workflow_name: "WF", description: null, active: false, version: 1,
    created_at: "", created_by: null, updated_at: "", updated_by: null, steps: [], ...over };
}

function renderAt() {
  return render(
    <MemoryRouter initialEntries={["/workflows/wf1/edit"]}>
      <Routes><Route path="/workflows/:id/edit" element={<WorkflowEditPage />} /></Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.mocked(apiClient.get).mockReset();
});

function mockDef(d: object) {
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === "/workflow/definitions/wf1") return Promise.resolve({ data: d });
    if (url === "/org/members") return Promise.resolve({ data: { users: [] } });
    if (url === "/org/roles") return Promise.resolve({ data: { data: [] } });
    return Promise.reject(new Error(url));
  });
}

describe("WorkflowEditPage", () => {
  it("opens the builder in edit mode for an editable draft", async () => {
    mockDef(def({ editable: true }));
    renderAt();
    expect(await screen.findByText(/edit draft: wf/i)).toBeInTheDocument();
  });

  it("explains why an active workflow can't be edited and offers a new version", async () => {
    mockDef(def({ active: true, editable: false }));
    renderAt();
    expect(await screen.findByText(/can't be edited in place/i)).toBeInTheDocument();
    expect(screen.getByText(/it is active/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Create a new version" })).toBeInTheDocument();
  });

  it("explains a used (inactive) workflow", async () => {
    mockDef(def({ editable: false }));
    renderAt();
    expect(await screen.findByText(/already been used by an approval/i)).toBeInTheDocument();
  });
});
