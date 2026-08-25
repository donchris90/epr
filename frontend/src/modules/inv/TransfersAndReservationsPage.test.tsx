import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import TransfersAndReservationsPage from "./TransfersAndReservationsPage";
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
      <TransfersAndReservationsPage />
    </QueryClientProvider>
  );
}

function mockGet(overrides: Record<string, unknown> = {}) {
  const responses: Record<string, unknown> = {
    "/inv/warehouses": WAREHOUSES,
    "/inv/material-items": MATERIALS,
    "/inv/stock-transfers": [],
    "/inv/stock/reservations": [],
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

describe("TransfersAndReservationsPage", () => {
  it("shows real, honest empty states when there is genuinely nothing yet", async () => {
    renderPage();

    expect(await screen.findByText("No stock transfers yet.")).toBeInTheDocument();
    expect(screen.getByText("No stock reservations yet.")).toBeInTheDocument();
  });

  it("lists a real transfer with its real quantity and status", async () => {
    mockGet({ "/inv/stock-transfers": [{ id: "t1", from_warehouse_id: "wh1", to_warehouse_id: "wh2", material_item_id: "m1", quantity: "20", status: "in_transit" }] });
    renderPage();

    expect(await screen.findByText("20")).toBeInTheDocument();
    expect(screen.getByText("in_transit")).toBeInTheDocument();
  });

  it("confirms receipt of a real in-transit transfer via the real endpoint", async () => {
    mockGet({ "/inv/stock-transfers": [{ id: "t1", from_warehouse_id: "wh1", to_warehouse_id: "wh2", material_item_id: "m1", quantity: "20", status: "in_transit" }] });
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: /confirm receipt/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/inv/stock-transfers/t1/confirm-receipt");
    });
  });

  it("does not show a confirm-receipt action for a real already-confirmed transfer", async () => {
    mockGet({ "/inv/stock-transfers": [{ id: "t1", from_warehouse_id: "wh1", to_warehouse_id: "wh2", material_item_id: "m1", quantity: "20", status: "confirmed" }] });
    renderPage();

    await screen.findByText("confirmed");
    expect(screen.queryByRole("button", { name: /confirm receipt/i })).not.toBeInTheDocument();
  });

  it("lists a real reservation and releases it via the real endpoint", async () => {
    mockGet({ "/inv/stock/reservations": [{ id: "r1", warehouse_id: "wh1", material_item_id: "m1", project_id: null, activity_id: null, quantity: "5", status: "active" }] });
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText("5")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^release$/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/inv/stock/reservations/r1/release");
    });
  });

  it("creates a real transfer via the real endpoint using the entered fields", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("No stock transfers yet.");

    const comboboxes = screen.getAllByRole("combobox");
    await user.click(comboboxes[0]);
    await user.click(await screen.findByText("Lagos Yard"));
    await user.click(comboboxes[1]);
    await user.click(await screen.findByText("Central Depot"));
    await user.click(comboboxes[2]);
    await user.click(await screen.findByText("Portland Cement 50kg"));

    const quantityInputs = screen.getAllByDisplayValue("");
    const numberInput = quantityInputs.find((el) => (el as HTMLInputElement).type === "number");
    await user.type(numberInput!, "15");

    await user.click(screen.getByRole("button", { name: /^transfer$/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith(
        "/inv/stock-transfers",
        expect.objectContaining({ from_warehouse_id: "wh1", to_warehouse_id: "wh2", material_item_id: "m1", quantity: "15" })
      );
    });
  });

  it("shows a real error banner when creating a transfer fails", async () => {
    vi.mocked(apiClient.post).mockRejectedValue({ response: { data: { title: "Insufficient stock" } } });
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("No stock transfers yet.");

    const comboboxes = screen.getAllByRole("combobox");
    await user.click(comboboxes[0]);
    await user.click(await screen.findByText("Lagos Yard"));
    await user.click(comboboxes[1]);
    await user.click(await screen.findByText("Central Depot"));
    await user.click(comboboxes[2]);
    await user.click(await screen.findByText("Portland Cement 50kg"));

    const numberInput = screen.getAllByDisplayValue("").find((el) => (el as HTMLInputElement).type === "number");
    await user.type(numberInput!, "999999");
    await user.click(screen.getByRole("button", { name: /^transfer$/i }));

    expect(await screen.findByText("Insufficient stock")).toBeInTheDocument();
  });
});
