import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import ResetPasswordPage from "./ResetPasswordPage";
import { apiClient } from "../api/client";

vi.mock("../api/client", () => ({
  apiClient: { post: vi.fn() },
}));

function renderPage(initialPath = "/reset-password?token=real-test-token") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/reset-password" element={<ResetPasswordPage />} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(apiClient.post).mockResolvedValue({ data: { message: "Password reset successfully." } });
});

describe("ResetPasswordPage", () => {
  it("reads the real token from the URL and submits it with the new password", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText(/^new password/i), "brandnewpassword456");
    await user.type(screen.getByLabelText(/confirm new password/i), "brandnewpassword456");
    await user.click(screen.getByRole("button", { name: /reset password/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/auth/reset-password", { token: "real-test-token", new_password: "brandnewpassword456" });
    });
  });

  it("shows a real error and never submits when no token is present in the URL", () => {
    renderPage("/reset-password");
    expect(screen.getByText(/missing its reset token/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /reset password/i })).not.toBeInTheDocument();
  });

  it("blocks submission client-side when passwords do not match", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText(/^new password/i), "brandnewpassword456");
    await user.type(screen.getByLabelText(/confirm new password/i), "differentpassword789");

    expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reset password/i })).toBeDisabled();
    expect(apiClient.post).not.toHaveBeenCalled();
  });

  it("blocks submission client-side when the password is shorter than 8 characters", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText(/^new password/i), "short");
    await user.type(screen.getByLabelText(/confirm new password/i), "short");

    expect(screen.getByRole("button", { name: /reset password/i })).toBeDisabled();
  });

  it("shows the real strength meter as the password is typed", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText(/^new password/i), "weak");
    expect(screen.getByText(/too short/i)).toBeInTheDocument();
  });

  it("shows a real success state and mentions sessions being signed out", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText(/^new password/i), "brandnewpassword456");
    await user.type(screen.getByLabelText(/confirm new password/i), "brandnewpassword456");
    await user.click(screen.getByRole("button", { name: /reset password/i }));

    await waitFor(() => {
      expect(screen.getByText(/reset successfully/i)).toBeInTheDocument();
      expect(screen.getByText(/all existing sessions/i)).toBeInTheDocument();
    });
  });

  it("shows the real backend error for an expired/invalid token", async () => {
    vi.mocked(apiClient.post).mockRejectedValue({ response: { data: { title: "This password reset link is invalid or has expired" } } });
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText(/^new password/i), "brandnewpassword456");
    await user.type(screen.getByLabelText(/confirm new password/i), "brandnewpassword456");
    await user.click(screen.getByRole("button", { name: /reset password/i }));

    await waitFor(() => {
      expect(screen.getByText(/invalid or has expired/i)).toBeInTheDocument();
    });
  });
});
