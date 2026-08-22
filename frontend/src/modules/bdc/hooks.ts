import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../api/client";
import type { Client, Lead, Opportunity } from "./types";
import type { Competitor, Consultant, GovernmentAgency, WinLossRecord, WinLossSummaryRow } from "./types";

export function useClients() {
  return useQuery({
    queryKey: ["bdc", "clients"],
    queryFn: async () => (await apiClient.get<{ data: Client[] }>("/bdc/clients")).data.data,
  });
}

/** No `GET /bdc/clients/<id>` endpoint exists on the backend (see
 * routes.py -- only list + create), so a "detail" lookup is a
 * client-side find over the already-fetched list rather than its own
 * request. This is why ClientDetailPage renders nothing useful until
 * useClients() itself has resolved. */
export function useClient(clientId?: string) {
  const clients = useClients();
  const client = clientId ? clients.data?.find((c) => c.id === clientId) : undefined;
  return { ...clients, data: client };
}

export function useCreateClient() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { name: string; billing_email?: string; billing_address?: string; notes?: string }) =>
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

/** Same story as useClient -- no `GET /bdc/leads/<id>`. */
export function useLead(leadId?: string) {
  const leads = useLeads();
  const lead = leadId ? leads.data?.find((l) => l.id === leadId) : undefined;
  return { ...leads, data: lead };
}

export function useCreateLead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      name: string;
      source?: string;
      estimated_value?: string;
      currency?: string;
      probability_pct?: string;
      client_id?: string;
    }) => apiClient.post<Lead>("/bdc/leads", payload),
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

/** `stage` is a real, supported query param on `GET /bdc/opportunities`
 * (see routes.py) -- kept as a separate hook rather than folding into
 * useOpportunities() above so that call keeps matching the exact
 * source pattern the module's type-safety regression test
 * (hooks.test.ts) checks for. */
export function useOpportunitiesByStage(stage: string) {
  return useQuery({
    queryKey: ["bdc", "opportunities", stage],
    queryFn: async () =>
      (await apiClient.get<{ data: Opportunity[] }>("/bdc/opportunities", { params: { stage } })).data.data,
  });
}

/** Same story as useClient/useLead -- no `GET /bdc/opportunities/<id>`.
 * Always fetches the unfiltered list so a single opportunity can be
 * found regardless of what stage filter a list page elsewhere used. */
export function useOpportunity(opportunityId?: string) {
  const opportunities = useOpportunities();
  const opportunity = opportunityId ? opportunities.data?.find((o) => o.id === opportunityId) : undefined;
  return { ...opportunities, data: opportunity };
}

export function useTenderCalendar() {
  return useQuery({
    queryKey: ["bdc", "opportunities", "tender-calendar"],
    queryFn: async () => (await apiClient.get<{ data: Opportunity[] }>("/bdc/opportunities/tender-calendar")).data.data,
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
      scorecard,
    }: {
      id: string;
      decision: "bid" | "no_bid";
      rationale: string;
      reasonCode?: string;
      scorecard: Record<string, unknown>;
    }) =>
      apiClient.post<Opportunity>(`/bdc/opportunities/${id}/bid-no-bid`, {
        decision,
        scorecard,
        rationale,
        reason_code: reasonCode,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["bdc", "opportunities"] }),
  });
}

export function useRecordWinLoss() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      outcome,
      winningPrice,
      competitorId,
      reasonCode,
      valueBand,
    }: {
      id: string;
      outcome: "won" | "lost";
      winningPrice?: string;
      competitorId?: string;
      reasonCode?: string;
      valueBand?: string;
    }) =>
      apiClient.post<WinLossRecord>(`/bdc/opportunities/${id}/win-loss`, {
        opportunity_id: id,
        outcome,
        winning_price: winningPrice || undefined,
        competitor_id: competitorId || undefined,
        reason_code: reasonCode || undefined,
        value_band: valueBand || undefined,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["bdc", "opportunities"] }),
  });
}

export function useWinLossSummary(groupBy: "client" | "value_band" = "client") {
  return useQuery({
    queryKey: ["bdc", "win-loss-summary", groupBy],
    queryFn: async () =>
      (await apiClient.get<{ data: WinLossSummaryRow[] }>("/bdc/opportunities/win-loss-summary", { params: { group_by: groupBy } }))
        .data.data,
  });
}

export function useCompetitors() {
  return useQuery({
    queryKey: ["bdc", "competitors"],
    queryFn: async () => (await apiClient.get<{ data: Competitor[] }>("/bdc/competitors")).data.data,
  });
}

export function useConsultants() {
  return useQuery({
    queryKey: ["bdc", "consultants"],
    queryFn: async () => (await apiClient.get<{ data: Consultant[] }>("/bdc/consultants")).data.data,
  });
}

export function useGovernmentAgencies() {
  return useQuery({
    queryKey: ["bdc", "government-agencies"],
    queryFn: async () => (await apiClient.get<{ data: GovernmentAgency[] }>("/bdc/government-agencies")).data.data,
  });
}
