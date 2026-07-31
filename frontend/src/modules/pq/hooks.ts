import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../api/client";

export function useStockpiles() {
  return useQuery({
    queryKey: ["pq", "stockpiles"],
    queryFn: async () => (await apiClient.get("/pq/stockpiles")).data.data,
  });
}

export function useCreateStockpile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { material_type: string; location?: string; quantity?: string }) =>
      apiClient.post("/pq/stockpiles", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pq", "stockpiles"] }),
  });
}

export function useReconcileStockpile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ stockpileId, physical_quantity }: { stockpileId: string; physical_quantity: string }) =>
      apiClient.post(`/pq/stockpiles/${stockpileId}/reconcile`, { physical_quantity }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pq", "stockpiles"] }),
  });
}

export function useExplosivesRegister() {
  return useQuery({
    queryKey: ["pq", "explosives-register"],
    queryFn: async () => (await apiClient.get("/pq/explosives-register")).data.data,
  });
}

export function useCreateExplosivesEntry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { entry_type: string; material_type: string; quantity: string }) =>
      apiClient.post("/pq/explosives-register", payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pq", "explosives-register"] });
      qc.invalidateQueries({ queryKey: ["pq", "explosives-balance"] });
    },
  });
}

export function useAddExplosivesCorrection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ entryId, reason, corrected_quantity }: { entryId: string; reason: string; corrected_quantity?: string }) =>
      apiClient.post(`/pq/explosives-register/${entryId}/corrections`, { reason, corrected_quantity }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pq", "explosives-register"] }),
  });
}

export function useExplosivesBalance() {
  return useQuery({
    queryKey: ["pq", "explosives-balance"],
    queryFn: async () => (await apiClient.get("/pq/explosives-register/balance")).data,
  });
}
