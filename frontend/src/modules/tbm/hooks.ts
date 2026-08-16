import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../api/client";

export function useTenders() {
  return useQuery({
    queryKey: ["tbm", "tenders"],
    queryFn: async () => (await apiClient.get("/tbm/tenders")).data.data,
  });
}

export function useTender(tenderId?: string) {
  return useQuery({
    queryKey: ["tbm", "tender", tenderId],
    queryFn: async () => (await apiClient.get(`/tbm/tenders/${tenderId}`)).data,
    enabled: !!tenderId,
  });
}

export function useCreateTender() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { opportunity_id: string; reference_number: string }) =>
      apiClient.post("/tbm/tenders", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tbm", "tenders"] }),
  });
}

export function useBOQItems(tenderId?: string) {
  return useQuery({
    queryKey: ["tbm", "boq-items", tenderId],
    queryFn: async () => (await apiClient.get(`/tbm/tenders/${tenderId}/boq-items`)).data.data,
    enabled: !!tenderId,
  });
}

export function useAddBOQItem(tenderId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { description: string; unit?: string; quantity?: string }) =>
      apiClient.post(`/tbm/tenders/${tenderId}/boq-items`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tbm", "boq-items", tenderId] }),
  });
}

export function useChecklistItems(tenderId?: string) {
  return useQuery({
    queryKey: ["tbm", "checklist", tenderId],
    // No list endpoint was built for checklist items directly, so this
    // reads them off the readiness call's blockers instead in the UI;
    // kept here as a placeholder for when a GET list route is added.
    queryFn: async () => [],
    enabled: false,
  });
}

export function useAddChecklistItem(tenderId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { label: string; is_mandatory?: boolean }) =>
      apiClient.post(`/tbm/tenders/${tenderId}/checklist-items`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tbm", "readiness", tenderId] }),
  });
}

export function useSubmissionReadiness(tenderId?: string) {
  return useQuery({
    queryKey: ["tbm", "readiness", tenderId],
    queryFn: async () => (await apiClient.get(`/tbm/tenders/${tenderId}/submission-readiness`)).data,
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
