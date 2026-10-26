import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import RfqInvitationsPage from "./RfqInvitationsPage";
import { vendorPortalClient } from "../api/client";

vi.mock("../lib/auth", async (orig) => ({ ...(await orig<any>()), getPortalUserId: () => "u1" }));

const base = {
  invitation_id: "i1", rfq_id: "r1", title: "Cement supply", description: "500 bags", response_deadline: null,
  rfq_status: "open", invitation_status: "invited", quote: null, can_quote: true,
};

function renderPage() {
  return render(<MemoryRouter><RfqInvitationsPage /></MemoryRouter>);
}

describe("RfqInvitationsPage", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("shows an honest empty state", async () => {
    vi.spyOn(vendorPortalClient, "get").mockResolvedValue({ data: { data: [] } });
    renderPage();
    expect(await screen.findByText(/not been invited/i)).toBeInTheDocument();
  });

  it("submits a quote and reloads", async () => {
    const get = vi.spyOn(vendorPortalClient, "get")
      .mockResolvedValueOnce({ data: { data: [base] } })
      .mockResolvedValueOnce({ data: { data: [{ ...base, can_quote: false, quote: { id: "q", rfq_id: "r1", price: "1500", lead_time_days: 5, payment_terms: "Net 30" } }] } });
    const post = vi.spyOn(vendorPortalClient, "post").mockResolvedValue({ data: {} });
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Submit a quote" }));
    await userEvent.type(screen.getByLabelText("Price"), "1500");
    await userEvent.type(screen.getByLabelText("Lead time (days)"), "5");
    await userEvent.click(screen.getByRole("button", { name: "Submit quote" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/vnp/vendor-users/u1/quotes", { rfq_id: "r1", price: "1500", lead_time_days: 5, payment_terms: undefined }));
    expect(await screen.findByText("Quote submitted")).toBeInTheDocument();
    expect(get).toHaveBeenCalledTimes(2);
  });

  it("shows the server's error when a quote is refused", async () => {
    vi.spyOn(vendorPortalClient, "get").mockResolvedValue({ data: { data: [base] } });
    vi.spyOn(vendorPortalClient, "post").mockRejectedValue({ response: { data: { title: "This RFQ is closed or past its response deadline" } } });
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Submit a quote" }));
    await userEvent.type(screen.getByLabelText("Price"), "10");
    await userEvent.click(screen.getByRole("button", { name: "Submit quote" }));
    expect(await screen.findByText(/closed or past/i)).toBeInTheDocument();
  });

  it("offers no quote button when the RFQ is closed", async () => {
    vi.spyOn(vendorPortalClient, "get").mockResolvedValue({ data: { data: [{ ...base, can_quote: false, rfq_status: "closed" }] } });
    renderPage();
    expect(await screen.findByText("Closed")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Submit a quote" })).toBeNull();
  });

  it("declines an invitation with a reason", async () => {
    const get = vi.spyOn(vendorPortalClient, "get")
      .mockResolvedValueOnce({ data: { data: [{ ...base, can_decline: true }] } })
      .mockResolvedValueOnce({ data: { data: [{ ...base, invitation_status: "declined", decline_reason: "No stock", can_quote: false, can_decline: false }] } });
    const post = vi.spyOn(vendorPortalClient, "post").mockResolvedValue({ data: {} });
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Decline" }));
    await userEvent.type(screen.getByLabelText("Reason (optional)"), "No stock");
    await userEvent.click(screen.getByRole("button", { name: "Confirm decline" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/vnp/vendor-users/u1/rfq-invitations/r1/decline", { reason: "No stock" }));
    expect(await screen.findByText("Declined")).toBeInTheDocument();
    expect(screen.getByText(/No stock/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Submit a quote" })).toBeNull();
    expect(get).toHaveBeenCalledTimes(2);
  });

  it("offers Decline only when the server says it is allowed", async () => {
    vi.spyOn(vendorPortalClient, "get").mockResolvedValue({ data: { data: [base] } });
    renderPage();
    await screen.findByRole("button", { name: "Submit a quote" });
    expect(screen.queryByRole("button", { name: "Decline" })).toBeNull();
  });

  it("revises an existing quote with the current values prefilled", async () => {
    const quoted = { ...base, can_quote: false, can_revise: true, invitation_status: "responded",
      quote: { id: "q", rfq_id: "r1", price: "1500.0000", lead_time_days: 5, payment_terms: "Net 30", revision_count: 0 } };
    const get = vi.spyOn(vendorPortalClient, "get")
      .mockResolvedValueOnce({ data: { data: [quoted] } })
      .mockResolvedValueOnce({ data: { data: [{ ...quoted, quote: { ...quoted.quote, price: "1200.0000", revision_count: 1 } }] } });
    const put = vi.spyOn(vendorPortalClient, "put").mockResolvedValue({ data: {} });
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Revise quote" }));
    const price = screen.getByLabelText("Price") as HTMLInputElement;
    expect(price.value).toBe("1500");
    await userEvent.clear(price);
    await userEvent.type(price, "1200");
    await userEvent.click(screen.getByRole("button", { name: "Save revised quote" }));
    await waitFor(() => expect(put).toHaveBeenCalledWith("/vnp/vendor-users/u1/quotes/r1", { price: "1200", lead_time_days: 5, payment_terms: "Net 30" }));
    expect(await screen.findByText(/revised 1×/)).toBeInTheDocument();
    expect(get).toHaveBeenCalledTimes(2);
  });

  it("shows the server's error when a revision is refused", async () => {
    const quoted = { ...base, can_quote: false, can_revise: true, quote: { id: "q", rfq_id: "r1", price: "10", lead_time_days: null, payment_terms: null } };
    vi.spyOn(vendorPortalClient, "get").mockResolvedValue({ data: { data: [quoted] } });
    vi.spyOn(vendorPortalClient, "put").mockRejectedValue({ response: { data: { title: "This RFQ is closed or past its response deadline" } } });
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Revise quote" }));
    await userEvent.click(screen.getByRole("button", { name: "Save revised quote" }));
    expect(await screen.findByText(/closed or past/i)).toBeInTheDocument();
  });
});
