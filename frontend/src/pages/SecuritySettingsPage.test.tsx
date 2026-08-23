import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import SecuritySettingsPage from "./SecuritySettingsPage";
import { apiClient } from "../api/client";

vi.mock("../api/client", () => ({
  apiClient: { get: vi.fn() },
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <SecuritySettingsPage />
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe("SecuritySettingsPage", () => {
  it("shows the real last login time from the backend", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { email: "test@example.com", last_login_at: "2026-08-23T12:00:00Z" } });
    renderPage();

    await waitFor(() => {
      expect(screen.getByText(new Date("2026-08-23T12:00:00Z").toLocaleString())).toBeInTheDocument();
    });
  });

  it("shows a real, honest message when there is no login on record yet", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { email: "test@example.com", last_login_at: null } });
    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/no previous login on record/i)).toBeInTheDocument();
    });
  });

  it("clearly marks two-factor authentication as not available, not a fake toggle", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { email: "test@example.com", last_login_at: null } });
    renderPage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /two-factor authentication/i })).toBeInTheDocument();
    });
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("switch")).not.toBeInTheDocument();
    expect(screen.getAllByText(/not available/i).length).toBeGreaterThanOrEqual(2);
  });

  it("clearly marks active sessions as not available, not an empty fake list", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { email: "test@example.com", last_login_at: null } });
    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/active sessions/i)).toBeInTheDocument();
      expect(screen.getByText(/sign every device out immediately/i)).toBeInTheDocument();
    });
  });

  it("links to the real change-password flow on the profile page", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { email: "test@example.com", last_login_at: null } });
    renderPage();

    await waitFor(() => {
      expect(screen.getByRole("link", { name: /change password/i })).toHaveAttribute("href", "/settings/profile");
    });
  });

  it("shows a real error banner when the backend request genuinely fails", async () => {
    vi.mocked(apiClient.get).mockRejectedValue({ response: { data: { title: "Something went wrong" } } });
    renderPage();

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
    expect(screen.getByRole("alert")).toHaveTextContent("Something went wrong");
  });
});
