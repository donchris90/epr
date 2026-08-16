import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../api/client";

export function useSubcontractors() {
  return useQuery({
    queryKey: ["sub", "subcontractors"],
    queryFn: async () => (await apiClient.get("/sub/subcontractors")).data.data,
  });
}

export function useCreateSubcontractor() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { name: string; trade_specialty?: string }) => apiClient.post("/sub/subcontractors", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sub", "subcontractors"] }),
  });
}

export function useAgreements() {
  return useQuery({
    queryKey: ["sub", "agreements"],
    queryFn: async () => (await apiClient.get("/sub/agreements")).data.data,
  });
}

export function useCreateAgreement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { subcontractor_id: string; agreement_number: string; value: string; retention_percentage?: string }) =>
      apiClient.post("/sub/agreements", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sub", "agreements"] }),
  });
}

export function useScopeItems(agreementId?: string) {
  return useQuery({
    queryKey: ["sub", "agreements", agreementId, "scope-items"],
    queryFn: async () => (await apiClient.get(`/sub/agreements/${agreementId}/scope-items`)).data.data,
    enabled: !!agreementId,
  });
}

export function useAddScopeItem(agreementId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { description: string; quantity?: string; unit?: string; rate?: string; is_lump_sum?: boolean }) =>
      apiClient.post(`/sub/agreements/${agreementId}/scope-items`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sub", "agreements", agreementId, "scope-items"] }),
  });
}

export function useCreateMeasurementSheet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { agreement_id: string; scope_item_id: string; verified_quantity: string }) =>
      apiClient.post("/sub/measurement-sheets", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sub"] }),
  });
}

export function useVerifyMeasurementSheet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sheetId: string) => apiClient.post(`/sub/measurement-sheets/${sheetId}/verify`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sub"] }),
  });
}

export function usePaymentCertificates(agreementId?: string) {
  return useQuery({
    queryKey: ["sub", "agreements", agreementId, "payment-certificates"],
    queryFn: async () => (await apiClient.get(`/sub/agreements/${agreementId}/payment-certificates`)).data.data,
    enabled: !!agreementId,
  });
}

export function useIssuePaymentCertificate(agreementId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { certificate_number: string; measurement_sheet_ids: string[]; waiver?: boolean; waiver_reason?: string }) =>
      apiClient.post(`/sub/agreements/${agreementId}/payment-certificates`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sub", "agreements", agreementId, "payment-certificates"] }),
  });
}

export function useReleaseRetention() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (retentionId: string) => apiClient.post(`/sub/retention/${retentionId}/release`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sub"] }),
  });
}
