import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ApprovalCenterPage from "./ApprovalCenterPage";
import { apiClient } from "../api/client";

vi.mock("../api/client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

const SAMPLE_DEFINITION = {
  id: "wf1",
  module_name: "ctm",
  entity_type: "contract_amendment",
  workflow_name: "Contract Amendment Approval",
  description: null,
  active: true,
  version: 1,
  created_at: "2026-01-01T00:00:00Z",
  created_by: null,
  updated_at: "2026-01-01T00:00:00Z",
  updated_by: null,
  steps: [
    {
      id: "step-1",
      step_number: 1,
      name: "Finance Approval",
      approver_type: "specific_role",
      required_role_id: "role-1",
      timeout_hours: 24,
      auto_escalate: false,
      allow_skip: false,
      parallel: false,
    },
  ],
};

const SAMPLE_INSTANCE = {
  id: "wi1",
  workflow_id: "wf1",
  module_name: "ctm",
  entity_type: "contract_amendment",
  entity_id: "e1",
  status: "pending",
  current_step_number: 1,
  amount: "5000000",
  initiated_by: "u1",
  created_at: new Date().toISOString(),
  actions: [
    {
      id: "a1",
      step_number: 1,
      action_type: "submitted",
      actor_id: "u1",
      old_status: "draft",
      new_status: "pending",
      comment: "Please review this amendment",
      delegated_to: null,
      created_at: new Date().toISOString(),
    },
  ],
};

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === "/workflow/instances/pending") return Promise.resolve({ data: { data: [SAMPLE_INSTANCE] } });
    if (url === "/workflow/instances") return Promise.resolve({ data: { data: [SAMPLE_INSTANCE] } });
    if (url === "/org/members") return Promise.resolve({ data: { users: [{ id: "u1", email: "requester@example.com" }] } });
    if (url === "/workflow/definitions") return Promise.resolve({ data: { data: [SAMPLE_DEFINITION] } });
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
  vi.mocked(apiClient.post).mockResolvedValue({ data: {} });
});

describe("ApprovalCenterPage", () => {
  it("lists real pending approvals with resolved requester names", async () => {
    render(<ApprovalCenterPage />);
    await waitFor(() => {
      expect(screen.getByText("requester@example.com")).toBeInTheDocument();
      expect(screen.getByText("CTM — contract amendment")).toBeInTheDocument();
    });
  });

  it("shows a real empty state with no pending approvals", async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === "/workflow/instances/pending") return Promise.resolve({ data: { data: [] } });
      if (url === "/org/members") return Promise.resolve({ data: { users: [] } });
      if (url === "/workflow/definitions") return Promise.resolve({ data: { data: [] } });
      return Promise.reject(new Error(`unexpected GET ${url}`));
    });
    render(<ApprovalCenterPage />);
    await waitFor(() => {
      expect(screen.getByText(/no pending approvals/i)).toBeInTheDocument();
    });
  });

  it("opens the detail modal showing the real action history", async () => {
    const user = userEvent.setup();
    render(<ApprovalCenterPage />);
    await waitFor(() => screen.getByText("requester@example.com"));

    await user.click(screen.getByRole("button", { name: /view/i }));

    await waitFor(() => {
      expect(screen.getByText(/please review this amendment/i)).toBeInTheDocument();
    });
  });

  it("approve requires a real confirmation step before calling the endpoint", async () => {
    const user = userEvent.setup();
    render(<ApprovalCenterPage />);
    await waitFor(() => screen.getByText("requester@example.com"));
    await user.click(screen.getByRole("button", { name: /view/i }));
    await waitFor(() => screen.getByRole("button", { name: /^approve$/i }));

    await user.click(screen.getByRole("button", { name: /^approve$/i }));

    expect(await screen.findByText(/approve this request/i)).toBeInTheDocument();
    expect(apiClient.post).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: /yes, confirm/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/workflow/instances/wi1/approve", { comment: undefined });
    });
  });

  it("confirmation can be cancelled without calling the endpoint", async () => {
    const user = userEvent.setup();
    render(<ApprovalCenterPage />);
    await waitFor(() => screen.getByText("requester@example.com"));
    await user.click(screen.getByRole("button", { name: /view/i }));
    await waitFor(() => screen.getByRole("button", { name: /^approve$/i }));

    await user.click(screen.getByRole("button", { name: /^approve$/i }));
    await user.click(screen.getByRole("button", { name: /^cancel$/i }));

    expect(apiClient.post).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /^approve$/i })).toBeInTheDocument();
  });

  it("reject also requires real confirmation, then calls the real endpoint", async () => {
    const user = userEvent.setup();
    render(<ApprovalCenterPage />);
    await waitFor(() => screen.getByText("requester@example.com"));
    await user.click(screen.getByRole("button", { name: /view/i }));
    await waitFor(() => screen.getByRole("button", { name: /^reject$/i }));

    await user.click(screen.getByRole("button", { name: /^reject$/i }));
    expect(await screen.findByText(/reject this request/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /yes, confirm/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/workflow/instances/wi1/reject", { comment: undefined });
    });
  });

  it("delegate requires choosing a real person, confirms, then calls the real endpoint", async () => {
    const user = userEvent.setup();
    render(<ApprovalCenterPage />);
    await waitFor(() => screen.getByText("requester@example.com"));
    await user.click(screen.getByRole("button", { name: /view/i }));
    await waitFor(() => screen.getByRole("button", { name: /^delegate$/i }));

    await user.click(screen.getByRole("button", { name: /^delegate$/i }));
    await user.selectOptions(screen.getByLabelText(/delegate to/i), "u1");
    await user.click(screen.getByRole("button", { name: /confirm delegate/i }));
    expect(await screen.findByText(/delegate to requester@example\.com/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /yes, confirm/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/workflow/instances/wi1/delegate", { delegate_to: "u1", comment: undefined });
    });
  });

  it("switching to All/History calls the real history endpoint", async () => {
    const user = userEvent.setup();
    render(<ApprovalCenterPage />);
    await waitFor(() => screen.getByText("requester@example.com"));

    await user.click(screen.getByRole("button", { name: /all \/ history/i }));

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith("/workflow/instances", { params: undefined });
    });
  });

  it("real module filter is passed to the backend as a query param", async () => {
    const user = userEvent.setup();
    render(<ApprovalCenterPage />);
    await waitFor(() => screen.getByText("requester@example.com"));

    await user.selectOptions(screen.getByLabelText(/module/i), "ctm");

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith("/workflow/instances/pending", { params: { module_name: "ctm" } });
    });
  });

  it("filters client-side by search text", async () => {
    const user = userEvent.setup();
    render(<ApprovalCenterPage />);
    await waitFor(() => screen.getByText("requester@example.com"));

    await user.type(screen.getByPlaceholderText(/requester, module/i), "nothing matches this");

    expect(screen.queryByText("requester@example.com")).not.toBeInTheDocument();
  });

  it("shows a real SLA badge derived from the real workflow definition's timeout", async () => {
    render(<ApprovalCenterPage />);
    await waitFor(() => {
      expect(screen.getAllByText(/within sla|due soon|overdue/i).length).toBeGreaterThan(0);
    });
  });
});
