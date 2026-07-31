import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../api/client";

export function useEVMSnapshots(projectId?: string) {
  return useQuery({
    queryKey: ["pc", "evm-snapshots", projectId],
    queryFn: async () => (await apiClient.get("/pc/evm-snapshots", { params: { project_id: projectId } })).data.data,
    enabled: !!projectId,
  });
}

export function useCreateEVMSnapshot() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      project_id: string;
      period_end: string;
      planned_value: string;
      earned_value: string;
      actual_cost: string;
      budget_at_completion: string;
    }) => apiClient.post("/pc/evm-snapshots", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pc", "evm-snapshots"] }),
  });
}

export function useAtRiskProjects(threshold?: string) {
  return useQuery({
    queryKey: ["pc", "at-risk-projects", threshold],
    queryFn: async () => (await apiClient.get("/pc/at-risk-projects", { params: { threshold } })).data.data,
  });
}

export function useGenerateForecast() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ snapshotId, method }: { snapshotId: string; method?: string }) =>
      apiClient.post(`/pc/evm-snapshots/${snapshotId}/forecast`, { method }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pc"] }),
  });
}

export function useRiskRegister(projectId?: string) {
  return useQuery({
    queryKey: ["pc", "risk-register", projectId],
    queryFn: async () => (await apiClient.get("/pc/risk-register", { params: { project_id: projectId } })).data.data,
    enabled: !!projectId,
  });
}

export function useCreateRiskEntry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { project_id: string; description: string; probability: string; impact_value: string }) =>
      apiClient.post("/pc/risk-register", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pc", "risk-register"] }),
  });
}
