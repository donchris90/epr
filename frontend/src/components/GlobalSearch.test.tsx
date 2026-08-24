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
      expect(screen.getAllByText("Project").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Client").length).toBeGreaterThan(0);
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

  describe("keyboard navigation", () => {
    it("navigates results with arrow keys and selects the real active one with Enter", async () => {
      const user = userEvent.setup();
      renderInline();

      const input = screen.getByPlaceholderText(/search projects/i);
      await user.type(input, "Lekki");
      await waitFor(() => screen.getByText("Lekki Tower"));

      await user.keyboard("{ArrowDown}{ArrowDown}{Enter}");

      expect(mockNavigate).toHaveBeenCalledWith("/business-development/clients");
    });

    it("closes the dropdown on Escape without navigating", async () => {
      const user = userEvent.setup();
      renderInline();

      const input = screen.getByPlaceholderText(/search projects/i);
      await user.type(input, "Lekki");
      await waitFor(() => screen.getByText("Lekki Tower"));

      await user.keyboard("{Escape}");

      await waitFor(() => {
        expect(screen.queryByText("Lekki Tower")).not.toBeInTheDocument();
      });
      expect(mockNavigate).not.toHaveBeenCalled();
    });
  });

  describe("module filtering", () => {
    it("shows real filter chips only when more than one real result type is present", async () => {
      const user = userEvent.setup();
      renderInline();

      await user.type(screen.getByPlaceholderText(/search projects/i), "Lekki");
      await waitFor(() => screen.getByText("Lekki Tower"));

      expect(screen.getByRole("button", { name: "All" })).toBeInTheDocument();
    });

    it("filters to only the real selected type when a filter chip is clicked", async () => {
      const user = userEvent.setup();
      renderInline();

      await user.type(screen.getByPlaceholderText(/search projects/i), "Lekki");
      await waitFor(() => screen.getByText("Lekki Tower"));

      await user.click(screen.getByRole("button", { name: "Client" }));

      expect(screen.queryByText("Lekki Tower")).not.toBeInTheDocument();
      expect(screen.getByText("Lekki Estate Ltd")).toBeInTheDocument();
    });

    it("does not show filter chips when there is only one real result type", async () => {
      vi.mocked(apiClient.get).mockResolvedValue({ data: { data: [SAMPLE_RESULTS[0]] } });
      const user = userEvent.setup();
      renderInline();

      await user.type(screen.getByPlaceholderText(/search projects/i), "Lekki");
      await waitFor(() => screen.getByText("Lekki Tower"));

      expect(screen.queryByRole("button", { name: "All" })).not.toBeInTheDocument();
    });
  });

  describe("recent searches", () => {
    beforeEach(() => {
      localStorage.clear();
    });

    it("saves a real completed search to recent searches", async () => {
      const user = userEvent.setup();
      renderInline();

      await user.type(screen.getByPlaceholderText(/search projects/i), "Lekki");
      await waitFor(() => screen.getByText("Lekki Tower"));

      expect(JSON.parse(localStorage.getItem("sf_recent_searches") ?? "[]")).toContain("Lekki");
    });

    it("shows real recent searches in the icon variant when the input is focused but empty", async () => {
      localStorage.setItem("sf_recent_searches", JSON.stringify(["Konga", "Dangote"]));
      const user = userEvent.setup();
      render(
        <MemoryRouter>
          <GlobalSearch variant="icon" />
        </MemoryRouter>
      );

      await user.click(screen.getByRole("button", { name: /search/i }));

      expect(screen.getByText("Konga")).toBeInTheDocument();
      expect(screen.getByText("Dangote")).toBeInTheDocument();
    });

    it("clicking a real recent search re-runs it", async () => {
      localStorage.setItem("sf_recent_searches", JSON.stringify(["Lekki"]));
      const user = userEvent.setup();
      render(
        <MemoryRouter>
          <GlobalSearch variant="icon" />
        </MemoryRouter>
      );

      await user.click(screen.getByRole("button", { name: /search/i }));
      await user.click(screen.getByText("Lekki"));

      await waitFor(() => {
        expect(apiClient.get).toHaveBeenCalledWith("/search", { params: { q: "Lekki" } });
      });
    });
  });
});
