import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import NotificationPreferencesPage from "./NotificationPreferencesPage";
import { apiClient } from "../api/client";

vi.mock("../api/client", () => ({
  apiClient: { get: vi.fn(), put: vi.fn() },
}));

const PREFS = ["approvals", "projects", "finance", "hse", "system"].map((category) => ({
  category,
  in_app: true,
  email: true,
}));

beforeEach(() => {
  vi.resetAllMocks();
});

describe("NotificationPreferencesPage", () => {
  it("loads and shows every category", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { preferences: PREFS } });
    render(<NotificationPreferencesPage />);
    expect(await screen.findByLabelText("Finance email")).toBeChecked();
    expect(screen.getByLabelText("HSE in-app")).toBeChecked();
  });

  it("saves toggled values", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { preferences: PREFS } });
    const saved = PREFS.map((p) => (p.category === "finance" ? { ...p, email: false } : p));
    vi.mocked(apiClient.put).mockResolvedValue({ data: { preferences: saved } });
    render(<NotificationPreferencesPage />);
    await userEvent.click(await screen.findByLabelText("Finance email"));
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(screen.getByText("Saved")).toBeInTheDocument());
    const body = vi.mocked(apiClient.put).mock.calls[0][1] as any;
    expect(body.preferences.find((p: any) => p.category === "finance").email).toBe(false);
    expect(body.preferences.find((p: any) => p.category === "approvals").email).toBe(true);
  });

  it("shows an error when saving fails", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { preferences: PREFS } });
    vi.mocked(apiClient.put).mockRejectedValue({ response: { data: { title: "Invalid preferences" } } });
    render(<NotificationPreferencesPage />);
    await userEvent.click(await screen.findByRole("button", { name: "Save" }));
    expect(await screen.findByText("Invalid preferences")).toBeInTheDocument();
  });
});
