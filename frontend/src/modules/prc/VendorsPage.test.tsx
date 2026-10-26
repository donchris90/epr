import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import VendorsPage from "./VendorsPage";
import { apiClient } from "../../api/client";

vi.mock("../../api/client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn() },
  getErrorMessage: (e: any) => e?.message ?? "err",
}));

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === "/prc/vendors") return Promise.resolve({ data: { data: [{ id: "v1", name: "Acme Steel", status: "active", tax_registration_number: null }] } } as any);
    if (url === "/documents") return Promise.resolve({ data: { data: [{ id: "d1", doc_type: "certificate", original_filename: "licence.pdf", size_bytes: 10, status: "uploaded", created_at: "2026-10-01T00:00:00Z" }] } } as any);
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
});

describe("VendorsPage portal documents", () => {
  it("opens that vendor's portal documents from the row", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><VendorsPage /></QueryClientProvider>);
    await userEvent.click(await screen.findByRole("button", { name: "Portal documents" }));
    expect(await screen.findByText("licence.pdf")).toBeInTheDocument();
    expect(apiClient.get).toHaveBeenCalledWith("/documents", { params: { source: "vendor", portal_owner_id: "v1" } });
  });
});
