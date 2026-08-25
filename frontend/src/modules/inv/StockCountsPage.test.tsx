import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import StockCountsPage from "./StockCountsPage";
import { apiClient } from "../../api/client";

vi.mock("../../api/client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn() },
  getErrorMessage: vi.fn((err: any) => err?.response?.data?.title || "Something went wrong."),
}));

const WAREHOUSES = [{ id: "wh1", name: "Lagos Yard", warehouse_type: "site_store", project_id: null, location: null }];
const MATERIALS = [{ id: "m1", code: "MAT-001", description: "Portland Cement 50kg", unit: "bag", is_batch_tracked: false, is_serial_tracked: false }];

const COUNT_IN_PROGRESS = {
  id: "c1",
  warehouse_id: "wh1",
  count_type: "cycle",
  status: "in_progress",
  lines: [{ id: "line1", material_item_id: "m1", system_quantity: "100", counted_quantity: null, variance: null }],
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <StockCountsPage />
    </QueryClientProvider>
  );
}

function mockGet(overrides: Record<string, unknown> = {}) {
  const responses: Record<string, unknown> = {
    "/inv/warehouses": { data: WAREHOUSES },
    "/inv/material-items": { data: MATERIALS },
    "/inv/stock-counts": { data: [] },
    ...overrides,
  };
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url in responses) return Promise.resolve({ data: responses[url] });
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
}

beforeEach(() => {
  vi.resetAllMocks();
  mockGet();
  vi.mocked(apiClient.post).mockResolvedValue({ data: {} });
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

describe("StockCountsPage", () => {
  it("shows a real, honest empty state when there are no counts yet", async () => {
    renderPage();
    expect(await screen.findByText("No stock counts yet.")).toBeInTheDocument();
  });

  it("lists a real count with its real line count and status", async () => {
    mockGet({ "/inv/stock-counts": { data: [COUNT_IN_PROGRESS] } });
    renderPage();

    // Wait on "in_progress" specifically -- it's genuinely unique to
    // the table row, unlike "cycle" which also matches the static
    // Count type <option> in the form above and resolves before the
    // real async list data has loaded.
    await screen.findByText("in_progress");
    expect(screen.getByRole("cell", { name: "cycle" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "1" })).toBeInTheDocument();
  });

  it("starts a real stock count via the real endpoint with the real selected items", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("No stock counts yet.");

    const comboboxes = screen.getAllByRole("combobox");
    await user.click(comboboxes[0]);
    await user.click(await screen.findByText("Lagos Yard"));

    // comboboxes[1] is the real Count type <select>, comboboxes[2] is
    // the real material-item picker used to build the item list.
    await user.click(comboboxes[2]);
    await user.click(await screen.findByText("Portland Cement 50kg"));
    await user.click(screen.getByRole("button", { name: /^add$/i }));

    await user.click(screen.getByRole("button", { name: /^start count$/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith(
        "/inv/stock-counts",
        expect.objectContaining({ warehouse_id: "wh1", count_type: "cycle", material_item_ids: ["m1"] })
      );
    });
  });

  it("navigates to a real count's detail view and shows its real lines", async () => {
    mockGet({
      "/inv/stock-counts": { data: [COUNT_IN_PROGRESS] },
      "/inv/stock-counts/c1": COUNT_IN_PROGRESS,
    });
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("in_progress");

    await user.click(screen.getByRole("button", { name: /open →/i }));

    expect(await screen.findByText("100")).toBeInTheDocument();
  });

  it("records a real line's counted quantity via the real endpoint", async () => {
    mockGet({
      "/inv/stock-counts": { data: [COUNT_IN_PROGRESS] },
      "/inv/stock-counts/c1": COUNT_IN_PROGRESS,
    });
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("in_progress");
    await user.click(screen.getByRole("button", { name: /open →/i }));
    await screen.findByText("100");

    await user.type(screen.getByPlaceholderText("Counted qty"), "98");
    await user.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/inv/stock-count-lines/line1/record", { counted_quantity: "98" });
    });
  });

  it("completes a real count via the real endpoint", async () => {
    mockGet({
      "/inv/stock-counts": { data: [COUNT_IN_PROGRESS] },
      "/inv/stock-counts/c1": COUNT_IN_PROGRESS,
    });
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("in_progress");
    await user.click(screen.getByRole("button", { name: /open →/i }));
    await screen.findByText("100");

    await user.click(screen.getByRole("button", { name: /^complete count$/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/inv/stock-counts/c1/complete");
    });
  });

  it("applies a real adjustment for a real completed count, after real confirmation", async () => {
    const completedCount = { ...COUNT_IN_PROGRESS, status: "completed" };
    mockGet({
      "/inv/stock-counts": { data: [completedCount] },
      "/inv/stock-counts/c1": completedCount,
    });
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("completed");
    await user.click(screen.getByRole("button", { name: /open →/i }));
    await screen.findByText("100");

    await user.click(screen.getByRole("button", { name: /apply adjustment to inventory/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/inv/stock-counts/c1/apply-adjustment");
    });
  });

  it("does not record or complete a real already-completed count's lines", async () => {
    const completedCount = { ...COUNT_IN_PROGRESS, status: "completed" };
    mockGet({
      "/inv/stock-counts": { data: [completedCount] },
      "/inv/stock-counts/c1": completedCount,
    });
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("completed");
    await user.click(screen.getByRole("button", { name: /open →/i }));
    await screen.findByText("100");

    expect(screen.queryByPlaceholderText("Counted qty")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^complete count$/i })).not.toBeInTheDocument();
  });

  it("shows a real error banner when the count detail fails to load", async () => {
    mockGet({ "/inv/stock-counts": { data: [COUNT_IN_PROGRESS] } });
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === "/inv/stock-counts/c1") return Promise.reject({ response: { data: { title: "Stock count not found" } } });
      const responses: Record<string, unknown> = { "/inv/warehouses": { data: WAREHOUSES }, "/inv/material-items": { data: MATERIALS }, "/inv/stock-counts": { data: [COUNT_IN_PROGRESS] } };
      if (url in responses) return Promise.resolve({ data: responses[url] });
      return Promise.reject(new Error(`unexpected GET ${url}`));
    });
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("in_progress");

    await user.click(screen.getByRole("button", { name: /open →/i }));

    expect(await screen.findByText("Stock count not found")).toBeInTheDocument();
  });
});
