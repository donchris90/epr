import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../api/client";

export function useAtRiskProjectsTool(threshold?: string) {
  return useQuery({
    queryKey: ["ai", "tools", "at-risk-projects", threshold],
    queryFn: async () => (await apiClient.get("/ai/tools/at-risk-projects", { params: { threshold } })).data.data,
  });
}

export function useIdleEquipmentTool(periodStart?: string, periodEnd?: string) {
  return useQuery({
    queryKey: ["ai", "tools", "idle-equipment", periodStart, periodEnd],
    queryFn: async () =>
      (await apiClient.get("/ai/tools/idle-equipment", { params: { period_start: periodStart, period_end: periodEnd } })).data.data,
    enabled: !!periodStart && !!periodEnd,
  });
}

export function useQueryLogs() {
  return useQuery({
    queryKey: ["ai", "query-logs"],
    queryFn: async () => (await apiClient.get("/ai/query-logs")).data.data,
  });
}

export function useCreateExtractionJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { extraction_type: string; extracted_data: Record<string, any>; confidence_scores?: Record<string, number> }) =>
      apiClient.post("/ai/extraction-jobs", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ai", "extraction-jobs"] }),
  });
}

export function useReviewExtractionJob() {
  return useMutation({
    mutationFn: ({ jobId, corrected_data }: { jobId: string; corrected_data?: Record<string, any> }) =>
      apiClient.post(`/ai/extraction-jobs/${jobId}/review`, { corrected_data }),
  });
}

export function useCommitExtractionToBOQ() {
  return useMutation({
    mutationFn: ({ jobId, estimate_version_id }: { jobId: string; estimate_version_id: string }) =>
      apiClient.post(`/ai/extraction-jobs/${jobId}/commit-to-boq`, { estimate_version_id }),
  });
}
