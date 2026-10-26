import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ProductionOrdersPage from "./ProductionOrdersPage";
import BomsPage from "./BomsPage";
import { apiClient } from "../../api/client";

vi.mock("../../api/client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn() },
  getErrorMessage: (e: any) => e?.response?.data?.detail || e?.response?.data?.title || "Something went wrong.",
}));

const ITEMS = [
  { id: "i-flour", code: "FLOUR", description: "Flour", unit: "kg", is_batch_tracked: false, is_serial_tracked: false },
  { id: "i-bread", code: "BREAD", description: "Bread", unit: "pc", is_batch_tracked: true, is_serial_tracked: false },
];
const BOM = { id: "b1", code: "BOM-BREAD", name: "Bread", product_item_id: "i-bread", output_quantity: "10.0000", is_active: true,
  lines: [{ id: "l1", component_item_id: "i-flour", quantity: "5.0000", scrap_percent: "10.000" }] };
const WH = { id: "w1", name: "Factory store", warehouse_type: "central_yard", project_id: null, location: null };
const order = (over: any = {}) => ({
  id: "o1", number: "PRD-00001", bom_id: "b1", product_item_id: "i-bread", warehouse_id: "w1", work_center_id: null,
  status: "draft", quantity_planned: "20.0000", quantity_produced: "0.0000", quantity_scrapped: "0.0000",
  labour_hours: "0.00", fuel_litres: "0.00", material_cost: "0.0000", labour_cost: "0.0000", fuel_cost: "0.0000",
  total_cost: "0.0000", unit_cost: "0.0000", batch_id: null, components: [], ...over,
});

function mockGets(orders: any[], availability: any[] = []) {
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    const data: Record<string, any> = {
      "/mfg/production-orders": orders,
      "/mfg/boms": [BOM],
      "/mfg/work-centers": [],
      "/inv/warehouses": [WH],
      "/inv/material-items": ITEMS,
      "/mfg/production-orders/o1/availability": availability,
      "/mfg/production-orders/o1/variances": [{ component_item_id: "i-flour", planned: "11", consumed: "13", variance: "2", valued_cost: "1300" }],
    };
    return url in data ? Promise.resolve({ data: { data: data[url] } } as any) : Promise.reject(new Error(`unexpected GET ${url}`));
  });
}

function renderIn(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

beforeEach(() => vi.resetAllMocks());

describe("ProductionOrdersPage", () => {
  it("offers the next step for each status", async () => {
    mockGets([order(), order({ id: "o2", number: "PRD-00002", status: "released" }), order({ id: "o3", number: "PRD-00003", status: "in_progress" })]);
    renderIn(<ProductionOrdersPage />);
    await screen.findByText("PRD-00001");
    expect(screen.getByRole("button", { name: "Release" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Complete" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Cancel" })).toHaveLength(3);
  });

  it("releases a draft order", async () => {
    mockGets([order()]);
    vi.mocked(apiClient.post).mockResolvedValue({ data: {} } as any);
    renderIn(<ProductionOrdersPage />);
    await userEvent.setup().click(await screen.findByRole("button", { name: "Release" }));
    await waitFor(() => expect(apiClient.post).toHaveBeenCalledWith("/mfg/production-orders/o1/release"));
  });

  it("creates an order from a BOM, quantity and warehouse", async () => {
    mockGets([]);
    vi.mocked(apiClient.post).mockResolvedValue({ data: {} } as any);
    const user = userEvent.setup();
    renderIn(<ProductionOrdersPage />);
    await user.click(await screen.findByRole("button", { name: "New production order" }));
    const selects = screen.getAllByRole("combobox");
    await user.selectOptions(selects[0], "b1");
    await user.type(screen.getByRole("textbox", { name: /quantity/i }), "20");
    await user.selectOptions(selects[1], "w1");
    await user.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith("/mfg/production-orders", { bom_id: "b1", quantity: "20", warehouse_id: "w1", work_center_id: null }),
    );
  });

  it("completes an order with costs, batch and quarantine, and warns about shortages", async () => {
    mockGets([order({ status: "in_progress" })], [{ component_item_id: "i-flour", code: "FLOUR", required: "11", available: "4", short: "7" }]);
    vi.mocked(apiClient.post).mockResolvedValue({ data: {} } as any);
    const user = userEvent.setup();
    renderIn(<ProductionOrdersPage />);
    await user.click(await screen.findByRole("button", { name: "Complete" }));
    expect(await screen.findByText(/FLOUR: short by 7/)).toBeInTheDocument();

    await user.clear(screen.getByLabelText("Good units produced"));
    await user.type(screen.getByLabelText("Good units produced"), "18");
    await user.clear(screen.getByLabelText("Scrapped units"));
    await user.type(screen.getByLabelText("Scrapped units"), "2");
    await user.clear(screen.getByLabelText("Fuel used (litres)"));
    await user.type(screen.getByLabelText("Fuel used (litres)"), "10");
    await user.type(await screen.findByLabelText("Fuel price per litre"), "900");
    await user.type(screen.getByLabelText("Batch number"), "B-001");
    await user.click(screen.getByLabelText(/quarantine/i));
    await user.click(screen.getByRole("button", { name: "Complete order" }));

    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith("/mfg/production-orders/o1/complete", {
        quantity_produced: "18", quantity_scrapped: "2", labour_hours: "0", fuel_litres: "10", fuel_unit_cost: "900",
        batch_number: "B-001", expiry_date: null, quarantine: true,
      }),
    );
  });

  it("shows the server's reason when completing fails and keeps the panel open", async () => {
    mockGets([order({ status: "in_progress" })]);
    vi.mocked(apiClient.post).mockRejectedValue({ response: { data: { title: "Insufficient stock", detail: "Requested 11, only 4 on hand." } } });
    const user = userEvent.setup();
    renderIn(<ProductionOrdersPage />);
    await user.click(await screen.findByRole("button", { name: "Complete" }));
    await user.click(await screen.findByRole("button", { name: "Complete order" }));
    expect(await screen.findByText(/only 4 on hand/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Complete order" })).toBeInTheDocument();
  });

  it("shows the cost split and material variance of a finished order", async () => {
    mockGets([order({ status: "done", quantity_produced: "20", material_cost: "2000", labour_cost: "6000", fuel_cost: "9000", total_cost: "17000", unit_cost: "850" })]);
    const user = userEvent.setup();
    renderIn(<ProductionOrdersPage />);
    await user.click(await screen.findByRole("button", { name: "View cost" }));
    const table = await screen.findByRole("table", { name: "Cost breakdown" });
    expect(within(table).getByText("Fuel (0 L)")).toBeInTheDocument();
    expect(within(table).getByText(/Total/)).toBeInTheDocument();
    const variance = await screen.findByRole("table", { name: "Material variances" });
    expect(within(variance).getByText("+2")).toBeInTheDocument();
  });
});

describe("BomsPage", () => {
  it("lists a BOM with its scrap allowance", async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) =>
      Promise.resolve({ data: { data: url === "/mfg/boms" ? [BOM] : ITEMS } } as any),
    );
    renderIn(<BomsPage />);
    expect(await screen.findByText("FLOUR × 5 (+10%)")).toBeInTheDocument();
  });

  it("saves a BOM with several components", async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) =>
      Promise.resolve({ data: { data: url === "/mfg/boms" ? [] : ITEMS } } as any),
    );
    vi.mocked(apiClient.post).mockResolvedValue({ data: {} } as any);
    const user = userEvent.setup();
    renderIn(<BomsPage />);
    await user.click(await screen.findByRole("button", { name: "New BOM" }));
    await user.type(screen.getByLabelText("Code"), "BOM-1");
    await user.type(screen.getByLabelText("Name"), "Bread");
    await user.selectOptions(screen.getByLabelText("Product made"), "i-bread");
    await user.clear(screen.getByLabelText("Makes (quantity)"));
    await user.type(screen.getByLabelText("Makes (quantity)"), "10");
    await user.selectOptions(screen.getByLabelText("Component 1"), "i-flour");
    await user.type(screen.getByLabelText("Quantity 1"), "5");
    await user.click(screen.getByRole("button", { name: "Add component" }));
    await user.selectOptions(screen.getByLabelText("Component 2"), "i-flour");
    await user.type(screen.getByLabelText("Quantity 2"), "1");
    await user.click(screen.getByRole("button", { name: "Save BOM" }));
    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith("/mfg/boms", {
        code: "BOM-1", name: "Bread", product_item_id: "i-bread", output_quantity: "10",
        lines: [
          { component_item_id: "i-flour", quantity: "5", scrap_percent: "0" },
          { component_item_id: "i-flour", quantity: "1", scrap_percent: "0" },
        ],
      }),
    );
  });
});
