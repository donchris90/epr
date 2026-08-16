import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../api/client";

export function useITPs() {
  return useQuery({
    queryKey: ["qms", "itps"],
    queryFn: async () => (await apiClient.get("/qms/itps")).data.data,
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
    queryFn: async () => (await apiClient.get(`/qms/itps/${itpId}/hold-points`)).data.data,
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

export function useNCRs() {
  return useQuery({
    queryKey: ["qms", "ncrs"],
    queryFn: async () => (await apiClient.get("/qms/ncrs")).data.data,
  });
}

export function useCreateNCR() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { description: string; root_cause?: string }) => apiClient.post("/qms/ncrs", payload),
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

export function useCreateCorrectiveAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { source: string; source_reference_id: string; description: string }) =>
      apiClient.post("/qms/corrective-actions", payload),
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

export function useCloseoutReadiness(projectId?: string) {
  return useQuery({
    queryKey: ["qms", "closeout-readiness", projectId],
    queryFn: async () => (await apiClient.get("/qms/closeout-readiness", { params: { project_id: projectId } })).data,
    enabled: !!projectId,
  });
}
