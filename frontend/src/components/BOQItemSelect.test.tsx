import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BOQItemSelect } from "./BOQItemSelect";
import { apiClient } from "../api/client";

vi.mock("../api/client", () => ({
  apiClient: { get: vi.fn() },
}));

beforeEach(() => {
  vi.resetAllMocks();
});

describe("BOQItemSelect", () => {
  it("shows a real, disabled 'select a contract first' state when no contract is chosen", () => {
    render(<BOQItemSelect contractId="" value="" onChange={vi.fn()} />);

    expect(screen.getByRole("combobox")).toBeDisabled();
    expect(screen.getByRole("combobox")).toHaveAttribute("placeholder", "Select a contract first");
    expect(apiClient.get).not.toHaveBeenCalled();
  });

  it("resolves the real two-step chain: contract -> tender_id -> tender's own BOQ items", async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === "/ctm/contracts/c1") return Promise.resolve({ data: { id: "c1", tender_id: "t1" } });
      if (url === "/tbm/tenders/t1/boq-items") {
        return Promise.resolve({ data: { data: [{ id: "boq1", item_code: "BOQ-004", description: "Concrete Works", unit: "m3" }] } });
      }
      return Promise.reject(new Error(`unexpected GET ${url}`));
    });
    const user = userEvent.setup();
    render(<BOQItemSelect contractId="c1" value="" onChange={vi.fn()} />);

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith("/ctm/contracts/c1");
      expect(apiClient.get).toHaveBeenCalledWith("/tbm/tenders/t1/boq-items");
    });

    await user.click(screen.getByRole("combobox"));
    expect(await screen.findByText("Concrete Works")).toBeInTheDocument();
    expect(screen.getByText("BOQ-004 · m3")).toBeInTheDocument();
  });

  it("calls onChange with the real BOQ item id on selection", async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === "/ctm/contracts/c1") return Promise.resolve({ data: { id: "c1", tender_id: "t1" } });
      if (url === "/tbm/tenders/t1/boq-items") {
        return Promise.resolve({ data: { data: [{ id: "boq1", item_code: "BOQ-004", description: "Concrete Works", unit: "m3" }] } });
      }
      return Promise.reject(new Error(`unexpected GET ${url}`));
    });
    const handleChange = vi.fn();
    const user = userEvent.setup();
    render(<BOQItemSelect contractId="c1" value="" onChange={handleChange} />);

    await user.click(screen.getByRole("combobox"));
    await user.click(await screen.findByText("Concrete Works"));

    expect(handleChange).toHaveBeenCalledWith("boq1");
  });

  it("re-resolves against the real new contract when contractId changes", async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === "/ctm/contracts/c1") return Promise.resolve({ data: { id: "c1", tender_id: "t1" } });
      if (url === "/ctm/contracts/c2") return Promise.resolve({ data: { id: "c2", tender_id: "t2" } });
      if (url === "/tbm/tenders/t1/boq-items") return Promise.resolve({ data: { data: [{ id: "boq1", item_code: "BOQ-004", description: "Concrete Works", unit: "m3" }] } });
      if (url === "/tbm/tenders/t2/boq-items") return Promise.resolve({ data: { data: [{ id: "boq2", item_code: "BOQ-009", description: "Steel Reinforcement", unit: "kg" }] } });
      return Promise.reject(new Error(`unexpected GET ${url}`));
    });
    const user = userEvent.setup();
    const { rerender } = render(<BOQItemSelect contractId="c1" value="" onChange={vi.fn()} />);

    await waitFor(() => expect(apiClient.get).toHaveBeenCalledWith("/tbm/tenders/t1/boq-items"));

    rerender(<BOQItemSelect contractId="c2" value="" onChange={vi.fn()} />);

    await waitFor(() => expect(apiClient.get).toHaveBeenCalledWith("/tbm/tenders/t2/boq-items"));
    await user.click(screen.getByRole("combobox"));
    expect(await screen.findByText("Steel Reinforcement")).toBeInTheDocument();
  });

  it("shows a real error state when the resolve chain fails", async () => {
    vi.mocked(apiClient.get).mockRejectedValue(new Error("network error"));
    render(<BOQItemSelect contractId="c1" value="" onChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByRole("combobox")).toHaveAttribute("placeholder", "Could not load BOQ items for this contract");
    });
  });
});
