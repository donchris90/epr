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
});
