import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../api/client";
import type {
  BOQItem,
  BudgetRevision,
  CostBreakdownStructure,
  CostLibraryItem,
  EngineersEstimate,
  EquipmentRate,
  EstimateVersion,
  LaborRate,
  Markup,
  MaterialPrice,
  RateAnalysis,
  TenderPriceSummary,
  VendorQuotation,
} from "./types";

// --- Estimate versions (EST-13, EST-14) -----------------------------------

export function useEstimateVersions(tenderId?: string) {
  return useQuery({
    queryKey: ["est", "versions", tenderId],
    queryFn: async () => (await apiClient.get<{ data: EstimateVersion[] }>(`/est/tenders/${tenderId}/estimate-versions`)).data.data,
    enabled: !!tenderId,
  });
}

export function useCreateEstimateVersion(tenderId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (label?: string) => apiClient.post<EstimateVersion>("/est/estimate-versions", { tender_id: tenderId, label }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["est", "versions", tenderId] }),
  });
}

export function useSubmitEstimateVersion(versionId?: string, tenderId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.post<EstimateVersion>(`/est/estimate-versions/${versionId}/submit`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["est", "versions", tenderId] }),
  });
}

// --- BOQ items (EST-01) ----------------------------------------------------

export function useBOQItems(versionId?: string) {
  return useQuery({
    queryKey: ["est", "boq-items", versionId],
    queryFn: async () => (await apiClient.get<{ data: BOQItem[] }>(`/est/estimate-versions/${versionId}/boq-items`)).data.data,
    enabled: !!versionId,
  });
}

export function useAddBOQItem(versionId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { description: string; unit?: string; quantity?: string; item_code?: string }) =>
      apiClient.post<BOQItem>(`/est/estimate-versions/${versionId}/boq-items`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["est", "boq-items", versionId] }),
  });
}

// --- Rate analysis & reconciliation (EST-02) --------------------------------

export function useRateAnalysis(boqItemId?: string) {
  return useQuery({
    queryKey: ["est", "rate-analysis", boqItemId],
    queryFn: async () => (await apiClient.get<RateAnalysis>(`/est/boq-items/${boqItemId}/rate-analysis`)).data,
    enabled: !!boqItemId,
    retry: false, // a 404 here just means "not priced yet" -- not worth retrying
  });
}

export function useSaveRateAnalysis(versionId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      boqItemId,
      lines,
      markupPct,
    }: {
      boqItemId: string;
      lines: { component_type: string; description: string; quantity_per_unit: string; unit_cost: string; cost_library_item_id?: string }[];
      markupPct: string;
    }) => apiClient.put<RateAnalysis>(`/est/boq-items/${boqItemId}/rate-analysis`, { lines, markup_pct: markupPct }),
    onSuccess: (_res, vars) => {
      qc.invalidateQueries({ queryKey: ["est", "boq-items", versionId] });
      qc.invalidateQueries({ queryKey: ["est", "rate-analysis", vars.boqItemId] });
      qc.invalidateQueries({ queryKey: ["est", "engineers-estimate", versionId] });
      qc.invalidateQueries({ queryKey: ["est", "tender-price", versionId] });
    },
  });
}

// --- Cost libraries, prices, rates -- "resources" (EST-03 through EST-07) --

export function useCostLibraryItems() {
  return useQuery({
    queryKey: ["est", "cost-library-items"],
    queryFn: async () => (await apiClient.get<{ data: CostLibraryItem[] }>("/est/cost-library-items")).data.data,
  });
}

export function useCreateCostLibraryItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { code: string; description: string; component_type: string; unit?: string; default_unit_cost: string }) =>
      apiClient.post<CostLibraryItem>("/est/cost-library-items", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["est", "cost-library-items"] }),
  });
}

export function useMaterialPrices(materialName?: string) {
  return useQuery({
    queryKey: ["est", "material-prices", materialName ?? "all"],
    queryFn: async () =>
      (await apiClient.get<{ data: MaterialPrice[] }>("/est/material-prices", { params: { material_name: materialName } })).data.data,
  });
}

export function useCreateMaterialPrice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { material_name: string; price: string; effective_date: string; location?: string; unit?: string; cost_library_item_id?: string }) =>
      apiClient.post<MaterialPrice>("/est/material-prices", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["est", "material-prices"] }),
  });
}

export function useEquipmentRates() {
  return useQuery({
    queryKey: ["est", "equipment-rates"],
    queryFn: async () => (await apiClient.get<{ data: EquipmentRate[] }>("/est/equipment-rates")).data.data,
  });
}

export function useCreateEquipmentRate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { equipment_type: string; cost_per_hour: string; source?: string; effective_date?: string }) =>
      apiClient.post<EquipmentRate>("/est/equipment-rates", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["est", "equipment-rates"] }),
  });
}

export function useLaborRates() {
  return useQuery({
    queryKey: ["est", "labor-rates"],
    queryFn: async () => (await apiClient.get<{ data: LaborRate[] }>("/est/labor-rates")).data.data,
  });
}

export function useCreateLaborRate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { trade: string; hourly_rate: string; grade?: string; statutory_oncost_pct?: string }) =>
      apiClient.post<LaborRate>("/est/labor-rates", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["est", "labor-rates"] }),
  });
}

export function useVendorQuotations(boqItemId?: string) {
  return useQuery({
    queryKey: ["est", "vendor-quotations", boqItemId],
    queryFn: async () => (await apiClient.get<{ data: VendorQuotation[] }>(`/est/boq-items/${boqItemId}/vendor-quotations`)).data.data,
    enabled: !!boqItemId,
  });
}

export function useCreateVendorQuotation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { boq_item_id: string; vendor_name: string; quoted_price: string; description?: string; quoted_at?: string; valid_until?: string }) =>
      apiClient.post<VendorQuotation>("/est/vendor-quotations", payload),
    onSuccess: (_res, vars) => qc.invalidateQueries({ queryKey: ["est", "vendor-quotations", vars.boq_item_id] }),
  });
}

// --- Markup & contingency (EST-08, EST-09) ---------------------------------
// Both of these are write/create-only on the backend: there is no
// `GET .../markups` or `GET .../contingency-items` list endpoint (see
// tbm/routes.py's equivalents by contrast, which at least have BOQ/
// bid-document GETs). Records created here can't be refetched or
// re-displayed after the fact, so the UI keeps them in local state for
// the current session and says so -- exactly the same honest
// workaround used for TBM's RFIs/Clarifications.

export function useAddMarkup(versionId?: string) {
  return useMutation({
    mutationFn: (payload: { scope: string; overhead_pct: string; profit_pct: string; target_boq_item_id?: string }) =>
      apiClient.post<Markup>(`/est/estimate-versions/${versionId}/markups`, payload),
  });
}

export function useAddContingencyItem(versionId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { kind: string; basis: string; value: string; description?: string }) =>
      apiClient.post<import("./types").ContingencyItem>(`/est/estimate-versions/${versionId}/contingency-items`, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["est", "tender-price", versionId] });
    },
  });
}

// --- Engineer's Estimate & Tender Price (EST-10, EST-11) --------------------
// Both are real backend-computed totals -- never recompute these
// client-side; only ever display what these two endpoints return.

export function useEngineersEstimate(versionId?: string) {
  return useQuery({
    queryKey: ["est", "engineers-estimate", versionId],
    queryFn: async () => (await apiClient.get<EngineersEstimate>(`/est/estimate-versions/${versionId}/engineers-estimate`)).data,
    enabled: !!versionId,
  });
}

export function useTenderPrice(versionId?: string) {
  return useQuery({
    queryKey: ["est", "tender-price", versionId],
    queryFn: async () => (await apiClient.get<TenderPriceSummary>(`/est/estimate-versions/${versionId}/tender-price`)).data,
    enabled: !!versionId,
  });
}

// --- Cost Breakdown Structure & Budget baseline (EST-12) --------------------

export function useGenerateCBS(versionId?: string) {
  return useMutation({
    mutationFn: (projectId?: string) => apiClient.post<CostBreakdownStructure>(`/est/estimate-versions/${versionId}/generate-cbs`, { project_id: projectId }),
  });
}

export function useCBS(cbsId?: string) {
  return useQuery({
    queryKey: ["est", "cbs", cbsId],
    queryFn: async () => (await apiClient.get<CostBreakdownStructure>(`/est/cost-breakdown-structures/${cbsId}`)).data,
    enabled: !!cbsId,
  });
}

export function useApproveCBS(cbsId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.post<CostBreakdownStructure>(`/est/cost-breakdown-structures/${cbsId}/approve`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["est", "cbs", cbsId] }),
  });
}

export function useCreateBudgetRevision(cbsId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { cbs_line_item_id: string; reason: string; revised_amount: string }) =>
      apiClient.post<BudgetRevision>(`/est/cost-breakdown-structures/${cbsId}/budget-revisions`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["est", "cbs", cbsId] }),
  });
}

export function useFinalizeBudgetRevision(cbsId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (revisionId: string) => apiClient.post<BudgetRevision>(`/est/budget-revisions/${revisionId}/finalize`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["est", "cbs", cbsId] }),
  });
}
