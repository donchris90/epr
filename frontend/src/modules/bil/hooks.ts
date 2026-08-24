import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../api/client";

/** Real type matching backend/app/modules/bil/schemas.py's own
 * VariationOrderSchema exactly -- checked directly before writing
 * this, not guessed. */
export interface VariationOrder {
  id: string;
  contract_id: string;
  boq_item_id: string | null;
  varied_quantity: string;
  status: string;
}

// --- Progress certificates (BIL-01, BIL-09) -------------------------------------

export function useCertificates(status?: string) {
  return useQuery({
    queryKey: ["bil", "certificates", status],
    queryFn: async () => (await apiClient.get("/bil/certificates", { params: status ? { status } : {} })).data.data,
  });
}

export function useCertificate(certificateId?: string) {
  return useQuery({
    queryKey: ["bil", "certificates", "detail", certificateId],
    queryFn: async () => (await apiClient.get(`/bil/certificates/${certificateId}`)).data,
    enabled: !!certificateId,
  });
}

export function useCreateCertificate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { contract_id?: string; project_id?: string; certificate_number: string }) =>
      apiClient.post("/bil/certificates", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["bil", "certificates"] }),
  });
}

export function useAddCertificateLine(certificateId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      boq_item_id: string;
      certified_quantity: string;
      rate: string;
      contracted_quantity: string;
      variation_order_id?: string;
    }) => apiClient.post(`/bil/certificates/${certificateId}/lines`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["bil", "certificates", "detail", certificateId] }),
  });
}

export function useApplyRetention(certificateId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (percentage: string) => apiClient.post(`/bil/certificates/${certificateId}/apply-retention`, { percentage }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["bil", "certificates", "detail", certificateId] }),
  });
}

export function useSubmitCertificate(certificateId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.post(`/bil/certificates/${certificateId}/submit`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["bil", "certificates", "detail", certificateId] });
      qc.invalidateQueries({ queryKey: ["bil", "certificates"] });
    },
  });
}

export function useApproveCertificate(certificateId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { approval_method: string; approved_by?: string }) =>
      apiClient.post(`/bil/certificates/${certificateId}/approve`, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["bil", "certificates", "detail", certificateId] });
      qc.invalidateQueries({ queryKey: ["bil", "certificates"] });
    },
  });
}

// --- Variation orders (BIL-04, business rule) -----------------------------------

export function useVariationOrders(status?: string) {
  return useQuery({
    queryKey: ["bil", "variation-orders", status],
    queryFn: async (): Promise<VariationOrder[]> => (await apiClient.get("/bil/variation-orders", { params: status ? { status } : {} })).data.data,
  });
}

export function useCreateVariationOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { contract_id: string; boq_item_id?: string; description: string; varied_quantity?: string; varied_rate?: string }) =>
      apiClient.post("/bil/variation-orders", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["bil", "variation-orders"] }),
  });
}

export function useDecideVariationOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ voId, decision }: { voId: string; decision: "approved" | "rejected" }) =>
      apiClient.post(`/bil/variation-orders/${voId}/decide`, { decision }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["bil", "variation-orders"] }),
  });
}

// --- Claims (BIL-05) --------------------------------------------------------------

export function useCreateClaim() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { contract_id: string; claim_type: string; description: string; claimed_amount?: string }) =>
      apiClient.post("/bil/claims", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["bil", "claims"] }),
  });
}

// --- Payment tracking & aging (BIL-06, BIL-07) -----------------------------------

export function useRecordPayment(certificateId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ trackingId, paid_amount }: { trackingId: string; paid_amount: string }) =>
      apiClient.post(`/bil/payment-tracking/${trackingId}/record-payment`, { paid_amount }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["bil", "certificates", "detail", certificateId] }),
  });
}

export function useOutstandingInvoices() {
  return useQuery({
    queryKey: ["bil", "outstanding-invoices"],
    queryFn: async () => (await apiClient.get("/bil/outstanding-invoices")).data,
  });
}

// --- Revenue recognition (BIL-08, business rule) ---------------------------------

export function useRecognizeRevenue() {
  return useMutation({
    mutationFn: (payload: {
      contract_id: string;
      period_start: string;
      period_end: string;
      contract_total_value: string;
      percentage_complete?: string;
      method?: string;
    }) => apiClient.post("/bil/revenue-recognition", payload),
  });
}
