import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../api/client";

export function useEquipmentList() {
  return useQuery({
    queryKey: ["eqp", "equipment"],
    queryFn: async () => (await apiClient.get("/eqp/equipment")).data.data,
  });
}

export function useIdleEquipment() {
  return useQuery({
    queryKey: ["eqp", "equipment", "idle"],
    queryFn: async () => (await apiClient.get("/eqp/equipment/idle")).data.data,
  });
}

export function useEquipment(equipmentId?: string) {
  return useQuery({
    queryKey: ["eqp", "equipment", "detail", equipmentId],
    queryFn: async () => (await apiClient.get(`/eqp/equipment/${equipmentId}`)).data,
    enabled: !!equipmentId,
  });
}

export function useCreateEquipment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { name: string; make?: string; model?: string; ownership_type?: string; acquisition_cost?: string }) =>
      apiClient.post("/eqp/equipment", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["eqp", "equipment"] }),
  });
}

export function useMaintenanceRecords(equipmentId?: string) {
  return useQuery({
    queryKey: ["eqp", "equipment", equipmentId, "maintenance"],
    queryFn: async () => (await apiClient.get(`/eqp/equipment/${equipmentId}/maintenance-records`)).data.data,
    enabled: !!equipmentId,
  });
}

export function useCreateMaintenanceRecord(equipmentId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { maintenance_type?: string; description?: string; scheduled_date?: string }) =>
      apiClient.post(`/eqp/equipment/${equipmentId}/maintenance-records`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["eqp", "equipment", equipmentId, "maintenance"] }),
  });
}

export function useOverdueMaintenance() {
  return useQuery({
    queryKey: ["eqp", "maintenance-records", "overdue"],
    queryFn: async () => (await apiClient.get("/eqp/maintenance-records/overdue")).data.data,
  });
}

export function useEquipmentAvailability(equipmentId?: string) {
  return useQuery({
    queryKey: ["eqp", "equipment", equipmentId, "availability"],
    queryFn: async () => (await apiClient.get(`/eqp/equipment/${equipmentId}/availability`)).data,
    enabled: !!equipmentId,
  });
}

export function useEquipmentCostPerHour(equipmentId?: string) {
  return useQuery({
    queryKey: ["eqp", "equipment", equipmentId, "cost-per-hour"],
    queryFn: async () => (await apiClient.get(`/eqp/equipment/${equipmentId}/cost-per-hour`)).data,
    enabled: !!equipmentId,
  });
}

export function useAddUtilizationRecord(equipmentId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { record_date: string; hours_scheduled?: string; hours_operated: string }) =>
      apiClient.post(`/eqp/equipment/${equipmentId}/utilization-records`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["eqp", "equipment", equipmentId] }),
  });
}
