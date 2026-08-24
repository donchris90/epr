import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { WarehouseSelect } from "./WarehouseSelect";
import { MaterialItemSelect } from "./MaterialItemSelect";
import { apiClient } from "../api/client";

vi.mock("../api/client", () => ({
  apiClient: { get: vi.fn() },
}));

beforeEach(() => {
  vi.resetAllMocks();
});

describe("WarehouseSelect", () => {
  it("loads and shows real warehouses from the backend", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: { data: [{ id: "w1", name: "Lagos Main Yard", warehouse_type: "site", location: "Lekki" }] },
    });
    const user = userEvent.setup();
    render(<WarehouseSelect value="" onChange={vi.fn()} />);

    await user.click(screen.getByRole("combobox"));

    expect(await screen.findByText("Lagos Main Yard")).toBeInTheDocument();
    expect(apiClient.get).toHaveBeenCalledWith("/inv/warehouses");
  });

  it("calls onChange with the real warehouse id on selection", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: { data: [{ id: "w1", name: "Lagos Main Yard", warehouse_type: "site", location: "Lekki" }] },
    });
    const handleChange = vi.fn();
    const user = userEvent.setup();
    render(<WarehouseSelect value="" onChange={handleChange} />);

    await user.click(screen.getByRole("combobox"));
    await user.click(await screen.findByText("Lagos Main Yard"));

    expect(handleChange).toHaveBeenCalledWith("w1");
  });

  it("shows a real error state when the backend request fails", async () => {
    vi.mocked(apiClient.get).mockRejectedValue(new Error("network error"));
    render(<WarehouseSelect value="" onChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByRole("combobox")).toHaveAttribute("placeholder", "Could not load warehouses");
    });
  });
});

describe("MaterialItemSelect", () => {
  it("loads and shows real material items from the backend", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: { data: [{ id: "m1", code: "MAT-001", description: "Portland Cement 50kg", unit: "bag" }] },
    });
    const user = userEvent.setup();
    render(<MaterialItemSelect value="" onChange={vi.fn()} />);

    await user.click(screen.getByRole("combobox"));

    expect(await screen.findByText("Portland Cement 50kg")).toBeInTheDocument();
    expect(apiClient.get).toHaveBeenCalledWith("/inv/material-items");
  });

  it("calls onChange with the real material item id on selection", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: { data: [{ id: "m1", code: "MAT-001", description: "Portland Cement 50kg", unit: "bag" }] },
    });
    const handleChange = vi.fn();
    const user = userEvent.setup();
    render(<MaterialItemSelect value="" onChange={handleChange} />);

    await user.click(screen.getByRole("combobox"));
    await user.click(await screen.findByText("Portland Cement 50kg"));

    expect(handleChange).toHaveBeenCalledWith("m1");
  });

  it("shows a real error state when the backend request fails", async () => {
    vi.mocked(apiClient.get).mockRejectedValue(new Error("network error"));
    render(<MaterialItemSelect value="" onChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByRole("combobox")).toHaveAttribute("placeholder", "Could not load material items");
    });
  });
});
