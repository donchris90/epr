import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { VendorSelect } from "./VendorSelect";
import { apiClient } from "../api/client";

vi.mock("../api/client", () => ({
  apiClient: { get: vi.fn() },
}));

beforeEach(() => {
  vi.resetAllMocks();
});

describe("VendorSelect", () => {
  it("loads and shows real vendors from the backend", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: { data: [{ id: "v1", name: "Konga Construction Ltd", status: "active" }] },
    });
    const user = userEvent.setup();
    render(<VendorSelect value="" onChange={vi.fn()} />);

    await user.click(screen.getByRole("combobox"));

    expect(await screen.findByText("Konga Construction Ltd")).toBeInTheDocument();
    expect(apiClient.get).toHaveBeenCalledWith("/prc/vendors");
  });

  it("shows an inactive vendor's real status as a sublabel", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: { data: [{ id: "v1", name: "Suspended Vendor Ltd", status: "suspended" }] },
    });
    const user = userEvent.setup();
    render(<VendorSelect value="" onChange={vi.fn()} />);

    await user.click(screen.getByRole("combobox"));

    expect(await screen.findByText("suspended")).toBeInTheDocument();
  });

  it("calls onChange with the real vendor id on selection", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: { data: [{ id: "v1", name: "Konga Construction Ltd", status: "active" }] },
    });
    const handleChange = vi.fn();
    const user = userEvent.setup();
    render(<VendorSelect value="" onChange={handleChange} />);

    await user.click(screen.getByRole("combobox"));
    await user.click(await screen.findByText("Konga Construction Ltd"));

    expect(handleChange).toHaveBeenCalledWith("v1");
  });

  it("shows a real error state when the backend request fails", async () => {
    vi.mocked(apiClient.get).mockRejectedValue(new Error("network error"));
    const user = userEvent.setup();
    render(<VendorSelect value="" onChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByRole("combobox")).toHaveAttribute("placeholder", "Could not load vendors");
    });
    await user.click(screen.getByRole("combobox"));
    expect(await screen.findByText("Could not load vendors")).toBeInTheDocument();
  });
});
