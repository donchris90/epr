import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../api/client";
import type { Client, Lead, Opportunity } from "./types";

export function useClients() {
  return useQuery({
    queryKey: ["bdc", "clients"],
    queryFn: async () => (await apiClient.get<{ data: Client[] }>("/bdc/clients")).data.data,
  });
}

export function useCreateClient() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { name: string; billing_email?: string }) =>
      apiClient.post<Client>("/bdc/clients", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["bdc", "clients"] }),
  });
}

export function useLeads() {
  return useQuery({
    queryKey: ["bdc", "leads"],
    queryFn: async () => (await apiClient.get<{ data: Lead[] }>("/bdc/leads")).data.data,
  });
}

export function useCreateLead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { name: string; source?: string; estimated_value?: string }) =>
      apiClient.post<Lead>("/bdc/leads", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["bdc", "leads"] }),
  });
}

export function useConvertLead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ leadId, clientId }: { leadId: string; clientId: string }) =>
      apiClient.post<Opportunity>(`/bdc/leads/${leadId}/convert`, { client_id: clientId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["bdc", "leads"] });
      qc.invalidateQueries({ queryKey: ["bdc", "opportunities"] });
    },
  });
}

export function useOpportunities() {
  return useQuery({
    queryKey: ["bdc", "opportunities"],
    queryFn: async () => (await apiClient.get<{ data: Opportunity[] }>("/bdc/opportunities")).data.data,
  });
}

export function useTransitionOpportunity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, newStage }: { id: string; newStage: string }) =>
      apiClient.post<Opportunity>(`/bdc/opportunities/${id}/transition`, { new_stage: newStage }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["bdc", "opportunities"] }),
  });
}

export function useBidNoBidDecision() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      decision,
      rationale,
      reasonCode,
    }: {
      id: string;
      decision: "bid" | "no_bid";
      rationale: string;
      reasonCode?: string;
    }) =>
      apiClient.post<Opportunity>(`/bdc/opportunities/${id}/bid-no-bid`, {
        decision,
        scorecard: {},
        rationale,
        reason_code: reasonCode,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["bdc", "opportunities"] }),
  });
}
