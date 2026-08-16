import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import WarehousesPage from "./WarehousesPage";
import { apiClient } from "../../api/client";

/**
 * Regression coverage for a real bug found via a systematic dropdown
 * audit (see README.md's "frontend dropdown bug hunt" session notes):
 * this form used to offer ["central", "site", "yard"] -- none of
 * which the real backend CHECK constraint (WAREHOUSE_TYPES =
 * ("central_yard", "site_store", "quarry")) accepted. Warehouse
 * creation through the UI would have failed every single time.
 */

vi.mock("../../api/client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

function renderWithClient(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

const VALID_WAREHOUSE_TYPES = ["central_yard", "site_store", "quarry"];

beforeEach(() => {
  vi.mocked(apiClient.get).mockResolvedValue({ data: { data: [] } });
  vi.mocked(apiClient.post).mockResolvedValue({ data: {} });
});

describe("WarehousesPage warehouse type", () => {
  it("only offers real backend-valid warehouse type values", async () => {
    const user = userEvent.setup();
    renderWithClient(<WarehousesPage />);

    await user.click(screen.getByRole("button", { name: /new warehouse/i }));

    const select = screen.getByRole("combobox");
    const options = within(select).getAllByRole("option").map((o) => (o as HTMLOptionElement).value);

    expect(options).toEqual(VALID_WAREHOUSE_TYPES);
    // The specific regression: none of the original invented values
    // should ever reappear.
    expect(options).not.toContain("central");
    expect(options).not.toContain("site");
    expect(options).not.toContain("yard");
  });

  it("submits a valid warehouse_type value on create", async () => {
    const user = userEvent.setup();
    renderWithClient(<WarehousesPage />);

    await user.click(screen.getByRole("button", { name: /new warehouse/i }));
    await user.type(screen.getByLabelText(/name/i), "Main Site Store");

    const select = screen.getByRole("combobox");
    await user.selectOptions(select, "quarry");

    await user.click(screen.getByRole("button", { name: /^add$/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith(
        "/inv/warehouses",
        expect.objectContaining({ warehouse_type: "quarry" }),
      );
    });

    const [, payload] = vi.mocked(apiClient.post).mock.calls[0];
    expect(VALID_WAREHOUSE_TYPES).toContain((payload as { warehouse_type: string }).warehouse_type);
  });
});
