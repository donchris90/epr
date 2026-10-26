import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import BankingDetailsCard, { maskAccount } from "./BankingDetailsCard";
import { vendorPortalClient } from "./api/client";

vi.mock("./api/client", () => ({
  vendorPortalClient: { get: vi.fn(), post: vi.fn() },
  getVendorPortalErrorMessage: vi.fn((e: any) => e?.response?.data?.title || "Something went wrong."),
}));
vi.mock("./lib/auth", () => ({ getPortalUserId: () => "vu-1", setPortalTokens: vi.fn(), clearPortalSession: vi.fn() }));

const REQ = (o: any) => ({ id: "r1", vendor_id: "v", proposed_banking_details: { bank_name: "GTBank", account_name: "Acme", account_number: "0123456789" }, status: "pending", submitted_at: "2026-10-01T10:00:00Z", reviewed_at: null, rejection_reason: null, ...o });

function listReturns(rows: any[]) {
  vi.mocked(vendorPortalClient.get).mockResolvedValue({ data: { data: rows } } as any);
}

beforeEach(() => vi.clearAllMocks());

describe("BankingDetailsCard", () => {
  it("masks account numbers", () => {
    expect(maskAccount("0123456789")).toBe("••••6789");
    expect(maskAccount(undefined)).toBe("—");
  });

  it("submits a change request and refreshes the list", async () => {
    const user = userEvent.setup();
    listReturns([]);
    vi.mocked(vendorPortalClient.post).mockResolvedValue({ data: REQ({}) } as any);
    render(<BankingDetailsCard />);

    await user.type(screen.getByLabelText("Bank name"), "GTBank");
    await user.type(screen.getByLabelText("Account name"), "Acme Ltd");
    await user.type(screen.getByLabelText("Account number"), "0123456789");
    await user.click(screen.getByRole("button", { name: /request change/i }));

    await waitFor(() =>
      expect(vendorPortalClient.post).toHaveBeenCalledWith("/vnp/vendor-users/vu-1/banking-change-requests", {
        proposed_banking_details: { bank_name: "GTBank", account_name: "Acme Ltd", account_number: "0123456789" },
      })
    );
    expect(await screen.findByText("Submitted for review.")).toBeInTheDocument();
    expect(vendorPortalClient.get).toHaveBeenCalledTimes(2);
  });

  it("rejects a non-numeric account number without calling the API", async () => {
    const user = userEvent.setup();
    listReturns([]);
    render(<BankingDetailsCard />);
    await user.type(screen.getByLabelText("Bank name"), "GTBank");
    await user.type(screen.getByLabelText("Account name"), "Acme");
    await user.type(screen.getByLabelText("Account number"), "12ab");
    await user.click(screen.getByRole("button", { name: /request change/i }));
    expect(await screen.findByText(/6–20 digits/)).toBeInTheDocument();
    expect(vendorPortalClient.post).not.toHaveBeenCalled();
  });

  it("hides the form while a request is pending and never shows the full number", async () => {
    listReturns([REQ({})]);
    render(<BankingDetailsCard />);
    expect(await screen.findByText(/awaiting review/i)).toBeInTheDocument();
    expect(screen.queryByLabelText("Bank name")).not.toBeInTheDocument();
    expect(screen.getByText(/••••6789/)).toBeInTheDocument();
    expect(screen.queryByText(/0123456789/)).not.toBeInTheDocument();
  });

  it("shows the rejection reason and allows a new request", async () => {
    listReturns([REQ({ status: "rejected", rejection_reason: "Name mismatch" })]);
    render(<BankingDetailsCard />);
    expect(await screen.findByText(/Name mismatch/)).toBeInTheDocument();
    expect(screen.getByLabelText("Bank name")).toBeInTheDocument();
  });
});
