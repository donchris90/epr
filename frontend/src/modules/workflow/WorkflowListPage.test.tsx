import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import WorkflowListPage from "./WorkflowListPage";
import { apiClient } from "../../api/client";
import * as permissions from "../../lib/permissions";

vi.mock("../../api/client", () => ({
  apiClient: { get: vi.fn() },
}));

vi.mock("../../lib/permissions", () => ({
  hasPermission: vi.fn(),
}));

const REAL_DEFINITIONS = [
  {
    id: "wf-1",
    module_name: "prc",
    entity_type: "purchase_request",
    workflow_name: "Purchase Request Approval",
    description: "For large purchases",
    active: true,
    version: 2,
    created_at: "2026-01-01T00:00:00Z",
    created_by: "user-1",
    updated_at: "2026-02-01T00:00:00Z",
    updated_by: "user-1",
    steps: [],
  },
  {
    id: "wf-2",
    module_name: "ctm",
    entity_type: "contract_amendment",
    workflow_name: "Contract Amendment Draft",
    description: null,
    active: false,
    version: 1,
    created_at: "2026-01-05T00:00:00Z",
    created_by: "user-2",
    updated_at: "2026-01-05T00:00:00Z",
    updated_by: null,
    steps: [],
  },
];

function renderList() {
  return render(
    <MemoryRouter>
      <WorkflowListPage />
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.mocked(permissions.hasPermission).mockReturnValue(true);
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === "/workflow/definitions") return Promise.resolve({ data: { data: REAL_DEFINITIONS } });
    if (url === "/org/members") return Promise.resolve({ data: { users: [{ id: "user-1", email: "admin@example.com" }] } });
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
});

describe("WorkflowListPage", () => {
  it("lists real workflows from the backend", async () => {
    renderList();
    await waitFor(() => {
      expect(screen.getByText("Purchase Request Approval")).toBeInTheDocument();
      expect(screen.getByText("Contract Amendment Draft")).toBeInTheDocument();
    });
  });

  it("resolves created_by to a real name, not a raw id", async () => {
    renderList();
    await waitFor(() => {
      expect(screen.getByText("admin@example.com")).toBeInTheDocument();
    });
  });

  it("shows real status badges reflecting the actual active field", async () => {
    renderList();
    await waitFor(() => screen.getByText("Purchase Request Approval"));

    // "Active"/"Draft" also appear as option text in the status
    // filter dropdown -- getAllByText and confirm the real badge
    // (a <span>, not an <option>) is among the matches.
    const activeMatches = screen.getAllByText("Active");
    expect(activeMatches.some((el) => el.tagName === "SPAN")).toBe(true);
    const draftMatches = screen.getAllByText("Draft");
    expect(draftMatches.some((el) => el.tagName === "SPAN")).toBe(true);
  });

  it("filters client-side by search text", async () => {
    const user = userEvent.setup();
    renderList();
    await waitFor(() => screen.getByText("Purchase Request Approval"));

    await user.type(screen.getByPlaceholderText(/search by name/i), "Contract");

    expect(screen.queryByText("Purchase Request Approval")).not.toBeInTheDocument();
    expect(screen.getByText("Contract Amendment Draft")).toBeInTheDocument();
  });

  it("filters client-side by status", async () => {
    const user = userEvent.setup();
    renderList();
    await waitFor(() => screen.getByText("Purchase Request Approval"));

    await user.selectOptions(screen.getByLabelText(/status/i), "inactive");

    expect(screen.queryByText("Purchase Request Approval")).not.toBeInTheDocument();
    expect(screen.getByText("Contract Amendment Draft")).toBeInTheDocument();
  });

  it("real module filter is passed to the backend as a query param", async () => {
    const user = userEvent.setup();
    renderList();
    await waitFor(() => screen.getByText("Purchase Request Approval"));

    await user.selectOptions(screen.getByLabelText(/module/i), "ctm");

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith("/workflow/definitions", { params: { module_name: "ctm" } });
    });
  });

  it("shows the real empty state when nothing matches", async () => {
    const user = userEvent.setup();
    renderList();
    await waitFor(() => screen.getByText("Purchase Request Approval"));

    await user.type(screen.getByPlaceholderText(/search by name/i), "nothing matches this at all");

    expect(screen.getByText(/no workflows found/i)).toBeInTheDocument();
  });

  it("hides the New Workflow action for a user without workflow:admin", async () => {
    vi.mocked(permissions.hasPermission).mockReturnValue(false);
    renderList();
    await waitFor(() => screen.getByText("Purchase Request Approval"));

    expect(screen.queryByRole("link", { name: /new workflow/i })).not.toBeInTheDocument();
  });

  it("shows the New Workflow action for a user with workflow:admin", async () => {
    renderList();
    await waitFor(() => {
      expect(screen.getByRole("link", { name: /new workflow/i })).toBeInTheDocument();
    });
  });
});
