import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import TanksPage from "./TanksPage";
import { apiClient } from "../../api/client";

vi.mock("../../api/client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn() },
  getErrorMessage: (e: any) => e?.response?.data?.title || "Something went wrong.",
}));

const TANK = { id: "t1", name: "Tank A", tank_type: "bulk_storage", current_level_litres: "0.00" };
const PENDING = { id: "p1", tank_id: "t1", quantity_litres: "500.00", unit_price: "900.0000", total_cost: "450000", delivery_confirmed: false };

function mockGets(pending: any[]) {
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === "/fuel/tanks") return Promise.resolve({ data: { data: [TANK] } } as any);
    if (url === "/fuel/purchases") return Promise.resolve({ data: { data: pending } } as any);
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><TanksPage /></QueryClientProvider>);
}

beforeEach(() => vi.resetAllMocks());

describe("TanksPage purchases", () => {
  it("lists pending deliveries and confirms one", async () => {
    mockGets([PENDING]);
    vi.mocked(apiClient.post).mockResolvedValue({ data: {} } as any);
    const user = userEvent.setup();
    renderPage();
    expect(await screen.findByText("Pending deliveries")).toBeInTheDocument();
    expect(screen.getByText("500.00 L")).toBeInTheDocument();
    expect(apiClient.get).toHaveBeenCalledWith("/fuel/purchases", { params: { confirmed: false } });
    await user.click(screen.getByRole("button", { name: "Confirm delivery" }));
    await waitFor(() => expect(apiClient.post).toHaveBeenCalledWith("/fuel/purchases/p1/confirm-delivery"));
  });

  it("shows no pending section when nothing is waiting", async () => {
    mockGets([]);
    renderPage();
    await screen.findByText("Tank A");
    expect(screen.queryByText("Pending deliveries")).toBeNull();
  });

  it("records a purchase as already delivered by default", async () => {
    mockGets([]);
    vi.mocked(apiClient.post).mockResolvedValue({ data: {} } as any);
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByRole("button", { name: "Purchase" }));
    await user.type(screen.getByPlaceholderText("Quantity (litres)"), "500");
    await user.type(screen.getByPlaceholderText("Unit price"), "900");
    await user.click(screen.getByRole("button", { name: "Record" }));
    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith("/fuel/purchases", { tank_id: "t1", quantity_litres: "500", unit_price: "900", confirm_delivery: true })
    );
  });

  it("can record a purchase as not yet delivered", async () => {
    mockGets([]);
    vi.mocked(apiClient.post).mockResolvedValue({ data: {} } as any);
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByRole("button", { name: "Purchase" }));
    await user.click(screen.getByLabelText(/already been delivered/i));
    expect(screen.getByText(/only added to the tank once you confirm/i)).toBeInTheDocument();
    await user.type(screen.getByPlaceholderText("Quantity (litres)"), "100");
    await user.type(screen.getByPlaceholderText("Unit price"), "900");
    await user.click(screen.getByRole("button", { name: "Record" }));
    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith("/fuel/purchases", { tank_id: "t1", quantity_litres: "100", unit_price: "900", confirm_delivery: false })
    );
  });

  it("shows the error instead of failing silently", async () => {
    mockGets([PENDING]);
    vi.mocked(apiClient.post).mockRejectedValue({ response: { data: { title: "Delivery is already confirmed" } } });
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByRole("button", { name: "Confirm delivery" }));
    expect(await screen.findByText("Delivery is already confirmed")).toBeInTheDocument();
  });
});
