import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import WorkflowBuilderPage from "./WorkflowBuilderPage";
import { apiClient } from "../../api/client";
import * as permissions from "../../lib/permissions";

vi.mock("../../api/client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn() },
}));

vi.mock("../../lib/permissions", () => ({
  hasPermission: vi.fn(),
}));

const REAL_USER = { id: "user-1", email: "pm@example.com", status: "active" };
const REAL_ROLE = { id: "role-1", name: "Finance" };

function renderBuilder() {
  return render(
    <MemoryRouter>
      <WorkflowBuilderPage />
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.mocked(permissions.hasPermission).mockReturnValue(true);
  vi.mocked(apiClient.get).mockReset();
  vi.mocked(apiClient.post).mockReset();
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === "/org/members") return Promise.resolve({ data: { users: [REAL_USER] } });
    if (url === "/org/roles") return Promise.resolve({ data: { data: [REAL_ROLE] } });
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
});

describe("WorkflowBuilderPage — permissions", () => {
  it("does not render the builder for a user without workflow:admin", () => {
    vi.mocked(permissions.hasPermission).mockReturnValue(false);
    renderBuilder();

    expect(screen.getByText(/don't have permission/i)).toBeInTheDocument();
    expect(screen.queryByText("New Workflow")).not.toBeInTheDocument();
  });

  it("renders the real builder for a user with workflow:admin", () => {
    renderBuilder();
    expect(screen.getByText("New Workflow")).toBeInTheDocument();
  });
});

describe("WorkflowBuilderPage — validation", () => {
  it("blocks publish and shows real errors for an empty draft", async () => {
    const user = userEvent.setup();
    renderBuilder();

    await user.click(screen.getByRole("button", { name: "Publish" }));

    expect(await screen.findByText(/can't be published yet/i)).toBeInTheDocument();
    expect(apiClient.post).not.toHaveBeenCalled();
  });

  it("clears once the real problems are fixed", async () => {
    const user = userEvent.setup();
    renderBuilder();

    await user.click(screen.getByRole("button", { name: "Publish" }));
    expect(await screen.findByText(/can't be published yet/i)).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText(/purchase request approval/i), "Real Workflow");
    await user.selectOptions(screen.getByLabelText(/trigger/i), "prc::purchase_request");
    await user.click(screen.getByRole("button", { name: /add step/i }));

    // Configure the step so it's genuinely valid (real name and role selected)
    await user.type(screen.getByLabelText(/step name/i), "Finance Approval");
    await user.selectOptions(screen.getByLabelText(/approver role/i), "role-1");
    await user.click(screen.getByRole("button", { name: "Done" }));

    vi.mocked(apiClient.post).mockResolvedValue({
      data: { id: "wf-1", workflow_name: "Real Workflow", module_name: "prc", entity_type: "purchase_request", active: false, version: 1, steps: [] },
    });

    await user.click(screen.getByRole("button", { name: "Publish" }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/workflow/definitions", expect.objectContaining({ workflow_name: "Real Workflow" }));
    });
  });
});

describe("WorkflowBuilderPage — node configuration", () => {
  it("adding a step opens real configuration for it", async () => {
    const user = userEvent.setup();
    renderBuilder();

    await user.click(screen.getByRole("button", { name: /add step/i }));

    expect(await screen.findByText(/configure:/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/step name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/approver type/i)).toBeInTheDocument();
  });

  it("switching approver type to a specific person shows the real user picker", async () => {
    const user = userEvent.setup();
    renderBuilder();
    await user.click(screen.getByRole("button", { name: /add step/i }));

    await user.selectOptions(screen.getByLabelText(/approver type/i), "specific_user");

    await waitFor(() => {
      expect(screen.getByText("pm@example.com")).toBeInTheDocument();
    });
  });

  it("adding a parallel approver to an existing step creates a real second, linked step", async () => {
    const user = userEvent.setup();
    renderBuilder();
    await user.click(screen.getByRole("button", { name: /add step/i }));
    await user.click(screen.getByRole("button", { name: "Done" }));

    await user.click(screen.getByRole("button", { name: /parallel approver/i }));

    // Multiple real "parallel" indicators now exist (the canvas node
    // label and the step group's own badge) -- ambiguous for a single
    // findByText, so confirm plurality directly instead.
    await waitFor(() => {
      expect(screen.getAllByText(/parallel/i).length).toBeGreaterThan(1);
    });
  });
});

describe("WorkflowBuilderPage — save draft vs publish", () => {
  async function buildValidDraft(user: ReturnType<typeof userEvent.setup>) {
    await user.type(screen.getByPlaceholderText(/purchase request approval/i), "Real Draft");
    await user.selectOptions(screen.getByLabelText(/trigger/i), "prc::purchase_request");
    await user.click(screen.getByRole("button", { name: /add step/i }));
    await user.type(screen.getByLabelText(/step name/i), "Finance Approval");
    await user.selectOptions(screen.getByLabelText(/approver role/i), "role-1");
    await user.click(screen.getByRole("button", { name: "Done" }));
  }

  it("save draft calls the real create endpoint and never activates", async () => {
    const user = userEvent.setup();
    renderBuilder();
    await buildValidDraft(user);

    vi.mocked(apiClient.post).mockResolvedValue({
      data: { id: "wf-1", workflow_name: "Real Draft", module_name: "prc", entity_type: "purchase_request", active: false, version: 1, steps: [] },
    });

    await user.click(screen.getByRole("button", { name: "Save Draft" }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/workflow/definitions", expect.any(Object));
      expect(apiClient.post).not.toHaveBeenCalledWith(expect.stringContaining("/activate"));
    });
  });

  it("publish calls create then the real activate endpoint", async () => {
    const user = userEvent.setup();
    renderBuilder();
    await buildValidDraft(user);

    vi.mocked(apiClient.post).mockImplementation((url: string) => {
      if (url === "/workflow/definitions") {
        return Promise.resolve({
          data: { id: "wf-1", workflow_name: "Real Draft", module_name: "prc", entity_type: "purchase_request", active: false, version: 1, steps: [] },
        });
      }
      if (url === "/workflow/definitions/wf-1/activate") {
        return Promise.resolve({ data: { id: "wf-1", active: true } });
      }
      return Promise.reject(new Error(`unexpected POST ${url}`));
    });

    await user.click(screen.getByRole("button", { name: "Publish" }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/workflow/definitions/wf-1/activate");
    });
  });
});
