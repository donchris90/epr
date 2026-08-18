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
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === "/workflow/instances/pending") return Promise.resolve({ data: { data: [SAMPLE_INSTANCE] } });
    if (url === "/workflow/instances") return Promise.resolve({ data: { data: [SAMPLE_INSTANCE] } });
    if (url === "/org/members") return Promise.resolve({ data: { users: [{ id: "u1", email: "requester@example.com" }] } });
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

  it("calls the real approve endpoint", async () => {
    const user = userEvent.setup();
    render(<ApprovalCenterPage />);
    await waitFor(() => screen.getByText("requester@example.com"));
    await user.click(screen.getByRole("button", { name: /view/i }));
    await waitFor(() => screen.getByRole("button", { name: /^approve$/i }));

    await user.click(screen.getByRole("button", { name: /^approve$/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/workflow/instances/wi1/approve", { comment: undefined });
    });
  });

  it("calls the real reject endpoint", async () => {
    const user = userEvent.setup();
    render(<ApprovalCenterPage />);
    await waitFor(() => screen.getByText("requester@example.com"));
    await user.click(screen.getByRole("button", { name: /view/i }));
    await waitFor(() => screen.getByRole("button", { name: /^reject$/i }));

    await user.click(screen.getByRole("button", { name: /^reject$/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/workflow/instances/wi1/reject", { comment: undefined });
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
});
