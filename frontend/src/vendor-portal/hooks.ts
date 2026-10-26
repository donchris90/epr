import { useEffect, useState } from "react";
import { vendorPortalClient, getVendorPortalErrorMessage } from "./api/client";
import { getPortalUserId, setPortalTokens, clearPortalSession } from "./lib/auth";
import type { RfqInvitation, PurchaseOrder, OrderAcknowledgment, Quotation, InvoiceUpload, PortalUser, BankingDetails, BankingChangeRequest } from "./types";

/** Real login, backed by POST /v1/vnp/auth/login (built earlier this
 * session -- previously genuinely missing from the backend entirely,
 * see docs/SUBCONTRACTOR_VENDOR_PORTAL_GAPS.md). */
export async function loginVendor(email: string, password: string): Promise<void> {
  const res = await vendorPortalClient.post("/vnp/auth/login", { email, password });
  setPortalTokens(res.data.access_token, res.data.refresh_token);
}

export async function logoutVendor(): Promise<void> {
  try {
    const { getPortalRefreshToken } = await import("./lib/auth");
    const refreshToken = getPortalRefreshToken();
    if (refreshToken) {
      await vendorPortalClient.post(
        "/vnp/auth/logout",
        {},
        { headers: { Authorization: `Bearer ${refreshToken}` } }
      );
    }
  } catch {
    // Real, deliberate: logout still clears the local session even if
    // the real revoke call fails -- the person's own browser session
    // ends either way.
  } finally {
    clearPortalSession();
  }
}

export function useVendorProfile() {
  const [profile, setProfile] = useState<PortalUser | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    vendorPortalClient
      .get("/vnp/auth/me")
      .then((res) => setProfile(res.data))
      .catch((err) => setError(getVendorPortalErrorMessage(err)));
  }, []);

  return { profile, error };
}

export async function changeVendorPassword(currentPassword: string, newPassword: string): Promise<void> {
  await vendorPortalClient.post("/vnp/auth/me/password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
}

/** Real PO list, backed by GET
 * /v1/vnp/vendor-users/<id>/purchase-orders (built alongside this
 * frontend -- previously genuinely missing; the only prior capability
 * was acknowledging a PO already known by id, with no way to
 * discover which POs exist at all). */
export function usePurchaseOrders() {
  const [orders, setOrders] = useState<PurchaseOrder[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const userId = getPortalUserId();
    if (!userId) {
      setError("Not signed in.");
      setLoading(false);
      return;
    }
    vendorPortalClient
      .get(`/vnp/vendor-users/${userId}/purchase-orders`)
      .then((res) => setOrders(res.data.data))
      .catch((err) => setError(getVendorPortalErrorMessage(err)))
      .finally(() => setLoading(false));
  }, []);

  return { orders, error, loading };
}

export async function acknowledgeOrder(purchaseOrderId: string, expectedDeliveryDate?: string): Promise<OrderAcknowledgment> {
  const userId = getPortalUserId();
  const res = await vendorPortalClient.post(`/vnp/vendor-users/${userId}/acknowledge-order`, {
    purchase_order_id: purchaseOrderId,
    expected_delivery_date: expectedDeliveryDate || undefined,
  });
  return res.data;
}

/** The RFQs this vendor was invited to, from GET
 * /v1/vnp/vendor-users/<id>/rfq-invitations (own invitations only). */
export function useRfqInvitations() {
  const [items, setItems] = useState<RfqInvitation[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  function reload() {
    const userId = getPortalUserId();
    if (!userId) {
      setError("Not signed in.");
      setLoading(false);
      return;
    }
    vendorPortalClient
      .get(`/vnp/vendor-users/${userId}/rfq-invitations`)
      .then((res) => setItems(res.data.data))
      .catch((err) => setError(getVendorPortalErrorMessage(err)))
      .finally(() => setLoading(false));
  }

  useEffect(reload, []);

  return { items, error, loading, reload };
}

export async function submitQuote(input: { rfq_id: string; price: string; lead_time_days?: number; payment_terms?: string }): Promise<Quotation> {
  const userId = getPortalUserId();
  const res = await vendorPortalClient.post(`/vnp/vendor-users/${userId}/quotes`, input);
  return res.data;
}

export async function reviseQuote(rfqId: string, input: { price: string; lead_time_days?: number | null; payment_terms?: string | null }): Promise<Quotation> {
  const userId = getPortalUserId();
  const res = await vendorPortalClient.put(`/vnp/vendor-users/${userId}/quotes/${rfqId}`, input);
  return res.data;
}

export async function declineRfq(rfqId: string, reason?: string): Promise<void> {
  const userId = getPortalUserId();
  await vendorPortalClient.post(`/vnp/vendor-users/${userId}/rfq-invitations/${rfqId}/decline`, { reason: reason || null });
}

export function useInvoices() {
  const [invoices, setInvoices] = useState<InvoiceUpload[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  function reload() {
    const userId = getPortalUserId();
    if (!userId) return;
    vendorPortalClient
      .get(`/vnp/vendor-users/${userId}/invoices`)
      .then((res) => setInvoices(res.data.data))
      .catch((err) => setError(getVendorPortalErrorMessage(err)));
  }

  useEffect(reload, []);

  return { invoices, error, reload };
}

/** Real invoice submission -- deliberately no document-attachment
 * field here despite UploadInvoiceSchema accepting an
 * invoice_document_id: confirmed directly that POST
 * /v1/documents/upload-request requires the documents:write
 * permission, which a real vendor-portal token does not and should
 * not have (that permission is tenant-wide, far broader than "attach
 * this one invoice's own file"). See
 * docs/SUBCONTRACTOR_VENDOR_PORTAL_GAPS.md. */
export async function uploadInvoice(input: {
  invoice_number: string;
  amount: string;
  purchase_order_id?: string;
  invoice_document_id?: string;
}): Promise<InvoiceUpload> {
  const userId = getPortalUserId();
  const res = await vendorPortalClient.post(`/vnp/vendor-users/${userId}/invoices`, input);
  return res.data;
}

// --- Banking details change requests (VNP-05) ----------------------------------
// A submission only STAGES a request; finance approval is what applies it
// to the live vendor record (see backend vnp services.approve_banking_change).

export function useBankingChangeRequests() {
  const [requests, setRequests] = useState<BankingChangeRequest[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  function reload() {
    const userId = getPortalUserId();
    if (!userId) return;
    vendorPortalClient
      .get(`/vnp/vendor-users/${userId}/banking-change-requests`)
      .then((res) => setRequests(res.data.data))
      .catch((err) => setError(getVendorPortalErrorMessage(err)));
  }

  useEffect(reload, []);

  return { requests, error, reload };
}

export async function submitBankingChange(details: BankingDetails): Promise<BankingChangeRequest> {
  const userId = getPortalUserId();
  const res = await vendorPortalClient.post(`/vnp/vendor-users/${userId}/banking-change-requests`, {
    proposed_banking_details: details,
  });
  return res.data;
}
