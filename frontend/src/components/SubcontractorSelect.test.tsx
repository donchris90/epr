import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SubcontractorSelect } from "./SubcontractorSelect";
import { apiClient } from "../api/client";

vi.mock("../api/client", () => ({
  apiClient: { get: vi.fn() },
}));

beforeEach(() => {
  vi.resetAllMocks();
});

describe("SubcontractorSelect", () => {
  it("loads and shows real subcontractors from the backend", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: { data: [{ id: "s1", name: "Prime Electrical Co", trade_specialty: "electrical", status: "active" }] },
    });
    const user = userEvent.setup();
    render(<SubcontractorSelect value="" onChange={vi.fn()} />);

    await user.click(screen.getByRole("combobox"));

    expect(await screen.findByText("Prime Electrical Co")).toBeInTheDocument();
    expect(apiClient.get).toHaveBeenCalledWith("/sub/subcontractors");
  });

  it("calls onChange with the real subcontractor id on selection", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: { data: [{ id: "s1", name: "Prime Electrical Co", trade_specialty: "electrical", status: "active" }] },
    });
    const handleChange = vi.fn();
    const user = userEvent.setup();
    render(<SubcontractorSelect value="" onChange={handleChange} />);

    await user.click(screen.getByRole("combobox"));
    await user.click(await screen.findByText("Prime Electrical Co"));

    expect(handleChange).toHaveBeenCalledWith("s1");
  });

  it("shows a real error state when the backend request fails", async () => {
    vi.mocked(apiClient.get).mockRejectedValue(new Error("network error"));
    render(<SubcontractorSelect value="" onChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByRole("combobox")).toHaveAttribute("placeholder", "Could not load subcontractors");
    });
  });
});
