import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EmployeeSelect } from "./EmployeeSelect";
import { apiClient } from "../api/client";

vi.mock("../api/client", () => ({
  apiClient: { get: vi.fn() },
}));

beforeEach(() => {
  vi.resetAllMocks();
});

describe("EmployeeSelect", () => {
  it("loads and shows real employees from the backend", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: { data: [{ id: "e1", name: "Chidi Okafor", employee_number: "EMP-042", status: "active" }] },
    });
    const user = userEvent.setup();
    render(<EmployeeSelect value="" onChange={vi.fn()} />);

    await user.click(screen.getByRole("combobox"));

    expect(await screen.findByText("Chidi Okafor")).toBeInTheDocument();
    expect(screen.getByText("EMP-042")).toBeInTheDocument();
    expect(apiClient.get).toHaveBeenCalledWith("/wfm/employees");
  });

  it("calls onChange with the real employee id on selection", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: { data: [{ id: "e1", name: "Chidi Okafor", employee_number: "EMP-042", status: "active" }] },
    });
    const handleChange = vi.fn();
    const user = userEvent.setup();
    render(<EmployeeSelect value="" onChange={handleChange} />);

    await user.click(screen.getByRole("combobox"));
    await user.click(await screen.findByText("Chidi Okafor"));

    expect(handleChange).toHaveBeenCalledWith("e1");
  });

  it("shows a real error state when the backend request fails", async () => {
    vi.mocked(apiClient.get).mockRejectedValue(new Error("network error"));
    render(<EmployeeSelect value="" onChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByRole("combobox")).toHaveAttribute("placeholder", "Could not load employees");
    });
  });
});
