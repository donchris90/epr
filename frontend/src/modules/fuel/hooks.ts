import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../api/client";

export function useTanks() {
  return useQuery({
    queryKey: ["fuel", "tanks"],
    queryFn: async () => (await apiClient.get("/fuel/tanks")).data.data,
  });
}

export function useCreateTank() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { name: string; tank_type: string; capacity_litres?: string }) =>
      apiClient.post("/fuel/tanks", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["fuel", "tanks"] }),
  });
}

export function useReconcileTank() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ tankId, dip_reading_litres }: { tankId: string; dip_reading_litres: string }) =>
      apiClient.post(`/fuel/tanks/${tankId}/reconcile`, { dip_reading_litres }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["fuel", "tanks"] }),
  });
}

export function useCreatePurchase() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { tank_id: string; quantity_litres: string; unit_price: string }) =>
      apiClient.post("/fuel/purchases", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["fuel", "tanks"] }),
  });
}

export function useCreateIssue() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { tank_id: string; equipment_id: string; quantity_litres: string; issued_at: string }) =>
      apiClient.post("/fuel/issues", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["fuel"] }),
  });
}

export function useCountersignIssue() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (issueId: string) => apiClient.post(`/fuel/issues/${issueId}/countersign`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["fuel"] }),
  });
}

export function useTheftFlags() {
  return useQuery({
    queryKey: ["fuel", "theft-flags"],
    queryFn: async () => (await apiClient.get("/fuel/theft-flags")).data.data,
  });
}

export function useEscalateUnresolvedTheftFlags() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.post("/fuel/theft-flags/escalate-unresolved"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["fuel", "theft-flags"] }),
  });
}
