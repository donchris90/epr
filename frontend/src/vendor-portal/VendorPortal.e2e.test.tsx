import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import VendorPortalApp from "./index";
import { vendorPortalClient } from "./api/client";
import { clearPortalSession } from "./lib/auth";

/**
 * E2E-style walk through the real vendor portal build: login,
 * unauthorized redirect, dashboard, PO acknowledgment, invoice
 * submission, logout. Mocks only the HTTP boundary (vendorPortalClient)
 * -- everything else (routing, auth guard, localStorage token
 * storage, the actual page components) is real, exercised exactly as
 * a browser would. Deliberately mirrors
 * subcontractor-portal/SubcontractorPortal.e2e.test.tsx's own
 * established, proven pattern -- including its own real /portal/*
 * nesting fix, applied here from the start.
 */
vi.mock("./api/client", () => ({
  vendorPortalClient: { get: vi.fn(), post: vi.fn() },
  getVendorPortalErrorMessage: vi.fn((err: any) => err?.response?.data?.title || "Something went wrong."),
}));

const PURCHASE_ORDER = {
  id: "po-1",
  purchase_request_id: null,
  rfq_quotation_id: null,
  vendor_id: "vendor-1",
  po_number: "PO-001",
  status: "issued",
  total_value: "750000.00",
  currency: "NGN",
  is_blanket: false,
  compliance_waiver: false,
};

function fakeJwt(payload: Record<string, unknown>) {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const body = btoa(JSON.stringify(payload));
  return `${header}.${body}.fake-signature`;
}

const ACCESS_TOKEN = fakeJwt({ user_id: "portal-user-1", tenant_id: "tenant-1", is_portal_user: true });

function mockGet(url: string) {
  if (url === "/vnp/auth/me") {
    return Promise.resolve({ data: { id: "portal-user-1", vendor_id: "vendor-1", email: "vendor@example.com", is_active: true } });
  }
  if (url === "/vnp/vendor-users/portal-user-1/purchase-orders") {
    return Promise.resolve({ data: { data: [PURCHASE_ORDER] } });
  }
  if (url === "/vnp/vendor-users/portal-user-1/invoices") {
    return Promise.resolve({ data: { data: [] } });
  }
  return Promise.reject(new Error(`unexpected GET ${url}`));
}

function renderApp(initialPath = "/vendor/login") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/vendor/*" element={<VendorPortalApp />} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  clearPortalSession();
  vi.mocked(vendorPortalClient.get).mockImplementation(mockGet as any);
  vi.mocked(vendorPortalClient.post).mockImplementation((url: string) => {
    if (url === "/vnp/auth/login") {
      return Promise.resolve({ data: { access_token: ACCESS_TOKEN, refresh_token: "fake-refresh-token" } });
    }
    return Promise.reject(new Error(`unexpected POST ${url}`));
  });
});

describe("Vendor portal — unauthorized", () => {
  it("redirects an unauthenticated visitor straight to login", async () => {
    renderApp("/vendor/dashboard");
    expect(await screen.findByPlaceholderText("you@yourcompany.com")).toBeInTheDocument();
  });
});

describe("Vendor portal — login", () => {
  it("logs in and reaches the real dashboard with real purchase order data", async () => {
    const user = userEvent.setup();
    renderApp();

    await user.type(screen.getByPlaceholderText("you@yourcompany.com"), "vendor@example.com");
    await user.type(screen.getByPlaceholderText("••••••••"), "realpassword123");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText("PO-001")).toBeInTheDocument();
    expect(vendorPortalClient.post).toHaveBeenCalledWith("/vnp/auth/login", { email: "vendor@example.com", password: "realpassword123" });
  });

  it("shows a real error and does not navigate on invalid credentials", async () => {
    vi.mocked(vendorPortalClient.post).mockRejectedValueOnce({ response: { data: { title: "Invalid credentials" } } });
    const user = userEvent.setup();
    renderApp();

    await user.type(screen.getByPlaceholderText("you@yourcompany.com"), "vendor@example.com");
    await user.type(screen.getByPlaceholderText("••••••••"), "wrongpassword");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText("Invalid credentials")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("you@yourcompany.com")).toBeInTheDocument();
  });
});

describe("Vendor portal — purchase order acknowledgment", () => {
  async function loginAndOpenOrder(user: ReturnType<typeof userEvent.setup>) {
    renderApp();
    await user.type(screen.getByPlaceholderText("you@yourcompany.com"), "vendor@example.com");
    await user.type(screen.getByPlaceholderText("••••••••"), "realpassword123");
    await user.click(screen.getByRole("button", { name: /sign in/i }));
    await user.click(await screen.findByText("PO-001"));
  }

  it("walks dashboard -> PO detail -> real acknowledgment", async () => {
    const user = userEvent.setup();
    vi.mocked(vendorPortalClient.post).mockImplementation((url: string) => {
      if (url === "/vnp/auth/login") {
        return Promise.resolve({ data: { access_token: ACCESS_TOKEN, refresh_token: "fake-refresh-token" } });
      }
      if (url === "/vnp/vendor-users/portal-user-1/acknowledge-order") {
        return Promise.resolve({ data: { id: "ack-1", purchase_order_id: "po-1", acknowledged_at: "2026-08-23T00:00:00Z", expected_delivery_date: null } });
      }
      return Promise.reject(new Error(`unexpected POST ${url}`));
    });

    await loginAndOpenOrder(user);
    expect(await screen.findByRole("button", { name: /^acknowledge order$/i })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /^acknowledge order$/i }));

    await waitFor(() => {
      expect(vendorPortalClient.post).toHaveBeenCalledWith(
        "/vnp/vendor-users/portal-user-1/acknowledge-order",
        expect.objectContaining({ purchase_order_id: "po-1" })
      );
    });
    expect(await screen.findByText(/order acknowledged/i)).toBeInTheDocument();
  });
});

describe("Vendor portal — invoice submission", () => {
  it("submits a real invoice with a real amount", async () => {
    const user = userEvent.setup();
    vi.mocked(vendorPortalClient.post).mockImplementation((url: string, body?: any) => {
      if (url === "/vnp/auth/login") {
        return Promise.resolve({ data: { access_token: ACCESS_TOKEN, refresh_token: "fake-refresh-token" } });
      }
      if (url === "/vnp/vendor-users/portal-user-1/invoices") {
        return Promise.resolve({
          data: { id: "inv-1", purchase_order_id: body?.purchase_order_id ?? null, subcontract_certificate_id: null, invoice_number: body?.invoice_number, amount: body?.amount, status: "pending" },
        });
      }
      return Promise.reject(new Error(`unexpected POST ${url}`));
    });

    renderApp();
    await user.type(screen.getByPlaceholderText("you@yourcompany.com"), "vendor@example.com");
    await user.type(screen.getByPlaceholderText("••••••••"), "realpassword123");
    await user.click(screen.getByRole("button", { name: /sign in/i }));
    await screen.findByText("PO-001");

    await user.click(screen.getByRole("link", { name: /invoices/i }));
    await user.type(await screen.findByPlaceholderText(/INV-2026-001/i), "INV-100");
    await user.type(screen.getByPlaceholderText("0.00"), "45000");
    await user.click(screen.getByRole("button", { name: /submit invoice/i }));

    await waitFor(() => {
      expect(vendorPortalClient.post).toHaveBeenCalledWith(
        "/vnp/vendor-users/portal-user-1/invoices",
        expect.objectContaining({ invoice_number: "INV-100", amount: "45000" })
      );
    });
  });
});

describe("Vendor portal — logout", () => {
  it("real sign-out clears the session and returns to login", async () => {
    const user = userEvent.setup();
    vi.mocked(vendorPortalClient.post).mockImplementation((url: string) => {
      if (url === "/vnp/auth/login") {
        return Promise.resolve({ data: { access_token: ACCESS_TOKEN, refresh_token: "fake-refresh-token" } });
      }
      if (url === "/vnp/auth/logout") {
        return Promise.resolve({ data: { status: "logged out" } });
      }
      return Promise.reject(new Error(`unexpected POST ${url}`));
    });

    renderApp();
    await user.type(screen.getByPlaceholderText("you@yourcompany.com"), "vendor@example.com");
    await user.type(screen.getByPlaceholderText("••••••••"), "realpassword123");
    await user.click(screen.getByRole("button", { name: /sign in/i }));
    await screen.findByText("PO-001");

    await user.click(screen.getByText("Sign out"));

    expect(await screen.findByPlaceholderText("you@yourcompany.com")).toBeInTheDocument();
  });
});
