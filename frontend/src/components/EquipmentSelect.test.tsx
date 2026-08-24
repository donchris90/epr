import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EquipmentSelect } from "./EquipmentSelect";
import { apiClient } from "../api/client";

vi.mock("../api/client", () => ({
  apiClient: { get: vi.fn() },
}));

beforeEach(() => {
  vi.resetAllMocks();
});

describe("EquipmentSelect", () => {
  it("loads and shows real equipment from the backend", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: { data: [{ id: "eq1", name: "Excavator #3", make: "CAT", model: "320", serial_chassis_number: "SN-123" }] },
    });
    const user = userEvent.setup();
    render(<EquipmentSelect value="" onChange={vi.fn()} />);

    await user.click(screen.getByRole("combobox"));

    expect(await screen.findByText("Excavator #3")).toBeInTheDocument();
    expect(apiClient.get).toHaveBeenCalledWith("/eqp/equipment");
  });

  it("calls onChange with the real equipment id on selection", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: { data: [{ id: "eq1", name: "Excavator #3", make: "CAT", model: "320", serial_chassis_number: "SN-123" }] },
    });
    const handleChange = vi.fn();
    const user = userEvent.setup();
    render(<EquipmentSelect value="" onChange={handleChange} />);

    await user.click(screen.getByRole("combobox"));
    await user.click(await screen.findByText("Excavator #3"));

    expect(handleChange).toHaveBeenCalledWith("eq1");
  });

  it("shows a real error state when the backend request fails", async () => {
    vi.mocked(apiClient.get).mockRejectedValue(new Error("network error"));
    render(<EquipmentSelect value="" onChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByRole("combobox")).toHaveAttribute("placeholder", "Could not load equipment");
    });
  });
});
