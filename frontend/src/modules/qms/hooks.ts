import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../api/client";

/** Real types matching backend/app/modules/qms/schemas.py exactly --
 * checked directly against the actual schemas before writing these. */
export interface InspectionTestPlan {
  id: string;
  activity_type: string;
  title: string;
  description: string | null;
}

export interface ITPHoldPoint {
  id: string;
  itp_id: string;
  sequence_order: number;
  description: string;
  is_mandatory_hold: boolean;
  status: string;
}

export interface MaterialApproval {
  id: string;
  material_item_id: string | null;
  submittal_reference: string;
  status: "submitted" | "approved" | "rejected";
  review_notes: string | null;
}

export interface LabResult {
  id: string;
  pour_or_lot_reference: string | null;
  test_type: "concrete_cube_strength" | "compaction_density" | "asphalt_extraction" | "other";
  sample_reference: string | null;
  tested_at: string | null;
  result_value: string | null;
  unit: string | null;
  acceptance_threshold: string | null;
  pass_fail: boolean | null;
  lab_name: string | null;
}

export interface NCR {
  id: string;
  project_id: string | null;
  description: string;
  root_cause: string | null;
  disposition: string | null;
  status: string;
  closed_at: string | null;
}

export interface CorrectiveAction {
  id: string;
  ncr_id: string | null;
  source: "ncr" | "audit" | "incident";
  description: string;
  status: string;
  verified_by: string | null;
  verified_at: string | null;
}

export interface PunchListItem {
  id: string;
  project_id: string;
  area_building_section: string | null;
  description: string;
  status: string;
}

export interface SnagListItem {
  id: string;
  project_id: string;
  area_building_section: string | null;
  description: string;
  status: string;
}

// --- ITPs & hold points (QMS-01) ----------------------------------------------

export function useITPs() {
  return useQuery({
    queryKey: ["qms", "itps"],
    queryFn: async (): Promise<InspectionTestPlan[]> => (await apiClient.get("/qms/itps")).data.data,
  });
}

export function useCreateITP() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { activity_type: string; title: string; description?: string }) => apiClient.post("/qms/itps", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["qms", "itps"] }),
  });
}

export function useHoldPoints(itpId?: string) {
  return useQuery({
    queryKey: ["qms", "itps", itpId, "hold-points"],
    queryFn: async (): Promise<ITPHoldPoint[]> => (await apiClient.get(`/qms/itps/${itpId}/hold-points`)).data.data,
    enabled: !!itpId,
  });
}

export function useAddHoldPoint(itpId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { sequence_order: number; description: string; is_mandatory_hold?: boolean }) =>
      apiClient.post(`/qms/itps/${itpId}/hold-points`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["qms", "itps", itpId, "hold-points"] }),
  });
}

export function useRecordHoldPointResult() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ holdPointId, passed }: { holdPointId: string; passed: boolean }) =>
      apiClient.post(`/qms/hold-points/${holdPointId}/record-result`, { passed }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["qms"] }),
  });
}

export function useApproveConcession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ holdPointId, reason }: { holdPointId: string; reason: string }) =>
      apiClient.post(`/qms/hold-points/${holdPointId}/approve-concession`, { reason }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["qms"] }),
  });
}

export function useCanProceed(holdPointId?: string) {
  return useQuery({
    queryKey: ["qms", "hold-points", holdPointId, "can-proceed"],
    queryFn: async (): Promise<{ can_proceed: boolean }> => (await apiClient.get(`/qms/hold-points/${holdPointId}/can-proceed`)).data,
    enabled: !!holdPointId,
  });
}

// --- Material approvals (QMS-02) ----------------------------------------------

export function useMaterialApprovals(status?: string) {
  return useQuery({
    queryKey: ["qms", "material-approvals", status],
    queryFn: async (): Promise<MaterialApproval[]> => (await apiClient.get("/qms/material-approvals", { params: { status } })).data.data,
  });
}

export function useCreateMaterialApproval() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { submittal_reference: string; material_item_id?: string }) => apiClient.post("/qms/material-approvals", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["qms", "material-approvals"] }),
  });
}

export function useDecideMaterialApproval() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ approvalId, decision, reviewNotes }: { approvalId: string; decision: "approved" | "rejected"; reviewNotes?: string }) =>
      apiClient.post(`/qms/material-approvals/${approvalId}/decide`, { decision, review_notes: reviewNotes }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["qms", "material-approvals"] }),
  });
}

// --- Lab results (QMS-03) -----------------------------------------------------

export function useLabResults(testType?: string) {
  return useQuery({
    queryKey: ["qms", "lab-results", testType],
    queryFn: async (): Promise<LabResult[]> => (await apiClient.get("/qms/lab-results", { params: { test_type: testType } })).data.data,
  });
}

export function useCreateLabResult() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { test_type: string; sample_reference?: string; tested_at?: string; result_value?: string; unit?: string; acceptance_threshold?: string; lab_name?: string }) =>
      apiClient.post("/qms/lab-results", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["qms", "lab-results"] }),
  });
}

export function useRecordLabResultOutcome() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ resultId, passFail }: { resultId: string; passFail: boolean }) =>
      apiClient.post(`/qms/lab-results/${resultId}/record-outcome`, { pass_fail: passFail }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["qms", "lab-results"] }),
  });
}

// --- NCRs (QMS-04) -------------------------------------------------------------

export function useNCRs() {
  return useQuery({
    queryKey: ["qms", "ncrs"],
    queryFn: async (): Promise<NCR[]> => (await apiClient.get("/qms/ncrs")).data.data,
  });
}

export function useCreateNCR() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { description: string; root_cause?: string; project_id?: string }) => apiClient.post("/qms/ncrs", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["qms", "ncrs"] }),
  });
}

export function useDispositionNCR() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ ncrId, disposition }: { ncrId: string; disposition: string }) =>
      apiClient.post(`/qms/ncrs/${ncrId}/disposition`, { disposition }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["qms", "ncrs"] }),
  });
}

export function useCloseNCR() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ncrId: string) => apiClient.post(`/qms/ncrs/${ncrId}/close`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["qms", "ncrs"] }),
  });
}

// --- Corrective actions (QMS-06) -----------------------------------------------

export function useCorrectiveActions(filters: { ncrId?: string; status?: string } = {}) {
  return useQuery({
    queryKey: ["qms", "corrective-actions", filters],
    queryFn: async (): Promise<CorrectiveAction[]> =>
      (await apiClient.get("/qms/corrective-actions", { params: { ncr_id: filters.ncrId, status: filters.status } })).data.data,
  });
}

/** Real bug fixed here: this hook previously sent `source_reference_id`,
 * a field that does not exist on the real backend schema (the real
 * field is `ncr_id`) -- every corrective action logged from the NCR
 * page was silently created unlinked to its NCR, which meant
 * close_ncr's own real business rule ("cannot close without a linked,
 * verified corrective action") could never be satisfied no matter
 * what the user did through the UI. */
export function useCreateCorrectiveAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { source: string; ncr_id?: string; description: string; owner_id?: string; due_date?: string }) =>
      apiClient.post("/qms/corrective-actions", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["qms"] }),
  });
}

export function useCompleteCorrectiveAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (actionId: string) => apiClient.post(`/qms/corrective-actions/${actionId}/complete`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["qms"] }),
  });
}

export function useVerifyCorrectiveAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (actionId: string) => apiClient.post(`/qms/corrective-actions/${actionId}/verify`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["qms"] }),
  });
}

// --- Punch lists (QMS-05) -------------------------------------------------------

export function usePunchListItems(filters: { projectId?: string; status?: string } = {}) {
  return useQuery({
    queryKey: ["qms", "punch-list-items", filters],
    queryFn: async (): Promise<PunchListItem[]> =>
      (await apiClient.get("/qms/punch-list-items", { params: { project_id: filters.projectId, status: filters.status } })).data.data,
  });
}

export function useCreatePunchListItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { project_id: string; description: string; area_building_section?: string }) =>
      apiClient.post("/qms/punch-list-items", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["qms", "punch-list-items"] }),
  });
}

export function useClosePunchListItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (itemId: string) => apiClient.post(`/qms/punch-list-items/${itemId}/close`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["qms", "punch-list-items"] }),
  });
}

// --- Snag lists (QMS-07) --------------------------------------------------------

export function useSnagListItems(filters: { projectId?: string; status?: string } = {}) {
  return useQuery({
    queryKey: ["qms", "snag-list-items", filters],
    queryFn: async (): Promise<SnagListItem[]> =>
      (await apiClient.get("/qms/snag-list-items", { params: { project_id: filters.projectId, status: filters.status } })).data.data,
  });
}

export function useCreateSnagListItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { project_id: string; description: string; area_building_section?: string }) =>
      apiClient.post("/qms/snag-list-items", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["qms", "snag-list-items"] }),
  });
}

export function useCloseSnagListItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (itemId: string) => apiClient.post(`/qms/snag-list-items/${itemId}/close`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["qms", "snag-list-items"] }),
  });
}

// --- Close-out tracking (QMS-08) -------------------------------------------------

export function useCloseoutReadiness(projectId?: string) {
  return useQuery({
    queryKey: ["qms", "closeout-readiness", projectId],
    queryFn: async () => (await apiClient.get("/qms/closeout-readiness", { params: { project_id: projectId } })).data,
    enabled: !!projectId,
  });
}
