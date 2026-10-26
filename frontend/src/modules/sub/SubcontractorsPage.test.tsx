import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import SubcontractorsPage from "./SubcontractorsPage";
import { apiClient } from "../../api/client";

vi.mock("../../api/client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn() },
  getErrorMessage: (e: any) => e?.message ?? "err",
}));

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === "/sub/subcontractors") return Promise.resolve({ data: { data: [{ id: "s1", name: "Sparks Electrical", trade_specialty: "Electrical", status: "active" }] } } as any);
    if (url === "/sub/agreements") return Promise.resolve({ data: { data: [] } } as any);
    if (url === "/documents") return Promise.resolve({ data: { data: [] } } as any);
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
});

describe("SubcontractorsPage portal documents", () => {
  it("opens that subcontractor's portal documents from the row", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<MemoryRouter><QueryClientProvider client={client}><SubcontractorsPage /></QueryClientProvider></MemoryRouter>);
    await userEvent.click(await screen.findByRole("button", { name: "Portal documents" }));
    expect(await screen.findByText("Documents uploaded by Sparks Electrical")).toBeInTheDocument();
    expect(apiClient.get).toHaveBeenCalledWith("/documents", { params: { source: "subcontractor", portal_owner_id: "s1" } });
  });
});
