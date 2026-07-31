import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../api/client";

export function useSyncStatus() {
  return useQuery({
    queryKey: ["mfa", "sync-status"],
    queryFn: async () => (await apiClient.get("/mfa/sync-status")).data,
  });
}

export function useConflicts(status?: string) {
  return useQuery({
    queryKey: ["mfa", "conflicts", status],
    queryFn: async () => (await apiClient.get("/mfa/conflicts", { params: { status } })).data.data,
  });
}

export function useResolveConflict() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ conflictId, resolution }: { conflictId: string; resolution: Record<string, string> }) =>
      apiClient.post(`/mfa/conflicts/${conflictId}/resolve`, { resolution }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["mfa", "conflicts"] }),
  });
}
