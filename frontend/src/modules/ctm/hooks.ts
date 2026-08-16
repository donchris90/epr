import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../../api/client";

export function useContracts() {
  return useQuery({
    queryKey: ["ctm", "contracts"],
    queryFn: async () => (await apiClient.get("/ctm/contracts")).data.data,
  });
}

export function useContract(contractId?: string) {
  return useQuery({
    queryKey: ["ctm", "contract", contractId],
    queryFn: async () => (await apiClient.get(`/ctm/contracts/${contractId}`)).data,
    enabled: !!contractId,
  });
}

export function useExpiringInstruments(withinDays = 30) {
  return useQuery({
    queryKey: ["ctm", "expiring", withinDays],
    queryFn: async () => (await apiClient.get(`/ctm/expiring-instruments?within_days=${withinDays}`)).data,
  });
}
