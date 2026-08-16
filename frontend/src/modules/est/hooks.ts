import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../api/client";

export function useEstimateVersions(tenderId?: string) {
  return useQuery({
    queryKey: ["est", "versions", tenderId],
    queryFn: async () => (await apiClient.get(`/est/tenders/${tenderId}/estimate-versions`)).data.data,
    enabled: !!tenderId,
  });
}

export function useCreateEstimateVersion(tenderId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (label?: string) => apiClient.post("/est/estimate-versions", { tender_id: tenderId, label }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["est", "versions", tenderId] }),
  });
}

export function useSubmitEstimateVersion(versionId?: string, tenderId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.post(`/est/estimate-versions/${versionId}/submit`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["est", "versions", tenderId] }),
  });
}

export function useBOQItems(versionId?: string) {
  return useQuery({
    queryKey: ["est", "boq-items", versionId],
    queryFn: async () => (await apiClient.get(`/est/estimate-versions/${versionId}/boq-items`)).data.data,
    enabled: !!versionId,
  });
}

export function useAddBOQItem(versionId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { description: string; unit?: string; quantity?: string }) =>
      apiClient.post(`/est/estimate-versions/${versionId}/boq-items`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["est", "boq-items", versionId] }),
  });
}

export function useSaveRateAnalysis(versionId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      boqItemId,
      lines,
      markupPct,
    }: {
      boqItemId: string;
      lines: { component_type: string; description: string; quantity_per_unit: string; unit_cost: string }[];
      markupPct: string;
    }) => apiClient.put(`/est/boq-items/${boqItemId}/rate-analysis`, { lines, markup_pct: markupPct }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["est", "boq-items", versionId] }),
  });
}

export function useTenderPrice(versionId?: string) {
  return useQuery({
    queryKey: ["est", "tender-price", versionId],
    queryFn: async () => (await apiClient.get(`/est/estimate-versions/${versionId}/tender-price`)).data,
    enabled: !!versionId,
  });
}

export function useGenerateCBS(versionId?: string) {
  return useMutation({
    mutationFn: () => apiClient.post(`/est/estimate-versions/${versionId}/generate-cbs`, {}),
  });
}
