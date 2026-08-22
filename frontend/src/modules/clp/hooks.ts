import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../api/client";

export function useCreateClientUser() {
  return useMutation({
    mutationFn: (payload: { client_organization_name: string; email: string; password: string }) =>
      apiClient.post("/clp/client-users", payload),
  });
}

export function useAssignClientToProject() {
  return useMutation({
    mutationFn: ({ clientUserId, project_id }: { clientUserId: string; project_id: string }) =>
      apiClient.post(`/clp/client-users/${clientUserId}/assignments`, { project_id }),
  });
}

export function useClientRequests(clientUserId?: string) {
  return useQuery({
    queryKey: ["clp", "client-users", clientUserId, "requests"],
    queryFn: async () => (await apiClient.get(`/clp/client-users/${clientUserId}/requests`)).data.data,
    enabled: !!clientUserId,
  });
}

export function useResolveClientRequest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ requestId, response }: { requestId: string; response: string }) =>
      apiClient.post(`/clp/requests/${requestId}/resolve`, { response }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["clp"] }),
  });
}
