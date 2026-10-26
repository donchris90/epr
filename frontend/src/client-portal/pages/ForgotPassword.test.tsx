import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import ForgotPasswordPage from "./ForgotPasswordPage";
import { clientPortalClient } from "../api/client";

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/portal/forgot-password"]}>
      <Routes>
        <Route path="/portal/forgot-password" element={<ForgotPasswordPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("Client portal ForgotPasswordPage", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("posts to the client portal endpoint and shows a neutral confirmation", async () => {
    const post = vi.spyOn(clientPortalClient, "post").mockResolvedValue({ data: {} });
    renderPage();
    await userEvent.type(screen.getByLabelText(/email/i), "c@client.co");
    await userEvent.click(screen.getByRole("button", { name: /send reset link/i }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/clp/auth/forgot-password", { email: "c@client.co" }));
    expect(await screen.findByText(/if an account exists/i)).toBeInTheDocument();
  });
});
