import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import WasteAndReturnsPage from "./WasteAndReturnsPage";
import { apiClient } from "../../api/client";

vi.mock("../../api/client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn() },
  getErrorMessage: vi.fn((err: any) => err?.response?.data?.title || "Something went wrong."),
}));

const WAREHOUSES = [
  { id: "wh1", name: "Lagos Yard", warehouse_type: "site_store", project_id: null, location: null },
  { id: "wh2", name: "Central Depot", warehouse_type: "central_yard", project_id: null, location: null },
];
const MATERIALS = [{ id: "m1", code: "MAT-001", description: "Portland Cement 50kg", unit: "bag", is_batch_tracked: false, is_serial_tracked: false }];

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <WasteAndReturnsPage />
    </QueryClientProvider>
  );
}

function mockGet(overrides: Record<string, unknown> = {}) {
  const responses: Record<string, unknown> = {
    "/inv/warehouses": WAREHOUSES,
    "/inv/material-items": MATERIALS,
    "/inv/waste-records": [],
    "/inv/material-returns": [],
    ...overrides,
  };
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url in responses) return Promise.resolve({ data: { data: responses[url] } });
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
}

beforeEach(() => {
  vi.resetAllMocks();
  mockGet();
  vi.mocked(apiClient.post).mockResolvedValue({ data: {} });
});

describe("WasteAndReturnsPage", () => {
  it("shows real, honest empty states when there is genuinely nothing yet", async () => {
    renderPage();

    expect(await screen.findByText("No waste recorded yet.")).toBeInTheDocument();
    expect(screen.getByText("No material returns yet.")).toBeInTheDocument();
  });

  it("lists a real waste record with its real quantity, cause, and valued cost", async () => {
    mockGet({ "/inv/waste-records": [{ id: "w1", warehouse_id: "wh1", material_item_id: "m1", quantity: "5", cause_classification: "breakage", valued_cost: "25000" }] });
    renderPage();

    expect(await screen.findByText("5")).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "breakage" })).toBeInTheDocument();
    expect(screen.getByText(/25,000/)).toBeInTheDocument();
  });

  it("records real waste via the real endpoint with the real selected cause", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("No waste recorded yet.");

    const comboboxes = screen.getAllByRole("combobox");
    await user.click(comboboxes[0]);
    await user.click(await screen.findByText("Lagos Yard"));
    await user.click(comboboxes[1]);
    await user.click(await screen.findByText("Portland Cement 50kg"));

    const numberInput = screen.getAllByDisplayValue("").find((el) => (el as HTMLInputElement).type === "number");
    await user.type(numberInput!, "3");

    const causeSelect = screen.getByDisplayValue("breakage");
    await user.selectOptions(causeSelect, "theft");

    await user.click(screen.getByRole("button", { name: /^record$/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith(
        "/inv/waste-records",
        expect.objectContaining({ warehouse_id: "wh1", material_item_id: "m1", quantity: "3", cause_classification: "theft" })
      );
    });
  });

  it("lists a real return with a real human-readable type label", async () => {
    mockGet({ "/inv/material-returns": [{ id: "r1", material_item_id: "m1", quantity: "10", return_type: "site_to_yard", status: "completed" }] });
    renderPage();

    expect(await screen.findByText("To yard")).toBeInTheDocument();
  });

  it("submits a real return to yard via the real endpoint", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("No material returns yet.");

    // Note: native <select> elements (the Cause dropdown in the Waste
    // section above) also carry role="combobox" in this testing
    // environment, alongside this codebase's own custom Combobox --
    // so the real index order here is Warehouse(0), Material(1),
    // Cause-select(2), then Returns' own Material(3), Source(4),
    // Destination(5).
    const comboboxes = screen.getAllByRole("combobox");
    await user.click(comboboxes[3]);
    await user.click(await screen.findByText("Portland Cement 50kg"));
    await user.click(comboboxes[4]);
    await user.click(await screen.findByText("Lagos Yard"));
    await user.click(comboboxes[5]);
    await user.click(await screen.findByText("Central Depot"));

    const numberInputs = screen.getAllByDisplayValue("").filter((el) => (el as HTMLInputElement).type === "number");
    await user.type(numberInputs[numberInputs.length - 1], "8");

    await user.click(screen.getByRole("button", { name: /^return$/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith(
        "/inv/material-returns/to-yard",
        expect.objectContaining({ material_item_id: "m1", source_warehouse_id: "wh1", destination_warehouse_id: "wh2", quantity: "8" })
      );
    });
  });

  it("shows a real error banner when recording waste fails", async () => {
    vi.mocked(apiClient.post).mockRejectedValue({ response: { data: { title: "Warehouse not found" } } });
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("No waste recorded yet.");

    const comboboxes = screen.getAllByRole("combobox");
    await user.click(comboboxes[0]);
    await user.click(await screen.findByText("Lagos Yard"));
    await user.click(comboboxes[1]);
    await user.click(await screen.findByText("Portland Cement 50kg"));
    const numberInput = screen.getAllByDisplayValue("").find((el) => (el as HTMLInputElement).type === "number");
    await user.type(numberInput!, "1");
    await user.click(screen.getByRole("button", { name: /^record$/i }));

    expect(await screen.findByText("Warehouse not found")).toBeInTheDocument();
  });
});
