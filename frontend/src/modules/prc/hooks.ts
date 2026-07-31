import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../api/client";

// --- Vendors (PRC-01) ----------------------------------------------------------

export function useVendors() {
  return useQuery({
    queryKey: ["prc", "vendors"],
    queryFn: async () => (await apiClient.get("/prc/vendors")).data.data,
  });
}

export function useCreateVendor() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { name: string; tax_registration_number?: string }) => apiClient.post("/prc/vendors", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prc", "vendors"] }),
  });
}

export function useAddComplianceDocument(vendorId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { doc_type: string; valid_until?: string; document_id?: string }) =>
      apiClient.post(`/prc/vendors/${vendorId}/compliance-documents`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prc", "vendors"] }),
  });
}

// --- Purchase requests (PRC-04, PRC-11, business rule: budget breach) ----------

export function usePurchaseRequests(status?: string) {
  return useQuery({
    queryKey: ["prc", "purchase-requests", status],
    queryFn: async () =>
      (await apiClient.get("/prc/purchase-requests", { params: status ? { status } : {} })).data.data,
  });
}

export function useCreatePurchaseRequest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      project_id?: string;
      description: string;
      quantity: string;
      unit?: string;
      estimated_unit_cost?: string;
      estimated_total?: string;
    }) => apiClient.post("/prc/purchase-requests", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prc", "purchase-requests"] }),
  });
}

export function useSubmitPurchaseRequest(prId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { remaining_budget?: string; override?: boolean; override_reason?: string }) =>
      apiClient.post(`/prc/purchase-requests/${prId}/submit`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prc", "purchase-requests"] }),
  });
}

export function useApprovePurchaseRequest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (prId: string) => apiClient.post(`/prc/purchase-requests/${prId}/approve`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prc", "purchase-requests"] }),
  });
}

// --- Purchase orders (PRC-05, PRC-06, PRC-12) -----------------------------------

export function usePurchaseOrders(status?: string) {
  return useQuery({
    queryKey: ["prc", "purchase-orders", status],
    queryFn: async () => (await apiClient.get("/prc/purchase-orders", { params: status ? { status } : {} })).data.data,
  });
}

export function usePurchaseOrder(poId?: string) {
  return useQuery({
    queryKey: ["prc", "purchase-orders", "detail", poId],
    queryFn: async () => (await apiClient.get(`/prc/purchase-orders/${poId}`)).data,
    enabled: !!poId,
  });
}

export function useCreatePurchaseOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      vendor_id: string;
      purchase_request_id?: string;
      po_number: string;
      total_value: string;
      currency?: string;
      lines?: { description: string; quantity: string; unit_price: string; unit?: string }[];
    }) => apiClient.post("/prc/purchase-orders", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prc", "purchase-orders"] }),
  });
}

export function useInitiatePOApproval(poId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (thresholds: { value_threshold: string | null; role_required: string }[]) =>
      apiClient.post(`/prc/purchase-orders/${poId}/approval-workflow/initiate`, { thresholds }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prc", "purchase-orders", "detail", poId] }),
  });
}
export function useDecidePOApprovalStep(poId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ stepId, decision, comments }: { stepId: string; decision: "approved" | "rejected"; comments?: string }) =>
      apiClient.post(`/prc/po-approval-steps/${stepId}/decide`, { decision, comments }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prc", "purchase-orders", "detail", poId] }),
  });
}

export function useIssuePurchaseOrder(poId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { waiver?: boolean; waiver_reason?: string }) =>
      apiClient.post(`/prc/purchase-orders/${poId}/issue`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prc", "purchase-orders", "detail", poId] }),
  });
}

// --- Goods receipt (PRC-07, PRC-12) ------------------------------------------------

export function useCreateGRN(poId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { lines: { po_line_id: string; quantity_received: string; condition?: string; discrepancy_notes?: string }[] }) =>
      apiClient.post("/prc/goods-receipt-notes", { purchase_order_id: poId, ...payload }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prc", "purchase-orders", "detail", poId] }),
  });
}

export function useConfirmGRN(poId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (grnId: string) => apiClient.post(`/prc/goods-receipt-notes/${grnId}/confirm`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prc", "purchase-orders", "detail", poId] }),
  });
}

// --- Three-way invoice matching (PRC-08, business rule) ---------------------------

export function useCreateInvoiceMatch(poId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { goods_receipt_note_id?: string; vendor_invoice_reference: string; invoice_amount: string }) =>
      apiClient.post(`/prc/purchase-orders/${poId}/invoice-match`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prc", "purchase-orders", "detail", poId] }),
  });
}

export function useApproveMatchException(poId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ matchId, reason }: { matchId: string; reason: string }) =>
      apiClient.post(`/prc/invoice-matches/${matchId}/approve-exception`, { reason }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prc", "purchase-orders", "detail", poId] }),
  });
}
