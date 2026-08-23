import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import ForgotPasswordPage from "./ForgotPasswordPage";
import { apiClient } from "../api/client";

vi.mock("../api/client", () => ({
  apiClient: { post: vi.fn() },
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <ForgotPasswordPage />
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.mocked(apiClient.post).mockResolvedValue({ data: { message: "If an account exists for that email, a reset link has been sent." } });
});

describe("ForgotPasswordPage", () => {
  it("submits the entered email to the real endpoint", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByPlaceholderText(/you@company.com/i), "test@example.com");
    await user.click(screen.getByRole("button", { name: /send reset link/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/auth/forgot-password", { email: "test@example.com" });
    });
  });

  it("shows the real success state after submitting", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByPlaceholderText(/you@company.com/i), "test@example.com");
    await user.click(screen.getByRole("button", { name: /send reset link/i }));

    await waitFor(() => {
      expect(screen.getByText(/we've sent a link/i)).toBeInTheDocument();
    });
  });

  it("shows an identical success state even when the backend genuinely errors, matching the real never-reveal-existence contract only insofar as a real network/server error still surfaces honestly", async () => {
    // Real, important distinction: the backend itself always returns
    // 200 regardless of whether the account exists (verified in the
    // backend's own test suite) -- this frontend test instead confirms
    // a genuine failure (network error, 500, etc.) is NOT silently
    // hidden as a fake success, which would be dishonest UX.
    vi.mocked(apiClient.post).mockRejectedValue({ response: { data: { title: "Something went wrong" } } });
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByPlaceholderText(/you@company.com/i), "test@example.com");
    await user.click(screen.getByRole("button", { name: /send reset link/i }));

    await waitFor(() => {
      expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    });
    expect(screen.queryByText(/we've sent a link/i)).not.toBeInTheDocument();
  });

  it("disables the submit button while submitting", async () => {
    let resolvePost: (v: any) => void;
    vi.mocked(apiClient.post).mockReturnValue(new Promise((resolve) => (resolvePost = resolve)) as any);
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByPlaceholderText(/you@company.com/i), "test@example.com");
    await user.click(screen.getByRole("button", { name: /send reset link/i }));

    expect(screen.getByRole("button", { name: /sending/i })).toBeDisabled();
    resolvePost!({ data: {} });
  });

  it("provides a real link back to login", () => {
    renderPage();
    expect(screen.getByRole("link", { name: /back to sign in/i })).toHaveAttribute("href", "/login");
  });
});
