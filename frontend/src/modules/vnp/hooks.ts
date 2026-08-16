import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../api/client";

export function useCreateVendorUser() {
  return useMutation({
    mutationFn: (payload: { vendor_id: string; email: string }) => apiClient.post("/vnp/vendor-users", payload),
  });
}

export function useBankingChangeRequests(status?: string) {
  return useQuery({
    queryKey: ["vnp", "banking-change-requests", status],
    queryFn: async () => (await apiClient.get("/vnp/banking-change-requests", { params: { status } })).data.data,
  });
}

export function useApproveBankingChange() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (requestId: string) => apiClient.post(`/vnp/banking-change-requests/${requestId}/approve`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["vnp", "banking-change-requests"] }),
  });
}

export function useRejectBankingChange() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ requestId, reason }: { requestId: string; reason: string }) =>
      apiClient.post(`/vnp/banking-change-requests/${requestId}/reject`, { reason }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["vnp", "banking-change-requests"] }),
  });
}
