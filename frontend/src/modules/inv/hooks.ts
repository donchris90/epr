import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../api/client";

// --- Warehouses & material items (INV-01) -----------------------------------

export function useWarehouses() {
  return useQuery({
    queryKey: ["inv", "warehouses"],
    queryFn: async () => (await apiClient.get("/inv/warehouses")).data.data,
  });
}

export function useCreateWarehouse() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { name: string; warehouse_type: string; project_id?: string; location?: string }) =>
      apiClient.post("/inv/warehouses", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["inv", "warehouses"] }),
  });
}

export function useWarehouseStock(warehouseId?: string) {
  return useQuery({
    queryKey: ["inv", "warehouses", warehouseId, "stock"],
    queryFn: async () => (await apiClient.get(`/inv/warehouses/${warehouseId}/stock`)).data.data,
    enabled: !!warehouseId,
  });
}

export function useMaterialItems() {
  return useQuery({
    queryKey: ["inv", "material-items"],
    queryFn: async () => (await apiClient.get("/inv/material-items")).data.data,
  });
}

export function useCreateMaterialItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { code: string; description: string; unit?: string; is_batch_tracked?: boolean; is_serial_tracked?: boolean }) =>
      apiClient.post("/inv/material-items", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["inv", "material-items"] }),
  });
}

// --- Stock movements (INV-02, INV-03) ----------------------------------------

export function useAvailableStock(warehouseId?: string) {
  return useQuery({
    queryKey: ["inv", "stock", "available", warehouseId],
    queryFn: async () => (await apiClient.get("/inv/stock/available", { params: { warehouse_id: warehouseId } })).data.data,
    enabled: !!warehouseId,
  });
}

export function useReceiveStock() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { warehouse_id: string; material_item_id: string; quantity: string; unit_cost: string }) =>
      apiClient.post("/inv/stock/receive", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["inv"] }),
  });
}

export function useIssueStock() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { warehouse_id: string; material_item_id: string; quantity: string }) =>
      apiClient.post("/inv/stock/issue", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["inv"] }),
  });
}

// --- Reorder levels (INV-05) --------------------------------------------------

export function useReorderLevelsBelowThreshold() {
  return useQuery({
    queryKey: ["inv", "reorder-levels", "below-threshold"],
    queryFn: async () => (await apiClient.get("/inv/reorder-levels/below-threshold")).data.data,
  });
}

export function useCreateReorderLevel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { warehouse_id: string; material_item_id: string; reorder_point: string; reorder_quantity: string; auto_create_pr?: boolean }) =>
      apiClient.post("/inv/reorder-levels", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["inv", "reorder-levels"] }),
  });
}

// --- Batch numbers expiring (INV-08) ------------------------------------------

export function useExpiringBatches() {
  return useQuery({
    queryKey: ["inv", "batch-numbers", "expiring"],
    queryFn: async () => (await apiClient.get("/inv/batch-numbers/expiring")).data.data,
  });
}
