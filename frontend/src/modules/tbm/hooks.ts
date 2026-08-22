import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../api/client";
import type {
  ApprovalStep,
  BidDocument,
  Clarification,
  JVPartner,
  RFI,
  SubmissionReadiness,
  Tender,
  TenderBOQItem,
  TenderChecklistItem,
} from "./types";

export function useTenders() {
  return useQuery({
    queryKey: ["tbm", "tenders"],
    queryFn: async () => (await apiClient.get<{ data: Tender[] }>("/tbm/tenders")).data.data,
  });
}

export function useTender(tenderId?: string) {
  return useQuery({
    queryKey: ["tbm", "tender", tenderId],
    queryFn: async () => (await apiClient.get<Tender>(`/tbm/tenders/${tenderId}`)).data,
    enabled: !!tenderId,
  });
}

export function useCreateTender() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { opportunity_id: string; reference_number: string }) =>
      apiClient.post<Tender>("/tbm/tenders", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tbm", "tenders"] }),
  });
}

// --- BOQ items (TBM-02) -----------------------------------------------

export function useBOQItems(tenderId?: string) {
  return useQuery({
    queryKey: ["tbm", "boq-items", tenderId],
    queryFn: async () => (await apiClient.get<{ data: TenderBOQItem[] }>(`/tbm/tenders/${tenderId}/boq-items`)).data.data,
    enabled: !!tenderId,
  });
}

export function useAddBOQItem(tenderId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { description: string; unit?: string; quantity?: string; item_code?: string }) =>
      apiClient.post<TenderBOQItem>(`/tbm/tenders/${tenderId}/boq-items`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tbm", "boq-items", tenderId] }),
  });
}

// --- Bid documents (TBM-04) --------------------------------------------

export function useBidDocuments(tenderId?: string) {
  return useQuery({
    queryKey: ["tbm", "bid-documents", tenderId],
    queryFn: async () => (await apiClient.get<{ data: BidDocument[] }>(`/tbm/tenders/${tenderId}/bid-documents`)).data.data,
    enabled: !!tenderId,
  });
}

export function useAddBidDocument(tenderId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { doc_type: string; document_id?: string }) =>
      apiClient.post<BidDocument>(`/tbm/tenders/${tenderId}/bid-documents`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tbm", "bid-documents", tenderId] }),
  });
}

// --- RFIs (TBM-05) -------------------------------------------------------
// No `GET /tbm/tenders/<id>/rfis` list endpoint exists on the backend
// (routes.py only has POST create + POST respond) -- so unlike
// BOQ items/bid documents/approval steps/JV partners above, RFIs
// created here cannot be refetched from the server afterwards. The UI
// keeps them in local component state for the current session only
// and says so explicitly rather than implying they're persisted list
// data.

export function useCreateRFI(tenderId?: string) {
  return useMutation({
    mutationFn: (payload: { question: string; due_date?: string; related_boq_item_id?: string }) =>
      apiClient.post<RFI>(`/tbm/tenders/${tenderId}/rfis`, payload),
  });
}

export function useRespondToRFI() {
  return useMutation({
    mutationFn: ({ rfiId, response }: { rfiId: string; response: string }) =>
      apiClient.post<RFI>(`/tbm/rfis/${rfiId}/respond`, { response }),
  });
}

// --- Clarifications / addenda (TBM-06) -----------------------------------
// Same gap as RFIs: no GET list endpoint, session-local only.

export function useCreateClarification(tenderId?: string) {
  return useMutation({
    mutationFn: (payload: { addendum_number: string; description: string; issued_at?: string; requires_reestimate?: boolean }) =>
      apiClient.post<Clarification>(`/tbm/tenders/${tenderId}/clarifications`, payload),
  });
}

export function useAcknowledgeClarification() {
  return useMutation({
    mutationFn: (clarificationId: string) =>
      apiClient.post<Clarification>(`/tbm/clarifications/${clarificationId}/acknowledge`, {}),
  });
}

// --- Approval workflow (TBM-07) ------------------------------------------

export function useApprovalSteps(tenderId?: string) {
  return useQuery({
    queryKey: ["tbm", "approval-steps", tenderId],
    queryFn: async () => (await apiClient.get<{ data: ApprovalStep[] }>(`/tbm/tenders/${tenderId}/approval-steps`)).data.data,
    enabled: !!tenderId,
  });
}

export function useInitiateApprovalWorkflow(tenderId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (steps: { role_required: string }[]) =>
      apiClient.post<Tender>(`/tbm/tenders/${tenderId}/approval-workflow/initiate`, { steps }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tbm", "tender", tenderId] });
      qc.invalidateQueries({ queryKey: ["tbm", "approval-steps", tenderId] });
    },
  });
}

export function useDecideApprovalStep(tenderId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ stepId, decision, comments }: { stepId: string; decision: "approved" | "rejected"; comments?: string }) =>
      apiClient.post<ApprovalStep>(`/tbm/approval-steps/${stepId}/decide`, { decision, comments }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tbm", "approval-steps", tenderId] });
      qc.invalidateQueries({ queryKey: ["tbm", "readiness", tenderId] });
    },
  });
}

export function useReopenForRevision(tenderId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (reason: string) => apiClient.post<Tender>(`/tbm/tenders/${tenderId}/reopen-for-revision`, { reason }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tbm", "tender", tenderId] });
      qc.invalidateQueries({ queryKey: ["tbm", "approval-steps", tenderId] });
    },
  });
}

// --- Checklist (TBM-08) ---------------------------------------------------
// Same gap as RFIs/Clarifications: no GET list endpoint for checklist
// items either, so this stays session-local -- the pre-existing
// disabled placeholder hook below documents the same finding.

export function useChecklistItems(_tenderId?: string) {
  return useQuery({
    queryKey: ["tbm", "checklist", _tenderId],
    // No list endpoint was built for checklist items directly, so this
    // reads them off the readiness call's blockers instead in the UI;
    // kept here as a placeholder for when a GET list route is added.
    queryFn: async (): Promise<TenderChecklistItem[]> => [],
    enabled: false,
  });
}

export function useAddChecklistItem(tenderId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { label: string; is_mandatory?: boolean }) =>
      apiClient.post<TenderChecklistItem>(`/tbm/tenders/${tenderId}/checklist-items`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tbm", "readiness", tenderId] }),
  });
}

export function useCompleteChecklistItem(tenderId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (itemId: string) => apiClient.post<TenderChecklistItem>(`/tbm/checklist-items/${itemId}/complete`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tbm", "readiness", tenderId] }),
  });
}

// --- Submission (TBM-09, TBM-12) ------------------------------------------

export function useSubmissionReadiness(tenderId?: string) {
  return useQuery({
    queryKey: ["tbm", "readiness", tenderId],
    queryFn: async () => (await apiClient.get<SubmissionReadiness>(`/tbm/tenders/${tenderId}/submission-readiness`)).data,
    enabled: !!tenderId,
  });
}

export function useSubmitTender(tenderId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { method: string; submitted_at: string }) =>
      apiClient.post(`/tbm/tenders/${tenderId}/submit`, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tbm", "tender", tenderId] });
      qc.invalidateQueries({ queryKey: ["tbm", "readiness", tenderId] });
    },
  });
}

// --- Win/Loss outcome (TBM-10) --------------------------------------------

export function useRecordTenderOutcome(tenderId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { outcome: "won" | "lost"; winning_price?: string; competitor_id?: string; reason_code?: string }) =>
      apiClient.post<{ tender_status: string; win_loss_record_id: string }>(`/tbm/tenders/${tenderId}/outcome`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tbm", "tender", tenderId] }),
  });
}

// --- Joint Venture apportionment (TBM-11) ---------------------------------

export function useJVPartners(tenderId?: string) {
  return useQuery({
    queryKey: ["tbm", "jv-partners", tenderId],
    queryFn: async () => (await apiClient.get<{ data: JVPartner[] }>(`/tbm/tenders/${tenderId}/jv-partners`)).data.data,
    enabled: !!tenderId,
  });
}

export function useAddJVPartner(tenderId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { partner_name: string; scope_share_pct: string; financial_share_pct: string }) =>
      apiClient.post<JVPartner>(`/tbm/tenders/${tenderId}/jv-partners`, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tbm", "jv-partners", tenderId] });
      qc.invalidateQueries({ queryKey: ["tbm", "tender", tenderId] });
    },
  });
}
