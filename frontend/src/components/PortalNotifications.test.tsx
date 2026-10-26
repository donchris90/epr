import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { PortalNotificationBell, PortalNotificationsPage } from "./PortalNotifications";

const N = (o: any) => ({ id: "n1", type: "scp.claim_rejected", title: "Your claim was rejected", body: "Not substantiated", data: null, read_at: null, created_at: new Date().toISOString(), ...o });

let get: ReturnType<typeof vi.fn>;
let post: ReturnType<typeof vi.fn>;
const linkFor = (n: any) => (n.type.startsWith("scp.claim") ? "/subcontractor/claims" : null);

function Where() {
  return <div data-testid="where">{useLocation().pathname}</div>;
}

function setup(ui: (client: any) => JSX.Element, items: any[], unread = items.filter((i) => !i.read_at).length) {
  get = vi.fn((url: string) =>
    Promise.resolve({ data: url.endsWith("unread-count") ? { unread_count: unread } : { data: items } })
  );
  post = vi.fn().mockResolvedValue({ data: {} });
  const client = { get, post };
  return render(
    <MemoryRouter initialEntries={["/start"]}>
      <Routes>
        <Route path="*" element={<>{ui(client)}<Where /></>} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => vi.clearAllMocks());

describe("PortalNotificationBell", () => {
  it("shows the unread badge, lists items, marks read and navigates on click", async () => {
    const user = userEvent.setup();
    setup((client) => <PortalNotificationBell client={client} allPath="/subcontractor/notifications" linkFor={linkFor} />, [N({})]);
    expect(await screen.findByTestId("unread-badge")).toHaveTextContent("1");

    await user.click(screen.getByLabelText("Notifications"));
    await user.click(await screen.findByText("Your claim was rejected"));

    await waitFor(() => expect(post).toHaveBeenCalledWith("/notifications/n1/read"));
    expect(screen.getByTestId("where")).toHaveTextContent("/subcontractor/claims");
    expect(screen.queryByTestId("unread-badge")).not.toBeInTheDocument();
  });

  it("shows an empty state and no badge when there is nothing", async () => {
    const user = userEvent.setup();
    setup((client) => <PortalNotificationBell client={client} allPath="/x" linkFor={linkFor} />, []);
    await user.click(screen.getByLabelText("Notifications"));
    expect(await screen.findByText(/no notifications yet/i)).toBeInTheDocument();
    expect(screen.queryByTestId("unread-badge")).not.toBeInTheDocument();
  });

  it("mark all read posts and clears the badge", async () => {
    const user = userEvent.setup();
    setup((client) => <PortalNotificationBell client={client} allPath="/x" linkFor={linkFor} />, [N({}), N({ id: "n2" })]);
    expect(await screen.findByTestId("unread-badge")).toHaveTextContent("2");
    await user.click(screen.getByLabelText("Notifications"));
    await user.click(await screen.findByText("Mark all read"));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/notifications/mark-all-read"));
    expect(screen.queryByTestId("unread-badge")).not.toBeInTheDocument();
  });
});

describe("PortalNotificationsPage", () => {
  it("lists notifications and marks one read when opened", async () => {
    const user = userEvent.setup();
    setup((client) => <PortalNotificationsPage client={client} linkFor={() => null} />, [N({})]);
    await user.click(await screen.findByText("Your claim was rejected"));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/notifications/n1/read"));
  });

  it("shows the empty state", async () => {
    setup((client) => <PortalNotificationsPage client={client} linkFor={() => null} />, []);
    expect(await screen.findByText("No notifications yet")).toBeInTheDocument();
  });
});
