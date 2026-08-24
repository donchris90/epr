import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../api/client";

/** Real types matching backend/app/modules/sub/schemas.py exactly --
 * checked directly against the actual schemas before writing these. */
export interface Subcontractor {
  id: string;
  name: string;
  trade_specialty: string | null;
  tax_registration_number: string | null;
  status: string;
}

export interface SubcontractAgreement {
  id: string;
  subcontractor_id: string;
  contract_id: string | null;
  agreement_number: string;
  value: string;
  currency: string;
  payment_terms_summary: string | null;
  retention_percentage: string;
  status: string;
}

export interface SubcontractScopeItem {
  id: string;
  agreement_id: string;
  boq_item_id: string | null;
  cbs_line_item_id: string | null;
  description: string;
  is_lump_sum: boolean;
  quantity: string | null;
  unit: string | null;
  rate: string | null;
  lump_sum_amount: string | null;
}

export interface SubcontractProgressEntry {
  id: string;
  agreement_id: string;
  scope_item_id: string | null;
  submitted_quantity: string;
  submitted_at: string | null;
  status: string;
}

export interface MeasurementSheet {
  id: string;
  agreement_id: string;
  scope_item_id: string;
  progress_entry_id: string | null;
  verified_quantity: string;
  measured_by: string | null;
  subcontractor_countersigned_by: string | null;
  measured_at: string | null;
  status: string;
}

export interface PaymentCertificateLine {
  id: string;
  certificate_id: string;
  measurement_sheet_id: string;
  certified_quantity: string;
  rate: string;
  amount: string;
}

export interface PaymentCertificate {
  id: string;
  agreement_id: string;
  certificate_number: string;
  period_start: string | null;
  period_end: string | null;
  gross_certified_amount: string;
  retention_withheld: string;
  back_charges_total: string;
  net_payable: string;
  status: string;
  issued_at: string | null;
  compliance_waiver: boolean;
  compliance_waiver_reason: string | null;
  lines: PaymentCertificateLine[];
}

export interface BackCharge {
  id: string;
  agreement_id: string;
  payment_certificate_id: string | null;
  description: string;
  amount: string;
  reason_category: "rework" | "materials_supplied" | "other";
  raised_at: string | null;
  raised_by: string | null;
}

export interface SubcontractRetention {
  id: string;
  agreement_id: string;
  percentage: string;
  amount_withheld: string;
  release_substantial_completion_pct: string;
  release_final_pct: string;
  released_substantial_completion: boolean;
  released_final: boolean;
}

export interface SubcontractClaim {
  id: string;
  agreement_id: string;
  claim_type: "delay" | "additional_scope" | "other";
  description: string;
  claimed_amount: string | null;
  claimed_days: number | null;
  status: string;
  submitted_at: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  response_notes: string | null;
}

export interface PerformanceRating {
  id: string;
  subcontractor_id: string;
  project_id: string | null;
  period_label: string | null;
  quality_score: string;
  schedule_score: string;
  safety_score: string;
  responsiveness_score: string;
  overall_score: string;
  rated_by: string | null;
  rated_at: string | null;
}

export interface ComplianceDocument {
  id: string;
  subcontractor_id: string;
  document_id: string | null;
  doc_type: string;
  valid_until: string | null;
}

// --- Subcontractors ------------------------------------------------------------

export function useSubcontractors() {
  return useQuery({
    queryKey: ["sub", "subcontractors"],
    queryFn: async (): Promise<Subcontractor[]> => (await apiClient.get("/sub/subcontractors")).data.data,
  });
}

export function useSubcontractor(subcontractorId?: string) {
  return useQuery({
    queryKey: ["sub", "subcontractors", subcontractorId],
    queryFn: async (): Promise<Subcontractor> => (await apiClient.get(`/sub/subcontractors/${subcontractorId}`)).data,
    enabled: !!subcontractorId,
  });
}

export function useCreateSubcontractor() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { name: string; trade_specialty?: string }) => apiClient.post("/sub/subcontractors", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sub", "subcontractors"] }),
  });
}

// --- Agreements & scope ----------------------------------------------------------

export function useAgreements() {
  return useQuery({
    queryKey: ["sub", "agreements"],
    queryFn: async (): Promise<SubcontractAgreement[]> => (await apiClient.get("/sub/agreements")).data.data,
  });
}

export function useAgreement(agreementId?: string) {
  return useQuery({
    queryKey: ["sub", "agreements", agreementId],
    queryFn: async (): Promise<SubcontractAgreement> => (await apiClient.get(`/sub/agreements/${agreementId}`)).data,
    enabled: !!agreementId,
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
    queryFn: async (): Promise<SubcontractScopeItem[]> => (await apiClient.get(`/sub/agreements/${agreementId}/scope-items`)).data.data,
    enabled: !!agreementId,
  });
}

export function useAddScopeItem(agreementId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { description: string; quantity?: string; unit?: string; rate?: string; is_lump_sum?: boolean; lump_sum_amount?: string }) =>
      apiClient.post(`/sub/agreements/${agreementId}/scope-items`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sub", "agreements", agreementId, "scope-items"] }),
  });
}

// --- Progress ----------------------------------------------------------------------

export function useProgressEntries(agreementId?: string) {
  return useQuery({
    queryKey: ["sub", "agreements", agreementId, "progress-entries"],
    queryFn: async (): Promise<SubcontractProgressEntry[]> =>
      (await apiClient.get(`/sub/agreements/${agreementId}/progress-entries`)).data.data,
    enabled: !!agreementId,
  });
}

export function useSubmitProgress(agreementId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { scope_item_id?: string; submitted_quantity: string }) =>
      apiClient.post(`/sub/agreements/${agreementId}/progress-entries`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sub", "agreements", agreementId, "progress-entries"] }),
  });
}

// --- Measurement sheets --------------------------------------------------------

export function useMeasurementSheets(agreementId?: string) {
  return useQuery({
    queryKey: ["sub", "agreements", agreementId, "measurement-sheets"],
    queryFn: async (): Promise<MeasurementSheet[]> =>
      (await apiClient.get(`/sub/agreements/${agreementId}/measurement-sheets`)).data.data,
    enabled: !!agreementId,
  });
}

export function useCreateMeasurementSheet(agreementId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { agreement_id: string; scope_item_id: string; progress_entry_id?: string; verified_quantity: string }) =>
      apiClient.post("/sub/measurement-sheets", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sub", "agreements", agreementId, "measurement-sheets"] }),
  });
}

export function useVerifyMeasurementSheet(agreementId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sheetId: string) => apiClient.post(`/sub/measurement-sheets/${sheetId}/verify`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sub", "agreements", agreementId, "measurement-sheets"] }),
  });
}

// --- Payment certificates --------------------------------------------------------

export function usePaymentCertificates(agreementId?: string) {
  return useQuery({
    queryKey: ["sub", "agreements", agreementId, "payment-certificates"],
    queryFn: async (): Promise<PaymentCertificate[]> => (await apiClient.get(`/sub/agreements/${agreementId}/payment-certificates`)).data.data,
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

// --- Back charges --------------------------------------------------------------

export function useBackCharges(agreementId?: string) {
  return useQuery({
    queryKey: ["sub", "agreements", agreementId, "back-charges"],
    queryFn: async (): Promise<BackCharge[]> => (await apiClient.get(`/sub/agreements/${agreementId}/back-charges`)).data.data,
    enabled: !!agreementId,
  });
}

export function useAddBackCharge(agreementId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { description: string; amount: string; reason_category?: string; payment_certificate_id?: string }) =>
      apiClient.post(`/sub/agreements/${agreementId}/back-charges`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sub", "agreements", agreementId, "back-charges"] }),
  });
}

// --- Retention -------------------------------------------------------------------

export function useRetentionRecords(agreementId?: string) {
  return useQuery({
    queryKey: ["sub", "agreements", agreementId, "retention"],
    queryFn: async (): Promise<SubcontractRetention[]> => (await apiClient.get(`/sub/agreements/${agreementId}/retention`)).data.data,
    enabled: !!agreementId,
  });
}

export function useAddRetention(agreementId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (percentage?: string) => apiClient.post(`/sub/agreements/${agreementId}/retention`, { percentage }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sub", "agreements", agreementId, "retention"] }),
  });
}

/** Real bug found and fixed here: this hook previously never sent
 * `stage` at all, despite ReleaseRetentionSchema requiring it
 * (validated against "substantial_completion"/"final") -- every real
 * call to this hook would have failed with a 422. */
export function useReleaseRetention(agreementId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ retentionId, stage }: { retentionId: string; stage: "substantial_completion" | "final" }) =>
      apiClient.post(`/sub/retention/${retentionId}/release`, { stage }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sub", "agreements", agreementId, "retention"] }),
  });
}

// --- Claims --------------------------------------------------------------------

export function useClaims(agreementId?: string) {
  return useQuery({
    queryKey: ["sub", "agreements", agreementId, "claims"],
    queryFn: async (): Promise<SubcontractClaim[]> => (await apiClient.get(`/sub/agreements/${agreementId}/claims`)).data.data,
    enabled: !!agreementId,
  });
}

export function useSubmitClaim(agreementId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { claim_type: string; description: string; claimed_amount?: string; claimed_days?: number }) =>
      apiClient.post(`/sub/agreements/${agreementId}/claims`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sub", "agreements", agreementId, "claims"] }),
  });
}

export function useReviewClaim(agreementId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ claimId, decision, responseNotes }: { claimId: string; decision: "approved" | "rejected"; responseNotes?: string }) =>
      apiClient.post(`/sub/claims/${claimId}/review`, { decision, response_notes: responseNotes }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sub", "agreements", agreementId, "claims"] }),
  });
}

// --- Compliance & performance (subcontractor-level, not agreement-level) --------

export function useComplianceDocuments(subcontractorId?: string) {
  return useQuery({
    queryKey: ["sub", "subcontractors", subcontractorId, "compliance-documents"],
    queryFn: async (): Promise<ComplianceDocument[]> =>
      (await apiClient.get(`/sub/subcontractors/${subcontractorId}/compliance-documents`)).data.data,
    enabled: !!subcontractorId,
  });
}

export function useAddComplianceDocument(subcontractorId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { doc_type: string; document_id?: string; valid_until?: string }) =>
      apiClient.post(`/sub/subcontractors/${subcontractorId}/compliance-documents`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sub", "subcontractors", subcontractorId, "compliance-documents"] }),
  });
}

export function usePerformanceRatings(subcontractorId?: string) {
  return useQuery({
    queryKey: ["sub", "subcontractors", subcontractorId, "ratings"],
    queryFn: async (): Promise<PerformanceRating[]> =>
      (await apiClient.get(`/sub/subcontractors/${subcontractorId}/ratings`)).data.data,
    enabled: !!subcontractorId,
  });
}

export function useAddPerformanceRating(subcontractorId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { project_id?: string; period_label?: string; quality_score: string; schedule_score: string; safety_score: string; responsiveness_score: string }) =>
      apiClient.post(`/sub/subcontractors/${subcontractorId}/ratings`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sub", "subcontractors", subcontractorId, "ratings"] }),
  });
}
