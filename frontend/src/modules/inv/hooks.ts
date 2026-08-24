import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../api/client";

/** Real types matching backend/app/modules/inv/schemas.py exactly --
 * checked directly against the actual schemas before writing these. */
export interface Warehouse {
  id: string;
  name: string;
  warehouse_type: "central_yard" | "site_store" | "quarry";
  project_id: string | null;
  location: string | null;
}

export interface MaterialItem {
  id: string;
  code: string;
  description: string;
  unit: string | null;
  is_batch_tracked: boolean;
  is_serial_tracked: boolean;
}

export interface StockItem {
  id: string;
  warehouse_id: string;
  material_item_id: string;
  quantity_on_hand: string;
  average_unit_cost: string;
}

export interface StockTransfer {
  id: string;
  from_warehouse_id: string;
  to_warehouse_id: string;
  material_item_id: string;
  quantity: string;
  status: string;
}

export interface StockReservation {
  id: string;
  warehouse_id: string;
  material_item_id: string;
  project_id: string | null;
  activity_id: string | null;
  quantity: string;
  status: string;
}

export interface ReorderLevel {
  id: string;
  warehouse_id: string;
  material_item_id: string;
  reorder_point: string;
  reorder_quantity: string;
  auto_create_pr: boolean;
}

export interface ItemCode {
  id: string;
  material_item_id: string;
  code_type: string;
  code_value: string;
}

export interface BatchNumber {
  id: string;
  material_item_id: string;
  warehouse_id: string;
  batch_number: string;
  manufactured_date: string | null;
  expiry_date: string | null;
  quality_cert_document_id: string | null;
  quantity_remaining: string;
}

export interface SerialNumber {
  id: string;
  material_item_id: string;
  serial_number: string;
  current_warehouse_id: string | null;
  status: string;
}

export interface WasteRecord {
  id: string;
  warehouse_id: string;
  material_item_id: string;
  quantity: string;
  cause_classification: "breakage" | "theft" | "spoilage" | "over_order";
  valued_cost: string;
}

export interface MaterialReturn {
  id: string;
  material_item_id: string;
  quantity: string;
  return_type: "site_to_yard" | "to_vendor";
  status: string;
}

export interface StockCountLine {
  id: string;
  material_item_id: string;
  system_quantity: string;
  counted_quantity: string | null;
  variance: string | null;
}

export interface StockCount {
  id: string;
  warehouse_id: string;
  count_type: string;
  status: string;
  lines: StockCountLine[];
}

// --- Warehouses & material items (INV-01) -----------------------------------

export function useWarehouses() {
  return useQuery({
    queryKey: ["inv", "warehouses"],
    queryFn: async (): Promise<Warehouse[]> => (await apiClient.get("/inv/warehouses")).data.data,
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
    queryFn: async (): Promise<StockItem[]> => (await apiClient.get(`/inv/warehouses/${warehouseId}/stock`)).data.data,
    enabled: !!warehouseId,
  });
}

export function useMaterialItems() {
  return useQuery({
    queryKey: ["inv", "material-items"],
    queryFn: async (): Promise<MaterialItem[]> => (await apiClient.get("/inv/material-items")).data.data,
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
    queryFn: async (): Promise<StockItem[]> => (await apiClient.get("/inv/stock/available", { params: { warehouse_id: warehouseId } })).data.data,
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

// --- Reservations (INV-03) ----------------------------------------------------

export function useReservations(filters: { warehouseId?: string; status?: string } = {}) {
  return useQuery({
    queryKey: ["inv", "reservations", filters],
    queryFn: async (): Promise<StockReservation[]> =>
      (await apiClient.get("/inv/stock/reservations", { params: { warehouse_id: filters.warehouseId, status: filters.status } })).data.data,
  });
}

export function useCreateReservation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { warehouse_id: string; material_item_id: string; quantity: string; project_id?: string; activity_id?: string }) =>
      apiClient.post("/inv/stock/reservations", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["inv", "reservations"] }),
  });
}

export function useReleaseReservation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (reservationId: string) => apiClient.post(`/inv/stock/reservations/${reservationId}/release`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["inv", "reservations"] }),
  });
}

// --- Stock transfers (INV-02) -------------------------------------------------

export function useStockTransfers(status?: string) {
  return useQuery({
    queryKey: ["inv", "stock-transfers", status],
    queryFn: async (): Promise<StockTransfer[]> => (await apiClient.get("/inv/stock-transfers", { params: { status } })).data.data,
  });
}

export function useCreateTransfer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { from_warehouse_id: string; to_warehouse_id: string; material_item_id: string; quantity: string }) =>
      apiClient.post("/inv/stock-transfers", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["inv", "stock-transfers"] }),
  });
}

export function useConfirmTransferReceipt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (transferId: string) => apiClient.post(`/inv/stock-transfers/${transferId}/confirm-receipt`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["inv", "stock-transfers"] }),
  });
}

// --- Reorder levels (INV-05) --------------------------------------------------

export function useReorderLevelsBelowThreshold() {
  return useQuery({
    queryKey: ["inv", "reorder-levels", "below-threshold"],
    queryFn: async (): Promise<{ reorder_level: ReorderLevel; available_quantity: string }[]> =>
      (await apiClient.get("/inv/reorder-levels/below-threshold")).data.data,
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

// --- Item codes, batch numbers, serial numbers (INV-05, 06, 07) --------------

export function useItemCodes(materialItemId?: string) {
  return useQuery({
    queryKey: ["inv", "item-codes", materialItemId],
    queryFn: async (): Promise<ItemCode[]> => (await apiClient.get("/inv/item-codes", { params: { material_item_id: materialItemId } })).data.data,
    enabled: !!materialItemId,
  });
}

export function useCreateItemCode() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { material_item_id: string; code_type: string; code_value: string }) => apiClient.post("/inv/item-codes", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["inv", "item-codes"] }),
  });
}

export function useBatchNumbers(filters: { materialItemId?: string; warehouseId?: string } = {}) {
  return useQuery({
    queryKey: ["inv", "batch-numbers", filters],
    queryFn: async (): Promise<BatchNumber[]> =>
      (await apiClient.get("/inv/batch-numbers", { params: { material_item_id: filters.materialItemId, warehouse_id: filters.warehouseId } })).data.data,
  });
}

export function useCreateBatchNumber() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { material_item_id: string; warehouse_id: string; batch_number: string; manufactured_date?: string; expiry_date?: string }) =>
      apiClient.post("/inv/batch-numbers", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["inv", "batch-numbers"] }),
  });
}

export function useExpiringBatches() {
  return useQuery({
    queryKey: ["inv", "batch-numbers", "expiring"],
    queryFn: async (): Promise<BatchNumber[]> => (await apiClient.get("/inv/batch-numbers/expiring")).data.data,
  });
}

export function useSerialNumbers(filters: { materialItemId?: string; status?: string } = {}) {
  return useQuery({
    queryKey: ["inv", "serial-numbers", filters],
    queryFn: async (): Promise<SerialNumber[]> =>
      (await apiClient.get("/inv/serial-numbers", { params: { material_item_id: filters.materialItemId, status: filters.status } })).data.data,
  });
}

export function useCreateSerialNumber() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { material_item_id: string; serial_number: string; current_warehouse_id?: string }) =>
      apiClient.post("/inv/serial-numbers", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["inv", "serial-numbers"] }),
  });
}

// --- Waste records (INV-08) ---------------------------------------------------

export function useWasteRecords(warehouseId?: string) {
  return useQuery({
    queryKey: ["inv", "waste-records", warehouseId],
    queryFn: async (): Promise<WasteRecord[]> => (await apiClient.get("/inv/waste-records", { params: { warehouse_id: warehouseId } })).data.data,
  });
}

export function useRecordWaste() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { warehouse_id: string; material_item_id: string; quantity: string; cause_classification: string; project_id?: string; notes?: string }) =>
      apiClient.post("/inv/waste-records", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["inv"] }),
  });
}

// --- Material returns (INV-09) ------------------------------------------------

export function useMaterialReturns(returnType?: string) {
  return useQuery({
    queryKey: ["inv", "material-returns", returnType],
    queryFn: async (): Promise<MaterialReturn[]> => (await apiClient.get("/inv/material-returns", { params: { return_type: returnType } })).data.data,
  });
}

export function useReturnToYard() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { material_item_id: string; source_warehouse_id: string; destination_warehouse_id: string; quantity: string; condition?: string }) =>
      apiClient.post("/inv/material-returns/to-yard", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["inv", "material-returns"] }),
  });
}

export function useReturnToVendor() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { material_item_id: string; source_warehouse_id: string; vendor_id: string; quantity: string; condition?: string; credit_note_reference?: string }) =>
      apiClient.post("/inv/material-returns/to-vendor", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["inv", "material-returns"] }),
  });
}

// --- Stock counts (INV-10) ----------------------------------------------------

export function useStockCounts(filters: { warehouseId?: string; status?: string } = {}) {
  return useQuery({
    queryKey: ["inv", "stock-counts", filters],
    queryFn: async (): Promise<StockCount[]> =>
      (await apiClient.get("/inv/stock-counts", { params: { warehouse_id: filters.warehouseId, status: filters.status } })).data.data,
  });
}

export function useStockCount(countId?: string) {
  return useQuery({
    queryKey: ["inv", "stock-counts", "detail", countId],
    queryFn: async (): Promise<StockCount> => (await apiClient.get(`/inv/stock-counts/${countId}`)).data,
    enabled: !!countId,
  });
}

export function useStartStockCount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { warehouse_id: string; count_type: string; material_item_ids: string[] }) =>
      apiClient.post("/inv/stock-counts", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["inv", "stock-counts"] }),
  });
}

export function useRecordCountLine(countId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ lineId, counted_quantity }: { lineId: string; counted_quantity: string }) =>
      apiClient.post(`/inv/stock-count-lines/${lineId}/record`, { counted_quantity }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["inv", "stock-counts", "detail", countId] }),
  });
}

export function useCompleteStockCount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (countId: string) => apiClient.post(`/inv/stock-counts/${countId}/complete`),
    onSuccess: (_data, countId) => {
      qc.invalidateQueries({ queryKey: ["inv", "stock-counts"] });
      qc.invalidateQueries({ queryKey: ["inv", "stock-counts", "detail", countId] });
    },
  });
}

export function useApplyStockCountAdjustment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (countId: string) => apiClient.post(`/inv/stock-counts/${countId}/apply-adjustment`),
    onSuccess: (_data, countId) => {
      qc.invalidateQueries({ queryKey: ["inv"] });
      qc.invalidateQueries({ queryKey: ["inv", "stock-counts", "detail", countId] });
    },
  });
}
