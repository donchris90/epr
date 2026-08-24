import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ContractSelect } from "./ContractSelect";
import { apiClient } from "../api/client";

vi.mock("../api/client", () => ({
  apiClient: { get: vi.fn() },
}));

beforeEach(() => {
  vi.resetAllMocks();
});

describe("ContractSelect", () => {
  it("loads and shows real contracts from the backend", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: { data: [{ id: "c1", contract_number: "CTR-2026-001", status: "active", contract_value: "5000000", currency: "NGN" }] },
    });
    const user = userEvent.setup();
    render(<ContractSelect value="" onChange={vi.fn()} />);

    await user.click(screen.getByRole("combobox"));

    expect(await screen.findByText("CTR-2026-001")).toBeInTheDocument();
    expect(apiClient.get).toHaveBeenCalledWith("/ctm/contracts");
  });

  it("calls onChange with the real contract id on selection", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: { data: [{ id: "c1", contract_number: "CTR-2026-001", status: "active", contract_value: "5000000", currency: "NGN" }] },
    });
    const handleChange = vi.fn();
    const user = userEvent.setup();
    render(<ContractSelect value="" onChange={handleChange} />);

    await user.click(screen.getByRole("combobox"));
    await user.click(await screen.findByText("CTR-2026-001"));

    expect(handleChange).toHaveBeenCalledWith("c1");
  });

  it("shows a real error state when the backend request fails", async () => {
    vi.mocked(apiClient.get).mockRejectedValue(new Error("network error"));
    render(<ContractSelect value="" onChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByRole("combobox")).toHaveAttribute("placeholder", "Could not load contracts");
    });
  });
});
