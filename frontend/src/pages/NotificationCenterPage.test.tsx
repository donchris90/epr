import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import NotificationCenterPage from "./NotificationCenterPage";
import { apiClient } from "../api/client";

vi.mock("../api/client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn() },
}));

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return { ...actual, useNavigate: () => mockNavigate };
});

const NOTIFICATIONS = [
  { id: "n1", type: "workflow.approval_requested", title: "PR needs your approval", body: "Purchase Request #100", data: null, read_at: null, created_at: new Date().toISOString() },
  { id: "n2", type: "clp.request_resolved", title: "Your RFI was answered", body: null, data: null, read_at: new Date().toISOString(), created_at: new Date().toISOString() },
  { id: "n3", type: "hse.incident_raised", title: "New safety incident", body: null, data: null, read_at: null, created_at: new Date().toISOString() },
  { id: "n4", type: "system.maintenance", title: "Scheduled maintenance", body: null, data: { entity_type: "purchase_order", entity_id: "po-1" }, read_at: null, created_at: new Date().toISOString() },
];

function renderPage() {
  return render(
    <MemoryRouter>
      <NotificationCenterPage />
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  mockNavigate.mockClear();
  vi.mocked(apiClient.get).mockResolvedValue({ data: { data: NOTIFICATIONS } });
  vi.mocked(apiClient.post).mockResolvedValue({ data: {} });
});

describe("NotificationCenterPage", () => {
  it("loads and lists every real notification for the caller", async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("PR needs your approval")).toBeInTheDocument();
      expect(screen.getByText("Your RFI was answered")).toBeInTheDocument();
      expect(screen.getByText("New safety incident")).toBeInTheDocument();
    });
    expect(apiClient.get).toHaveBeenCalledWith("/notifications", { params: { limit: 200 } });
  });

  it("shows a real error banner when the request fails", async () => {
    vi.mocked(apiClient.get).mockRejectedValue({ response: { data: { title: "Something went wrong" } } });
    renderPage();

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("shows a real, honest empty state with no notifications at all", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { data: [] } });
    renderPage();

    expect(await screen.findByText("No notifications yet.")).toBeInTheDocument();
  });

  it("filters to real Approvals only via the real workflow.* category derivation", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("PR needs your approval"));

    await user.click(screen.getByRole("tab", { name: "Approvals" }));

    expect(screen.getByText("PR needs your approval")).toBeInTheDocument();
    expect(screen.queryByText("Your RFI was answered")).not.toBeInTheDocument();
    expect(screen.queryByText("New safety incident")).not.toBeInTheDocument();
  });

  it("filters to real HSE only via the real hse.* category derivation", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("New safety incident"));

    await user.click(screen.getByRole("tab", { name: "HSE" }));

    expect(screen.getByText("New safety incident")).toBeInTheDocument();
    expect(screen.queryByText("PR needs your approval")).not.toBeInTheDocument();
  });

  it("maps an unrecognized real type prefix to the honest System tab", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("Scheduled maintenance"));

    await user.click(screen.getByRole("tab", { name: "System" }));

    expect(screen.getByText("Scheduled maintenance")).toBeInTheDocument();
  });

  it("filters to only real unread notifications, with a real live count in the tab", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("PR needs your approval"));

    expect(screen.getByRole("tab", { name: /unread \(3\)/i })).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: /unread/i }));

    expect(screen.getByText("PR needs your approval")).toBeInTheDocument();
    expect(screen.queryByText("Your RFI was answered")).not.toBeInTheDocument();
  });

  it("marks a real unread notification read via the real endpoint", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("PR needs your approval"));

    const row = screen.getByText("PR needs your approval").closest("div")!.parentElement!.parentElement!;
    await user.click(within(row).getByRole("button", { name: /mark read/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/notifications/n1/read");
    });
  });

  it("marks a real read notification unread via the real new endpoint", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("Your RFI was answered"));

    const row = screen.getByText("Your RFI was answered").closest("div")!.parentElement!.parentElement!;
    await user.click(within(row).getByRole("button", { name: /mark unread/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/notifications/n2/unread");
    });
  });

  it("marks every real notification read via mark all read", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("PR needs your approval"));

    await user.click(screen.getByRole("button", { name: /mark all read/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/notifications/mark-all-read");
    });
  });

  it("navigates to a real deep link when one exists for the notification's real data", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("Scheduled maintenance"));

    await user.click(screen.getByText("Scheduled maintenance"));

    expect(mockNavigate).toHaveBeenCalledWith("/procurement/orders/po-1");
  });

  it("does not navigate for a real notification with no recognized deep link", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("PR needs your approval"));

    await user.click(screen.getByText("PR needs your approval"));

    expect(mockNavigate).not.toHaveBeenCalled();
  });
});
