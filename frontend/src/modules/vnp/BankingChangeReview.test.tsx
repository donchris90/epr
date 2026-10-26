import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import BankingChangeReview from "./BankingChangeReview";
import { apiClient } from "../../api/client";

const pendingRow = {
  id: "r1", vendor_id: "v1234567", vendor_name: "Acme Steel", status: "pending",
  submitted_at: "2026-10-20T10:00:00Z", reviewed_at: null, rejection_reason: null,
  proposed_banking_details: { bank_name: "GTB", account_number: "222" },
  current_banking_details: { bank_name: "GTB", account_number: "111" },
  previous_banking_details: null,
};
const approvedRow = {
  ...pendingRow, id: "r2", status: "approved", reviewed_at: "2026-10-21T10:00:00Z",
  previous_banking_details: { bank_name: "Old Bank", account_number: "999" },
};

function renderIt() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><BankingChangeReview /></QueryClientProvider>);
}

function mockGet(pending: any[], all: any[]) {
  vi.spyOn(apiClient, "get").mockImplementation(async (_u: string, cfg: any) => ({
    data: { data: cfg?.params?.status === "all" ? all : pending },
  }));
}

describe("BankingChangeReview", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("shows the vendor name and marks only changed fields", async () => {
    mockGet([pendingRow], [pendingRow]);
    renderIt();
    expect(await screen.findByText("Acme Steel")).toBeInTheDocument();
    const rows = document.querySelectorAll("tr[data-changed]");
    const changed = Array.from(rows).filter((r) => r.getAttribute("data-changed") === "true");
    expect(changed).toHaveLength(1);
    expect(within(changed[0] as HTMLElement).getByText(/account number/i)).toBeInTheDocument();
  });

  it("needs a second click to approve", async () => {
    mockGet([pendingRow], [pendingRow]);
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: {} });
    renderIt();
    await userEvent.click(await screen.findByRole("button", { name: "Approve" }));
    expect(post).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Confirm approval" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/vnp/banking-change-requests/r1/approve"));
  });

  it("keeps Reject disabled until a reason is typed, then sends it", async () => {
    mockGet([pendingRow], [pendingRow]);
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: {} });
    renderIt();
    const reject = await screen.findByRole("button", { name: "Reject" });
    expect(reject).toBeDisabled();
    await userEvent.type(screen.getByPlaceholderText("Rejection reason"), "Name mismatch");
    await userEvent.click(reject);
    await waitFor(() => expect(post).toHaveBeenCalledWith("/vnp/banking-change-requests/r1/reject", { reason: "Name mismatch" }));
  });

  it("shows the server error when approval fails", async () => {
    mockGet([pendingRow], [pendingRow]);
    vi.spyOn(apiClient, "post").mockRejectedValue({ response: { data: { title: "Banking change request has already been decided" } } });
    renderIt();
    await userEvent.click(await screen.findByRole("button", { name: "Approve" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirm approval" }));
    expect(await screen.findByText(/already been decided/i)).toBeInTheDocument();
  });

  it("history shows decisions and what an approval replaced", async () => {
    mockGet([], [approvedRow]);
    renderIt();
    expect(await screen.findByText("Nothing pending")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "History" }));
    await userEvent.click(await screen.findByRole("button", { name: "Details" }));
    expect(screen.getByText("Old Bank")).toBeInTheDocument();
    expect(screen.getByText("Replaced")).toBeInTheDocument();
  });
});
