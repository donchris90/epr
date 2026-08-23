import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Combobox, type ComboboxOption } from "./Combobox";

const OPTIONS: ComboboxOption[] = [
  { id: "1", label: "Konga Construction Ltd", sublabel: "VEN-001" },
  { id: "2", label: "Dangote Supplies", sublabel: "VEN-002" },
  { id: "3", label: "Julius Berger Nigeria", sublabel: "VEN-003" },
];

describe("Combobox", () => {
  it("shows a real loading state", () => {
    render(<Combobox value="" onChange={vi.fn()} options={null} loading />);
    expect(screen.getByRole("combobox")).toHaveAttribute("placeholder", "Loading…");
  });

  it("shows a real error state", () => {
    render(<Combobox value="" onChange={vi.fn()} options={null} error errorMessage="Could not load vendors" />);
    expect(screen.getByRole("combobox")).toHaveAttribute("placeholder", "Could not load vendors");
  });

  it("shows a real empty state when the option list is genuinely empty", async () => {
    const user = userEvent.setup();
    render(<Combobox value="" onChange={vi.fn()} options={[]} emptyMessage="No vendors yet" />);

    await user.click(screen.getByRole("combobox"));

    expect(await screen.findByText("No vendors yet")).toBeInTheDocument();
  });

  it("shows every real option when opened with no search text", async () => {
    const user = userEvent.setup();
    render(<Combobox value="" onChange={vi.fn()} options={OPTIONS} />);

    await user.click(screen.getByRole("combobox"));

    expect(await screen.findByText("Konga Construction Ltd")).toBeInTheDocument();
    expect(screen.getByText("Dangote Supplies")).toBeInTheDocument();
    expect(screen.getByText("Julius Berger Nigeria")).toBeInTheDocument();
  });

  it("filters options by real, case-insensitive substring search against the label", async () => {
    const user = userEvent.setup();
    render(<Combobox value="" onChange={vi.fn()} options={OPTIONS} />);

    await user.click(screen.getByRole("combobox"));
    await user.type(screen.getByRole("combobox"), "konga");

    expect(await screen.findByText("Konga Construction Ltd")).toBeInTheDocument();
    expect(screen.queryByText("Dangote Supplies")).not.toBeInTheDocument();
  });

  it("filters options by real substring search against the sublabel too", async () => {
    const user = userEvent.setup();
    render(<Combobox value="" onChange={vi.fn()} options={OPTIONS} />);

    await user.click(screen.getByRole("combobox"));
    await user.type(screen.getByRole("combobox"), "ven-002");

    expect(await screen.findByText("Dangote Supplies")).toBeInTheDocument();
    expect(screen.queryByText("Konga Construction Ltd")).not.toBeInTheDocument();
  });

  it("calls onChange with the real selected option's id on click", async () => {
    const handleChange = vi.fn();
    const user = userEvent.setup();
    render(<Combobox value="" onChange={handleChange} options={OPTIONS} />);

    await user.click(screen.getByRole("combobox"));
    await user.click(await screen.findByText("Dangote Supplies"));

    expect(handleChange).toHaveBeenCalledWith("2");
  });

  it("supports real keyboard navigation (arrow down + enter)", async () => {
    const handleChange = vi.fn();
    const user = userEvent.setup();
    render(<Combobox value="" onChange={handleChange} options={OPTIONS} />);

    const input = screen.getByRole("combobox");
    await user.click(input);
    await user.keyboard("{ArrowDown}{ArrowDown}{Enter}");

    expect(handleChange).toHaveBeenCalledWith("2");
  });

  it("closes on Escape without selecting anything", async () => {
    const handleChange = vi.fn();
    const user = userEvent.setup();
    render(<Combobox value="" onChange={handleChange} options={OPTIONS} />);

    await user.click(screen.getByRole("combobox"));
    await user.keyboard("{Escape}");

    await waitFor(() => {
      expect(screen.queryByText("Konga Construction Ltd")).not.toBeInTheDocument();
    });
    expect(handleChange).not.toHaveBeenCalled();
  });

  it("shows the real selected option's label when a value is already set", () => {
    render(<Combobox value="2" onChange={vi.fn()} options={OPTIONS} />);
    expect(screen.getByRole("combobox")).toHaveValue("Dangote Supplies");
  });

  it("provides a real clear-selection control", async () => {
    const handleChange = vi.fn();
    const user = userEvent.setup();
    render(<Combobox value="2" onChange={handleChange} options={OPTIONS} />);

    await user.click(screen.getByRole("button", { name: /clear selection/i }));

    expect(handleChange).toHaveBeenCalledWith("");
  });

  it("does not show a clear button when clearable is false", () => {
    render(<Combobox value="2" onChange={vi.fn()} options={OPTIONS} clearable={false} />);
    expect(screen.queryByRole("button", { name: /clear selection/i })).not.toBeInTheDocument();
  });

  it("is disabled and shows no dropdown when disabled", async () => {
    const user = userEvent.setup();
    render(<Combobox value="" onChange={vi.fn()} options={OPTIONS} disabled />);

    expect(screen.getByRole("combobox")).toBeDisabled();
    await user.click(screen.getByRole("combobox"));
    expect(screen.queryByText("Konga Construction Ltd")).not.toBeInTheDocument();
  });

  it("closes the dropdown on an outside click", async () => {
    const user = userEvent.setup();
    render(
      <div>
        <Combobox value="" onChange={vi.fn()} options={OPTIONS} />
        <button>outside</button>
      </div>
    );

    await user.click(screen.getByRole("combobox"));
    expect(await screen.findByText("Konga Construction Ltd")).toBeInTheDocument();

    await user.click(screen.getByText("outside"));

    await waitFor(() => {
      expect(screen.queryByText("Konga Construction Ltd")).not.toBeInTheDocument();
    });
  });
});
