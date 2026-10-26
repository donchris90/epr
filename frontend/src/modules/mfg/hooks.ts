import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../api/client";

/** Shapes match backend/app/modules/mfg/schemas.py. Decimals arrive as strings. */
export interface WorkCenter {
  id: string;
  code: string;
  name: string;
  hourly_rate: string;
  equipment_id: string | null;
  is_active: boolean;
}

export interface BomLine {
  id?: string;
  component_item_id: string;
  quantity: string;
  scrap_percent: string;
}

export interface Bom {
  id: string;
  code: string;
  name: string;
  product_item_id: string;
  output_quantity: string;
  is_active: boolean;
  lines: BomLine[];
}

export interface ProductionComponent {
  id: string;
  component_item_id: string;
  planned_quantity: string;
  consumed_quantity: string;
  valued_cost: string;
}

export type OrderStatus = "draft" | "released" | "in_progress" | "done" | "cancelled";

export interface ProductionOrder {
  id: string;
  number: string;
  bom_id: string;
  product_item_id: string;
  warehouse_id: string;
  work_center_id: string | null;
  status: OrderStatus;
  quantity_planned: string;
  quantity_produced: string;
  quantity_scrapped: string;
  labour_hours: string;
  fuel_litres: string;
  material_cost: string;
  labour_cost: string;
  fuel_cost: string;
  total_cost: string;
  unit_cost: string;
  batch_id: string | null;
  components: ProductionComponent[];
}

export interface Availability {
  component_item_id: string;
  code: string;
  required: string;
  available: string;
  short: string;
}

export interface Variance {
  component_item_id: string;
  planned: string;
  consumed: string;
  variance: string;
  valued_cost: string;
}

export function useWorkCenters() {
  return useQuery({
    queryKey: ["mfg", "work-centers"],
    queryFn: async (): Promise<WorkCenter[]> => (await apiClient.get("/mfg/work-centers")).data.data,
  });
}

export function useCreateWorkCenter() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { code: string; name: string; hourly_rate: string }) => apiClient.post("/mfg/work-centers", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["mfg", "work-centers"] }),
  });
}

export function useBoms() {
  return useQuery({
    queryKey: ["mfg", "boms"],
    queryFn: async (): Promise<Bom[]> => (await apiClient.get("/mfg/boms")).data.data,
  });
}

export function useCreateBom() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      code: string;
      name: string;
      product_item_id: string;
      output_quantity: string;
      lines: { component_item_id: string; quantity: string; scrap_percent: string }[];
    }) => apiClient.post("/mfg/boms", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["mfg", "boms"] }),
  });
}

export function useProductionOrders() {
  return useQuery({
    queryKey: ["mfg", "orders"],
    queryFn: async (): Promise<ProductionOrder[]> => (await apiClient.get("/mfg/production-orders")).data.data,
  });
}

export function useCreateOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { bom_id: string; quantity: string; warehouse_id: string; work_center_id?: string | null }) =>
      apiClient.post("/mfg/production-orders", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["mfg", "orders"] }),
  });
}

export function useOrderAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action }: { id: string; action: "release" | "start" | "cancel" }) =>
      apiClient.post(`/mfg/production-orders/${id}/${action}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["mfg", "orders"] }),
  });
}

export interface CompletePayload {
  quantity_produced: string;
  quantity_scrapped?: string;
  labour_hours?: string;
  fuel_litres?: string;
  fuel_unit_cost?: string | null;
  batch_number?: string | null;
  expiry_date?: string | null;
  quarantine?: boolean;
}

export function useCompleteOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: CompletePayload & { id: string }) => apiClient.post(`/mfg/production-orders/${id}/complete`, payload),
    // Completing moves stock, so the inventory and fuel views are stale too.
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mfg"] });
      qc.invalidateQueries({ queryKey: ["inv"] });
      qc.invalidateQueries({ queryKey: ["fuel"] });
    },
  });
}

export function useAvailability(orderId: string | null) {
  return useQuery({
    queryKey: ["mfg", "availability", orderId],
    enabled: !!orderId,
    queryFn: async (): Promise<Availability[]> => (await apiClient.get(`/mfg/production-orders/${orderId}/availability`)).data.data,
  });
}

export function useVariances(orderId: string | null) {
  return useQuery({
    queryKey: ["mfg", "variances", orderId],
    enabled: !!orderId,
    queryFn: async (): Promise<Variance[]> => (await apiClient.get(`/mfg/production-orders/${orderId}/variances`)).data.data,
  });
}
