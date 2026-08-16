import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../api/client";

export function useAssets() {
  return useQuery({
    queryKey: ["ast", "assets"],
    queryFn: async () => (await apiClient.get("/ast/assets")).data.data,
  });
}

export function useAsset(assetId?: string) {
  return useQuery({
    queryKey: ["ast", "assets", assetId],
    queryFn: async () => (await apiClient.get(`/ast/assets/${assetId}`)).data,
    enabled: !!assetId,
  });
}

export function useCreateAsset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { name: string; asset_category: string; project_id?: string }) => apiClient.post("/ast/assets", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ast", "assets"] }),
  });
}

export function useCreateDLP(assetId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { dlp_start?: string; dlp_end?: string }) => apiClient.post(`/ast/assets/${assetId}/dlp`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ast"] }),
  });
}

export function useAddDefect() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ dlpId, description }: { dlpId: string; description: string }) =>
      apiClient.post(`/ast/dlp/${dlpId}/defects`, { description }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ast"] }),
  });
}

export function useResolveDefect() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (defectId: string) => apiClient.post(`/ast/defects/${defectId}/resolve`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ast"] }),
  });
}

export function useVerifyDefect() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (defectId: string) => apiClient.post(`/ast/defects/${defectId}/verify`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ast"] }),
  });
}

export function useReleaseRetention() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (dlpId: string) => apiClient.post(`/ast/dlp/${dlpId}/release-retention`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ast"] }),
  });
}
