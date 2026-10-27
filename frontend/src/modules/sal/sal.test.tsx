import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import SalesDocumentPage from "./SalesDocumentPage";
import SalesOrdersPage from "./SalesOrdersPage";
import SalesSettingsPage from "./SalesSettingsPage";
import SalesInvoicesPage from "./SalesInvoicesPage";
import { apiClient } from "../../api/client";

vi.mock("../../api/client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn() },
  getErrorMessage: (e: any) => e?.response?.data?.detail || e?.response?.data?.title || "Something went wrong.",
}));

const ITEMS = [{ id: "i-bread", code: "BREAD", description: "Bread", unit: "pc", is_batch_tracked: false, is_serial_tracked: false }];
const CLIENTS = [{ id: "c1", name: "Shoprite", billing_address: "12 Allen Avenue\nIkeja, Lagos", billing_email: "ap@shoprite.example" }];
const WH = [{ id: "w1", name: "Factory store" }];
const order = (over: any = {}) => ({
  id: "o1", number: "SO-00001", client_id: "c1", warehouse_id: "w1", status: "draft", order_date: "2026-10-27", delivery_date: null,
  vat_percent: "7.50", subtotal: "5000.00", vat_amount: "375.00", total: "5375.00",
  lines: [{ id: "l1", material_item_id: "i-bread", quantity: "10.0000", unit_price: "500.0000", delivered_quantity: "0.0000", invoiced_quantity: "0.0000" }],
  deliveries: [], invoices: [], delivered_value: "0", delivered_cost: "0", gross_margin: "0", ...over,
});

function mockGets(orders: any[], settings: any = null) {
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    const data: Record<string, any> = {
      "/sal/sales-orders": orders,
      "/bdc/clients": CLIENTS,
      "/inv/warehouses": WH,
      "/inv/material-items": ITEMS,
      "/fin/companies": [{ id: "co1", name: "Acme Foods" }],
      "/fin/chart-of-accounts": [
        { id: "a-ar", code: "1200", name: "Receivables" },
        { id: "a-rev", code: "4000", name: "Sales" },
        { id: "a-vat", code: "2200", name: "VAT payable" },
      ],
    };
    if (url === "/sal/sales-orders/o1") return Promise.resolve({ data: orders[0] } as any);
    if (url === "/sal/settings") return Promise.resolve({ data: { data: settings } } as any);
    return url in data ? Promise.resolve({ data: { data: data[url] } } as any) : Promise.reject(new Error(`unexpected GET ${url}`));
  });
}

function renderIn(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter>{ui}</MemoryRouter></QueryClientProvider>);
}

beforeEach(() => vi.resetAllMocks());

describe("SalesOrdersPage", () => {
  it("offers the right next step for each status", async () => {
    mockGets([
      order(),
      order({ id: "o2", number: "SO-00002", status: "confirmed" }),
      order({ id: "o3", number: "SO-00003", status: "delivered", lines: [{ id: "l3", material_item_id: "i-bread", quantity: "10", unit_price: "500", delivered_quantity: "10", invoiced_quantity: "4" }] }),
    ]);
    renderIn(<SalesOrdersPage />);
    await screen.findByText("SO-00001");
    expect(screen.getAllByRole("button", { name: "Confirm" })).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: "Deliver" })).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: "Invoice" })).toHaveLength(1); // only the one with uninvoiced deliveries
  });

  it("confirms and invoices through the API", async () => {
    mockGets([order(), order({ id: "o3", number: "SO-00003", status: "delivered", lines: [{ id: "l3", material_item_id: "i-bread", quantity: "10", unit_price: "500", delivered_quantity: "10", invoiced_quantity: "0" }] })]);
    vi.mocked(apiClient.post).mockResolvedValue({ data: {} } as any);
    const user = userEvent.setup();
    renderIn(<SalesOrdersPage />);
    await user.click(await screen.findByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(apiClient.post).toHaveBeenCalledWith("/sal/sales-orders/o1/confirm"));
    await user.click(screen.getByRole("button", { name: "Invoice" }));
    await waitFor(() => expect(apiClient.post).toHaveBeenCalledWith("/sal/sales-orders/o3/invoice"));
  });

  it("creates an order, leaving the price blank to use the item's default", async () => {
    mockGets([]);
    vi.mocked(apiClient.post).mockResolvedValue({ data: {} } as any);
    const user = userEvent.setup();
    renderIn(<SalesOrdersPage />);
    await user.click(await screen.findByRole("button", { name: "New sales order" }));
    await user.selectOptions(screen.getByLabelText("Client"), "c1");
    await user.selectOptions(screen.getByLabelText("Warehouse"), "w1");
    await user.selectOptions(screen.getByLabelText("Item 1"), "i-bread");
    await user.type(screen.getByLabelText("Quantity 1"), "10");
    await user.click(screen.getByRole("button", { name: "Save order" }));
    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith("/sal/sales-orders", {
        client_id: "c1", warehouse_id: "w1", lines: [{ material_item_id: "i-bread", quantity: "10", unit_price: null }],
      }),
    );
  });

  it("delivers part of an order, prefilled with what is left", async () => {
    mockGets([order({ status: "partially_delivered", lines: [{ id: "l1", material_item_id: "i-bread", quantity: "10", unit_price: "500", delivered_quantity: "4", invoiced_quantity: "0" }] })]);
    vi.mocked(apiClient.post).mockResolvedValue({ data: {} } as any);
    const user = userEvent.setup();
    renderIn(<SalesOrdersPage />);
    await user.click(await screen.findByRole("button", { name: "Deliver" }));
    const field = await screen.findByLabelText("Deliver BREAD");
    expect(field).toHaveValue("6");
    await user.clear(field);
    await user.type(field, "3");
    await user.click(screen.getByRole("button", { name: "Confirm delivery" }));
    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith("/sal/sales-orders/o1/deliveries", { lines: [{ order_line_id: "l1", quantity: "3" }] }),
    );
  });

  it("shows the server's reason when a delivery is short and keeps the panel open", async () => {
    mockGets([order({ status: "confirmed" })]);
    vi.mocked(apiClient.post).mockRejectedValue({ response: { data: { title: "Insufficient stock", detail: "Requested 10, only 4 on hand." } } });
    const user = userEvent.setup();
    renderIn(<SalesOrdersPage />);
    await user.click(await screen.findByRole("button", { name: "Deliver" }));
    await user.click(await screen.findByRole("button", { name: "Confirm delivery" }));
    expect(await screen.findByText(/only 4 on hand/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm delivery" })).toBeInTheDocument();
  });

  it("shows totals, VAT and margin in the details", async () => {
    mockGets([
      order({
        status: "delivered", delivered_value: "5000.00", delivered_cost: "4000.0000", gross_margin: "1000.0000",
        deliveries: [{ id: "d1", number: "DN-00001", delivered_at: "2026-10-27", lines: [] }],
        invoices: [{ id: "s1", number: "SI-00001", order_id: "o1", invoice_date: "2026-10-27", due_date: null, net_amount: "5000", vat_amount: "375", amount: "5375" }],
        lines: [{ id: "l1", material_item_id: "i-bread", quantity: "10", unit_price: "500", delivered_quantity: "10", invoiced_quantity: "10" }],
      }),
    ]);
    const user = userEvent.setup();
    renderIn(<SalesOrdersPage />);
    await user.click(await screen.findByRole("button", { name: "Details" }));
    expect(await screen.findByText(/VAT \(7\.5%\)/)).toBeInTheDocument();
    expect(screen.getByText(/DN-00001/)).toBeInTheDocument();
    expect(screen.getByText(/SI-00001/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Invoice" })).toBeNull();
  });
});

describe("SalesSettingsPage", () => {
  it("saves the accounts and VAT rate", async () => {
    mockGets([], null);
    vi.mocked(apiClient.put).mockResolvedValue({ data: {} } as any);
    const user = userEvent.setup();
    renderIn(<SalesSettingsPage />);
    await screen.findByRole("option", { name: "Acme Foods" });
    await screen.findAllByRole("option", { name: "1200 — Receivables" });
    await user.selectOptions(screen.getByLabelText("Company"), "co1");
    await user.selectOptions(screen.getByLabelText("Receivable account"), "a-ar");
    await user.selectOptions(screen.getByLabelText("Revenue account"), "a-rev");
    await user.selectOptions(screen.getByLabelText("VAT account (output VAT payable)"), "a-vat");
    await user.click(screen.getByRole("button", { name: "Save settings" }));
    await waitFor(() =>
      expect(apiClient.put).toHaveBeenCalledWith("/sal/settings", {
        company_id: "co1", receivable_account_id: "a-ar", revenue_account_id: "a-rev", vat_account_id: "a-vat",
        cogs_account_id: null, inventory_account_id: null, receipt_account_id: null,
        vat_percent: "7.5", payment_terms_days: 30,
      }),
    );
    expect(await screen.findByRole("status")).toHaveTextContent("Settings saved");
  });

  it("loads existing settings into the form", async () => {
    mockGets([], { company_id: "co1", receivable_account_id: "a-ar", revenue_account_id: "a-rev", vat_account_id: null, vat_percent: "0.00", payment_terms_days: 14 });
    renderIn(<SalesSettingsPage />);
    await waitFor(() => expect(screen.getByLabelText("Company")).toHaveValue("co1"));
    expect(screen.getByLabelText("VAT account (output VAT payable)")).toHaveValue("");
    expect(screen.getByLabelText("Payment terms (days)")).toHaveValue("14");
  });
});

const DOC_ORDER = order({
  status: "delivered",
  deliveries: [{ id: "d1", number: "DN-00001", delivered_at: "2026-10-27", lines: [{ order_line_id: "l1", material_item_id: "i-bread", quantity: "10.0000", valued_cost: "4000" }] }],
  invoices: [{
    id: "s1", number: "SI-00001", order_id: "o1", invoice_date: "2026-10-27", due_date: "2026-11-10",
    net_amount: "5000.00", vat_amount: "375.00", amount: "5375.00",
    lines: [{ order_line_id: "l1", material_item_id: "i-bread", quantity: "10.0000", unit_price: "500.0000", line_total: "5000.00" }],
  }],
});

function renderDoc(kind: "invoice" | "delivery", docId: string) {
  mockGets([DOC_ORDER], { company_id: "co1", receivable_account_id: "a", revenue_account_id: "b", vat_account_id: null, vat_percent: "7.5", payment_terms_days: 14 });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/sales/print/o1/${kind}/${docId}`]}>
        <Routes>
          <Route path="/sales/print/:orderId/invoice/:docId" element={<SalesDocumentPage kind="invoice" />} />
          <Route path="/sales/print/:orderId/delivery/:docId" element={<SalesDocumentPage kind="delivery" />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("SalesDocumentPage", () => {
  it("renders an invoice with company, client, lines, VAT and total", async () => {
    renderDoc("invoice", "s1");
    const doc = await screen.findByRole("article", { name: "Invoice" });
    expect(doc).toHaveTextContent("SI-00001");
    expect(doc).toHaveTextContent("Acme Foods");
    expect(doc).toHaveTextContent("Shoprite");
    expect(doc).toHaveTextContent("12 Allen Avenue");
    expect(doc).toHaveTextContent("BREAD — Bread");
    expect(doc).toHaveTextContent("VAT (7.5%)");
    expect(doc).toHaveTextContent(/Total.*5,375\.00/);
    expect(doc).toHaveTextContent("Due: 2026-11-10");
  });

  it("renders a delivery note without prices and with signature lines", async () => {
    renderDoc("delivery", "d1");
    const doc = await screen.findByRole("article", { name: "Delivery note" });
    expect(doc).toHaveTextContent("DN-00001");
    expect(doc).toHaveTextContent("Received by");
    expect(doc).not.toHaveTextContent("Unit price");
    expect(doc).not.toHaveTextContent("5,375");
  });

  it("says so when the document is not on the order", async () => {
    renderDoc("invoice", "nope");
    expect(await screen.findByText("Document not found")).toBeInTheDocument();
  });

  it("opens the browser print dialog", async () => {
    const print = vi.spyOn(window, "print").mockImplementation(() => {});
    renderDoc("invoice", "s1");
    await userEvent.setup().click(await screen.findByRole("button", { name: "Print / save as PDF" }));
    expect(print).toHaveBeenCalled();
  });
});

const INVOICE = (over: any = {}) => ({
  id: "s1", number: "SI-00001", order_id: "o1", invoice_date: "2026-10-27", due_date: "2026-11-10",
  net_amount: "5000.00", vat_amount: "375.00", amount: "5375.00", amount_paid: "0.00", balance: "5375.00", payment_status: "unpaid", ...over,
});

function mockInvoiceGets(invoices: any[], settings: any) {
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === "/sal/settings") return Promise.resolve({ data: { data: settings } } as any);
    const data: Record<string, any> = {
      "/sal/invoices": invoices,
      "/sal/sales-orders": [order()],
      "/fin/chart-of-accounts": [{ id: "a-bank", code: "1000", name: "GTB Current" }],
    };
    return url in data ? Promise.resolve({ data: { data: data[url] } } as any) : Promise.reject(new Error(`unexpected GET ${url}`));
  });
}

const SETTINGS = { company_id: "co1", receivable_account_id: "a", revenue_account_id: "b", vat_account_id: null, cogs_account_id: null, inventory_account_id: null, receipt_account_id: null, vat_percent: "7.5", payment_terms_days: 14 };

describe("SalesInvoicesPage payments", () => {
  it("shows paid, balance and status, and hides the button once paid", async () => {
    mockInvoiceGets([INVOICE(), INVOICE({ id: "s2", number: "SI-00002", amount_paid: "5375.00", balance: "0.00", payment_status: "paid" })], SETTINGS);
    renderIn(<SalesInvoicesPage />);
    await screen.findByText("SI-00001");
    expect(screen.getByText("Unpaid")).toBeInTheDocument();
    const paidRow = screen.getByText("SI-00002").closest("tr")!;
    expect(within(paidRow).getByText("Paid")).toBeInTheDocument();
    expect(within(paidRow).queryByRole("button", { name: "Record payment" })).toBeNull();
    expect(screen.getAllByRole("button", { name: "Record payment" })).toHaveLength(1);
  });

  it("records a payment into a chosen account", async () => {
    mockInvoiceGets([INVOICE()], SETTINGS); // no default receipt account -> must choose one
    vi.mocked(apiClient.post).mockResolvedValue({ data: {} } as any);
    const user = userEvent.setup();
    renderIn(<SalesInvoicesPage />);
    await user.click(await screen.findByRole("button", { name: "Record payment" }));
    expect(await screen.findByLabelText("Amount received")).toHaveValue("5375");
    await screen.findByRole("option", { name: "1000 — GTB Current" });
    await user.clear(screen.getByLabelText("Amount received"));
    await user.type(screen.getByLabelText("Amount received"), "2000");
    await user.type(screen.getByLabelText("Reference"), "NIP-9");
    await user.selectOptions(screen.getByLabelText("Paid into"), "a-bank");
    await user.click(screen.getAllByRole("button", { name: "Record payment" })[0]);
    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith("/sal/invoices/s1/payments", {
        amount: "2000", method: "transfer", reference: "NIP-9", deposit_account_id: "a-bank",
      }),
    );
  });

  it("leaves the account blank to use the default when one is set", async () => {
    mockInvoiceGets([INVOICE()], { ...SETTINGS, receipt_account_id: "a-bank" });
    vi.mocked(apiClient.post).mockResolvedValue({ data: {} } as any);
    const user = userEvent.setup();
    renderIn(<SalesInvoicesPage />);
    await user.click(await screen.findByRole("button", { name: "Record payment" }));
    await screen.findByRole("option", { name: "Default account" });
    await user.click(screen.getAllByRole("button", { name: "Record payment" })[0]);
    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith("/sal/invoices/s1/payments", {
        amount: "5375", method: "transfer", reference: null, deposit_account_id: null,
      }),
    );
  });

  it("shows the server's reason when the payment is refused and keeps the panel open", async () => {
    mockInvoiceGets([INVOICE()], { ...SETTINGS, receipt_account_id: "a-bank" });
    vi.mocked(apiClient.post).mockRejectedValue({ response: { data: { title: "Payment is more than the balance owed", detail: "Balance due is 100.00." } } });
    const user = userEvent.setup();
    renderIn(<SalesInvoicesPage />);
    await user.click(await screen.findByRole("button", { name: "Record payment" }));
    await screen.findByLabelText("Amount received");
    await user.click(screen.getAllByRole("button", { name: "Record payment" })[0]);
    expect(await screen.findByText(/Balance due is 100/)).toBeInTheDocument();
    expect(screen.getByLabelText("Amount received")).toBeInTheDocument();
  });
});
