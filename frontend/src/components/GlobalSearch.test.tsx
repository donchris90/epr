import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { GlobalSearch } from "./GlobalSearch";
import { apiClient } from "../api/client";

vi.mock("../api/client", () => ({
  apiClient: { get: vi.fn() },
}));

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return { ...actual, useNavigate: () => mockNavigate };
});

const SAMPLE_RESULTS = [
  { type: "project", id: "p1", label: "Lekki Tower", status: "active", url: "/projects/p1" },
  { type: "client", id: "c1", label: "Lekki Estate Ltd", status: null, url: "/business-development/clients" },
];

function renderInline() {
  return render(
    <MemoryRouter>
      <GlobalSearch variant="inline" />
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.mocked(apiClient.get).mockResolvedValue({ data: { data: SAMPLE_RESULTS } });
  mockNavigate.mockClear();
});

describe("GlobalSearch", () => {
  it("does not search below the minimum query length", async () => {
    const user = userEvent.setup();
    renderInline();

    await user.type(screen.getByPlaceholderText(/search projects/i), "L");

    await new Promise((r) => setTimeout(r, 300));
    expect(apiClient.get).not.toHaveBeenCalled();
  });

  it("searches and shows real results grouped by type", async () => {
    const user = userEvent.setup();
    renderInline();

    await user.type(screen.getByPlaceholderText(/search projects/i), "Lekki");

    await waitFor(() => {
      expect(screen.getByText("Lekki Tower")).toBeInTheDocument();
      expect(screen.getByText("Lekki Estate Ltd")).toBeInTheDocument();
      expect(screen.getByText("Project")).toBeInTheDocument();
      expect(screen.getByText("Client")).toBeInTheDocument();
    });
    expect(apiClient.get).toHaveBeenCalledWith("/search", { params: { q: "Lekki" } });
  });

  it("shows a real empty state for no matches", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { data: [] } });
    const user = userEvent.setup();
    renderInline();

    await user.type(screen.getByPlaceholderText(/search projects/i), "Zzzz");

    await waitFor(() => {
      expect(screen.getByText(/no matches for "zzzz"/i)).toBeInTheDocument();
    });
  });

  it("navigates to the real result URL on selection", async () => {
    const user = userEvent.setup();
    renderInline();

    await user.type(screen.getByPlaceholderText(/search projects/i), "Lekki");
    await waitFor(() => screen.getByText("Lekki Tower"));

    await user.click(screen.getByText("Lekki Tower"));

    expect(mockNavigate).toHaveBeenCalledWith("/projects/p1");
  });

  it("shows a real error message when the search request fails", async () => {
    vi.mocked(apiClient.get).mockRejectedValue({ response: { data: { title: "Authentication required" } } });
    const user = userEvent.setup();
    renderInline();

    await user.type(screen.getByPlaceholderText(/search projects/i), "Lekki");

    await waitFor(() => {
      expect(screen.getByText("Authentication required")).toBeInTheDocument();
    });
  });

  it("icon variant starts collapsed and expands on click", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <GlobalSearch variant="icon" />
      </MemoryRouter>
    );

    expect(screen.queryByPlaceholderText(/search projects/i)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /search/i }));

    expect(screen.getByPlaceholderText(/search projects/i)).toBeInTheDocument();
  });
});
