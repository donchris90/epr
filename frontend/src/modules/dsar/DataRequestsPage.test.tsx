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
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
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
      expect(apiClient.patch).toHaveBeenCalledWith("/dsar/requests/r1", { status: "completed", resolution_notes: "Sent export" })
    );
  });
});
