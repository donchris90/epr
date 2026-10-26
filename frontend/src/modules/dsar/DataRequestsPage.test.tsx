import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DataRequestsPage from "./DataRequestsPage";
import { apiClient } from "../../api/client";

vi.mock("../../api/client", () => ({ apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn() } }));

const REQ = (o: any = {}) => ({
  id: "r1", request_type: "erasure", subject_name: "Jane Doe", subject_email: "jane@example.com", subject_phone: null, details: null,
  status: "open", received_at: "2026-10-01T00:00:00Z", due_at: "2026-10-31T00:00:00Z", resolved_at: null, resolution_notes: null,
  actions: [], is_overdue: false, ...o,
});
const HITS = {
  total_matches: 2,
  results: {
    bdc_contacts: [{ id: "c1", table: "bdc_contacts", summary: "BDC contact: Jane Doe" }],
    users: [{ id: "u1", table: "users", summary: "Internal user: jane@example.com" }],
  },
};

function mockGets(requests: any[]) {
  vi.mocked(apiClient.get).mockImplementation((url: string) =>
    Promise.resolve({ data: url === "/dsar/requests" ? { data: requests } : HITS } as any)
  );
}

beforeEach(() => vi.resetAllMocks());

describe("DataRequestsPage", () => {
  it("shows the empty state", async () => {
    mockGets([]);
    render(<DataRequestsPage />);
    expect(await screen.findByText("No data requests logged")).toBeInTheDocument();
  });

  it("lists requests with an overdue badge", async () => {
    mockGets([REQ({ is_overdue: true })]);
    render(<DataRequestsPage />);
    expect(await screen.findByText("Jane Doe")).toBeInTheDocument();
    expect(screen.getByText("Overdue")).toBeInTheDocument();
  });

  it("requires an email or phone when logging a request", async () => {
    const user = userEvent.setup();
    mockGets([]);
    render(<DataRequestsPage />);
    await user.click(await screen.findByRole("button", { name: "Log request" }));
    await user.type(screen.getByLabelText("Person's name"), "Jane");
    await user.click(screen.getByRole("button", { name: "Log request" }));
    expect(await screen.findByText(/Enter an email or phone/)).toBeInTheDocument();
    expect(apiClient.post).not.toHaveBeenCalled();
  });

  it("erases only selected erasable records after confirmation; staff users are manual-only", async () => {
    const user = userEvent.setup();
    mockGets([REQ()]);
    vi.mocked(apiClient.post).mockResolvedValue({ data: REQ() } as any);
    render(<DataRequestsPage />);
    await user.click(await screen.findByText("Jane Doe"));

    const contact = await screen.findByLabelText("BDC contact: Jane Doe");
    expect(screen.getByLabelText("Internal user: jane@example.com")).toBeDisabled();
    expect(screen.getByText("handle manually")).toBeInTheDocument();

    await user.click(contact);
    await user.click(screen.getByRole("button", { name: /Erase selected \(1\)/ }));
    expect(apiClient.post).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Confirm erase" }));

    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith("/dsar/requests/r1/erase", { records: [{ table: "bdc_contacts", id: "c1" }] })
    );
  });

  it("does not offer erasure on an access request", async () => {
    const user = userEvent.setup();
    mockGets([REQ({ request_type: "access" })]);
    render(<DataRequestsPage />);
    await user.click(await screen.findByText("Jane Doe"));
    await screen.findByText("BDC contact: Jane Doe");
    expect(screen.queryByLabelText("BDC contact: Jane Doe")).not.toBeInTheDocument();
  });

  it("closes a request with notes", async () => {
    const user = userEvent.setup();
    mockGets([REQ({ request_type: "access" })]);
    vi.mocked(apiClient.patch).mockResolvedValue({ data: REQ() } as any);
    render(<DataRequestsPage />);
    await user.click(await screen.findByText("Jane Doe"));
    await user.type(await screen.findByLabelText(/Outcome notes/), "Sent export");
    await user.click(screen.getByRole("button", { name: "Mark completed" }));
    await waitFor(() =>
      expect(apiClient.patch).toHaveBeenCalledWith("/dsar/requests/r1", { status: "completed", resolution_notes: "Sent export", notify_requester: true })
    );
  });

  it("lets staff opt out of emailing the requester", async () => {
    const user = userEvent.setup();
    mockGets([REQ({ request_type: "access" })]);
    vi.mocked(apiClient.patch).mockResolvedValue({ data: REQ() } as any);
    render(<DataRequestsPage />);
    await user.click(await screen.findByText("Jane Doe"));
    await user.click(await screen.findByLabelText("Email the requester the outcome"));
    await user.click(screen.getByRole("button", { name: "Mark completed" }));
    await waitFor(() =>
      expect(apiClient.patch).toHaveBeenCalledWith("/dsar/requests/r1", { status: "completed", resolution_notes: null, notify_requester: false })
    );
  });

  it("downloads a data export for an access request", async () => {
    const user = userEvent.setup();
    const click = vi.fn();
    const create = vi.spyOn(document, "createElement");
    (URL as any).createObjectURL = vi.fn(() => "blob:x");
    (URL as any).revokeObjectURL = vi.fn();
    vi.mocked(apiClient.get).mockImplementation((url: string) =>
      Promise.resolve({ data: url === "/dsar/requests" ? { data: [REQ({ request_type: "access" })] } : url.endsWith("/export") ? { total_records: 1, records: {} } : HITS } as any)
    );
    render(<DataRequestsPage />);
    await user.click(await screen.findByText("Jane Doe"));
    create.mockImplementation(((tag: string) => {
      const el = document.createElementNS("http://www.w3.org/1999/xhtml", tag) as any;
      if (tag === "a") el.click = click;
      return el;
    }) as any);
    await user.click(await screen.findByRole("button", { name: "Download data export" }));
    await waitFor(() => expect(apiClient.get).toHaveBeenCalledWith("/dsar/requests/r1/export"));
    await waitFor(() => expect(click).toHaveBeenCalled());
    create.mockRestore();
  });

  it("does not offer export on an erasure request", async () => {
    const user = userEvent.setup();
    mockGets([REQ()]);
    render(<DataRequestsPage />);
    await user.click(await screen.findByText("Jane Doe"));
    await screen.findByText("BDC contact: Jane Doe");
    expect(screen.queryByRole("button", { name: "Download data export" })).toBeNull();
  });

  it("flags an unverified public request and disables its export", async () => {
    const user = userEvent.setup();
    mockGets([REQ({ request_type: "access", source: "public", email_verified: false })]);
    render(<DataRequestsPage />);
    expect(await screen.findByText("Public · unverified")).toBeInTheDocument();
    await user.click(screen.getByText("Jane Doe"));
    expect(await screen.findByRole("note")).toHaveTextContent(/hasn't confirmed their email/);
    expect(screen.getByRole("button", { name: "Download data export" })).toBeDisabled();
  });

  it("shows a verified public request as verified and enables export", async () => {
    const user = userEvent.setup();
    mockGets([REQ({ request_type: "access", source: "public", email_verified: true })]);
    render(<DataRequestsPage />);
    expect(await screen.findByText("Public · verified")).toBeInTheDocument();
    await user.click(screen.getByText("Jane Doe"));
    expect(await screen.findByRole("button", { name: "Download data export" })).toBeEnabled();
  });

  it("shows the shareable public form link for this tenant", async () => {
    const payload = btoa(JSON.stringify({ tenant_id: "t-123" }));
    localStorage.setItem("access_token", `h.${payload}.s`);
    mockGets([]);
    render(<DataRequestsPage />);
    expect(await screen.findByTestId("public-form-link")).toHaveTextContent("/privacy-request/t-123");
    localStorage.removeItem("access_token");
  });
});
