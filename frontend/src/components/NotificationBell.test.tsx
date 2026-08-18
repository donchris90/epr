import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NotificationBell } from "./NotificationBell";
import { apiClient } from "../api/client";

vi.mock("../api/client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

const SAMPLE_NOTIFICATIONS = [
  {
    id: "n1",
    type: "workflow.approval_requested",
    title: "Approval needed",
    body: "A purchase order needs your approval",
    data: { entity_type: "purchase_order", entity_id: "po-123" },
    read_at: null,
    created_at: new Date().toISOString(),
  },
  {
    id: "n2",
    type: "workflow.approval_requested",
    title: "Already read",
    body: null,
    data: null,
    read_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
  },
];

beforeEach(() => {
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === "/notifications/unread-count") return Promise.resolve({ data: { unread_count: 1 } });
    if (url === "/notifications") return Promise.resolve({ data: { data: SAMPLE_NOTIFICATIONS } });
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
  vi.mocked(apiClient.post).mockResolvedValue({ data: {} });
});

describe("NotificationBell", () => {
  it("shows the real unread count as a badge", async () => {
    render(<NotificationBell />);
    await waitFor(() => {
      expect(screen.getByText("1")).toBeInTheDocument();
    });
  });

  it("opens the dropdown and lists real notifications on click", async () => {
    const user = userEvent.setup();
    render(<NotificationBell />);

    await user.click(screen.getByRole("button", { name: /notifications/i }));

    await waitFor(() => {
      expect(screen.getByText("Approval needed")).toBeInTheDocument();
      expect(screen.getByText("Already read")).toBeInTheDocument();
    });
  });

  it("marks an unread notification read on click, calling the real endpoint", async () => {
    const user = userEvent.setup();
    render(<NotificationBell />);

    await user.click(screen.getByRole("button", { name: /notifications/i }));
    await waitFor(() => screen.getByText("Approval needed"));
    await user.click(screen.getByText("Approval needed"));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/notifications/n1/read");
    });
  });

  it("mark all read calls the real endpoint and clears the badge", async () => {
    const user = userEvent.setup();
    render(<NotificationBell />);

    await user.click(screen.getByRole("button", { name: /notifications/i }));
    await waitFor(() => screen.getByText("Mark all read"));
    await user.click(screen.getByText("Mark all read"));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/notifications/mark-all-read");
    });
    expect(screen.queryByText("1")).not.toBeInTheDocument();
  });

  it("does not navigate for a notification with no recognized deep link", async () => {
    const user = userEvent.setup();
    const originalHref = window.location.href;
    render(<NotificationBell />);

    await user.click(screen.getByRole("button", { name: /notifications/i }));
    await waitFor(() => screen.getByText("Already read"));
    await user.click(screen.getByText("Already read"));

    // "Already read" has data: null -- no deep link should be
    // attempted, and clicking an already-read notification should
    // not call the mark-read endpoint again either.
    expect(window.location.href).toBe(originalHref);
    expect(apiClient.post).not.toHaveBeenCalledWith("/notifications/n2/read");
  });
});
