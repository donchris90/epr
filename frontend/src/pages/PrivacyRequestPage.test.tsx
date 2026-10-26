import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import PrivacyRequestPage from "./PrivacyRequestPage";
import PrivacyRequestVerifyPage from "./PrivacyRequestVerifyPage";
import { apiClient } from "../api/client";

vi.mock("../api/client", () => ({ apiClient: { get: vi.fn(), post: vi.fn() } }));

function renderForm() {
  return render(
    <MemoryRouter initialEntries={["/privacy-request/t1"]}>
      <Routes>
        <Route path="/privacy-request/:tenantId" element={<PrivacyRequestPage />} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => vi.resetAllMocks());

describe("PrivacyRequestPage", () => {
  it("names the company and submits the request to the public endpoint", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { company_name: "Acme Build", response_days: 30 } } as any);
    vi.mocked(apiClient.post).mockResolvedValue({ data: { received: true } } as any);
    const user = userEvent.setup();
    renderForm();
    expect(await screen.findByText("Acme Build")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Your name"), "Jane Doe");
    await user.type(screen.getByLabelText("Your email"), "jane@example.com");
    await user.click(screen.getByRole("button", { name: "Send request" }));
    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith("/public/privacy/t1/requests", {
        request_type: "access", subject_name: "Jane Doe", subject_email: "jane@example.com", subject_phone: null, details: null, website: "",
      })
    );
    expect(await screen.findByRole("status")).toHaveTextContent(/confirmation link/i);
  });

  it("shows the server's error and keeps the form", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { company_name: "Acme Build", response_days: 30 } } as any);
    vi.mocked(apiClient.post).mockRejectedValue({ response: { data: { title: "Too many requests" } } });
    const user = userEvent.setup();
    renderForm();
    await user.type(await screen.findByLabelText("Your name"), "J");
    await user.type(screen.getByLabelText("Your email"), "j@example.com");
    await user.click(screen.getByRole("button", { name: "Send request" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Too many requests");
    expect(screen.getByRole("button", { name: "Send request" })).toBeInTheDocument();
  });

  it("says the link is invalid for an unknown company", async () => {
    vi.mocked(apiClient.get).mockRejectedValue({ response: { status: 404 } });
    renderForm();
    expect(await screen.findByText(/link isn't valid/i)).toBeInTheDocument();
  });
});

describe("PrivacyRequestVerifyPage", () => {
  const renderVerify = (qs: string) =>
    render(
      <MemoryRouter initialEntries={[`/privacy-request/t1/verify${qs}`]}>
        <Routes>
          <Route path="/privacy-request/:tenantId/verify" element={<PrivacyRequestVerifyPage />} />
        </Routes>
      </MemoryRouter>
    );

  it("confirms with the token from the link", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: { verified: true } } as any);
    renderVerify("?token=abc");
    expect(await screen.findByRole("status")).toHaveTextContent(/email is confirmed/i);
    expect(apiClient.post).toHaveBeenCalledWith("/public/privacy/t1/verify", { token: "abc" });
  });

  it("reports a bad or missing token", async () => {
    vi.mocked(apiClient.post).mockRejectedValue({ response: { status: 400 } });
    renderVerify("?token=bad");
    expect(await screen.findByRole("alert")).toHaveTextContent(/invalid or has expired/i);
  });

  it("does not call the API without a token", async () => {
    renderVerify("");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(apiClient.post).not.toHaveBeenCalled();
  });
});
