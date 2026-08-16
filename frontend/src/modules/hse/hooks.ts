import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../api/client";

export function useRiskAssessments() {
  return useQuery({
    queryKey: ["hse", "risk-assessments"],
    queryFn: async () => (await apiClient.get("/hse/risk-assessments")).data.data,
  });
}

export function useCreateRiskAssessment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { activity_or_area: string; description?: string; risk_level?: string; valid_until?: string }) =>
      apiClient.post("/hse/risk-assessments", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hse", "risk-assessments"] }),
  });
}

export function usePermits() {
  return useQuery({
    queryKey: ["hse", "permits"],
    queryFn: async () => (await apiClient.get("/hse/permits")).data.data,
  });
}

export function useIssuePermit() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { project_id: string; permit_type: string; risk_assessment_id?: string; workers_training_current?: boolean }) =>
      apiClient.post("/hse/permits", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hse", "permits"] }),
  });
}

export function useActivatePermit() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (permitId: string) => apiClient.post(`/hse/permits/${permitId}/activate`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hse", "permits"] }),
  });
}

export function useClosePermit() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (permitId: string) => apiClient.post(`/hse/permits/${permitId}/close`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hse", "permits"] }),
  });
}

export function useIncidents() {
  return useQuery({
    queryKey: ["hse", "incidents"],
    queryFn: async () => (await apiClient.get("/hse/incidents")).data.data,
  });
}

export function useCreateIncident() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { classification: string; description: string; regulatory_reportable?: boolean }) =>
      apiClient.post("/hse/incidents", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hse", "incidents"] }),
  });
}

export function useCloseIncident() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (incidentId: string) => apiClient.post(`/hse/incidents/${incidentId}/close`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hse", "incidents"] }),
  });
}

export function useCreateNearMiss() {
  return useMutation({
    mutationFn: (payload: { classification: string; description: string }) => apiClient.post("/hse/near-misses", payload),
  });
}

export function useSafetyIndicators(projectId?: string) {
  return useQuery({
    queryKey: ["hse", "safety-indicators", projectId],
    queryFn: async () => (await apiClient.get("/hse/safety-indicators", { params: { project_id: projectId } })).data,
    enabled: !!projectId,
  });
}
