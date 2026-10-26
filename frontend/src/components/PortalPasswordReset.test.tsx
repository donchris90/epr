import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { PortalForgotPassword, PortalResetPassword } from "./PortalPasswordReset";

let post = vi.fn();
const cfg = () => ({ client: { post } as any, apiPrefix: "/scp", basePath: "/subcontractor", portalName: "Subcontractor Portal" });

function renderAt(url: string) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/subcontractor/forgot-password" element={<PortalForgotPassword {...cfg()} />} />
        <Route path="/subcontractor/reset-password" element={<PortalResetPassword {...cfg()} />} />
        <Route path="/subcontractor/login" element={<div>login screen</div>} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  post = vi.fn();
});

describe("PortalForgotPassword", () => {
  it("posts the email to the portal's own endpoint and shows a neutral confirmation", async () => {
    const user = userEvent.setup();
    post.mockResolvedValue({ data: {} });
    renderAt("/subcontractor/forgot-password");
    await user.type(screen.getByLabelText(/email/i), "a@b.co");
    await user.click(screen.getByRole("button", { name: /send reset link/i }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/scp/auth/forgot-password", { email: "a@b.co" }));
    expect(await screen.findByText(/if an account exists/i)).toBeInTheDocument();
  });

  it("shows an error when the request fails", async () => {
    const user = userEvent.setup();
    post.mockRejectedValue({ response: { data: { title: "Too many requests" } } });
    renderAt("/subcontractor/forgot-password");
    await user.type(screen.getByLabelText(/email/i), "a@b.co");
    await user.click(screen.getByRole("button", { name: /send reset link/i }));
    expect(await screen.findByText("Too many requests")).toBeInTheDocument();
  });
});

describe("PortalResetPassword", () => {
  it("asks for a new link when the token is missing", () => {
    renderAt("/subcontractor/reset-password");
    expect(screen.getByText(/missing its reset token/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /request a new reset link/i })).toHaveAttribute("href", "/subcontractor/forgot-password");
  });

  it("keeps submit disabled until passwords match, then posts token + password", async () => {
    const user = userEvent.setup();
    post.mockResolvedValue({ data: {} });
    renderAt("/subcontractor/reset-password?token=abc123");
    const button = screen.getByRole("button", { name: /reset password/i });
    await user.type(screen.getByLabelText("New password"), "brandnewpass1");
    await user.type(screen.getByLabelText("Confirm new password"), "different");
    expect(button).toBeDisabled();
    await user.clear(screen.getByLabelText("Confirm new password"));
    await user.type(screen.getByLabelText("Confirm new password"), "brandnewpass1");
    expect(button).toBeEnabled();
    await user.click(button);
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/scp/auth/reset-password", { token: "abc123", new_password: "brandnewpass1" })
    );
    expect(await screen.findByText(/password reset successfully/i)).toBeInTheDocument();
  });

  it("surfaces an invalid/expired link error", async () => {
    const user = userEvent.setup();
    post.mockRejectedValue({ response: { data: { title: "This password reset link is invalid or has expired" } } });
    renderAt("/subcontractor/reset-password?token=bad");
    await user.type(screen.getByLabelText("New password"), "brandnewpass1");
    await user.type(screen.getByLabelText("Confirm new password"), "brandnewpass1");
    await user.click(screen.getByRole("button", { name: /reset password/i }));
    expect(await screen.findByText(/invalid or has expired/i)).toBeInTheDocument();
  });
});
