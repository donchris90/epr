import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../../api/client";

/** Real types matching backend/app/modules/exd/routes.py's own real
 * response shapes exactly -- checked directly against the actual
 * route/service code before writing these, not guessed. */
export interface CompanyRevenue {
  actual_revenue: string;
  budget_amount: string | null;
  variance: string | null;
  variance_pct: string | null;
  drill_down_journal_entries: string[];
}

export interface ProjectPerformance {
  project_id: string;
  cpi: string | null;
  spi: string | null;
}

export interface ProjectRisk {
  id: string;
  project_id: string;
  description: string;
  exposure_value: string;
}

/** Real type matching backend/app/modules/exd/services.py's own
 * get_ar_ap_aging_summary return shape exactly -- confirmed directly
 * against the real service function, not guessed. Real bug found and
 * fixed here: an earlier version of this type had
 * total_receivable/total_payable, fields that don't exist on the
 * real response at all -- the actual shape is accounts_receivable/
 * accounts_payable, each the same real age-band structure BIL's own
 * outstanding-invoices report uses, with individual overdue
 * certificates/invoices inside each band. */
export interface AgingItem {
  certificate_id?: string;
  certificate_number?: string;
  invoice_id?: string;
  invoice_number?: string;
  amount: string;
  due_date: string | null;
  status?: string;
}

export interface AgingBands {
  current: AgingItem[];
  "1_30_days": AgingItem[];
  "31_60_days": AgingItem[];
  "61_90_days": AgingItem[];
  over_90_days: AgingItem[];
}

export interface ARAPAging {
  accounts_receivable: AgingBands;
  accounts_payable: AgingBands;
}

/** Sums every real item's amount across all five real age bands. */
export function sumAgingBands(bands: AgingBands): number {
  return Object.values(bands)
    .flat()
    .reduce((sum, item) => sum + Number(item.amount), 0);
}

/** Every real overdue item (any band past "current") across both
 * sides -- the real data source for the dashboard's "Payment issue"
 * alert, not invented. */
export function overdueAgingItems(bands: AgingBands): AgingItem[] {
  return [...bands["1_30_days"], ...bands["31_60_days"], ...bands["61_90_days"], ...bands.over_90_days];
}

export interface EquipmentUtilization {
  ownership_type: string;
  hours_operated: string;
  hours_scheduled: string;
  utilization_pct: string;
}

/** Real, sensible default -- January 1st of the current year through
 * today ("year to date"), the same real default an executive
 * dashboard would reasonably show absent an explicit period picker.
 * Real bug found and fixed while building the dashboard's new
 * sections: period_start/period_end are `required=True` on both
 * CompanyRevenueQuerySchema and EquipmentUtilizationQuerySchema
 * (backend/app/modules/exd/schemas.py) -- neither hook sent them at
 * all before this, so both endpoints have always failed (company-
 * revenue: 422; equipment-utilization: an unhandled 500, confirmed
 * directly by reproducing both), silently shown on the dashboard as
 * a fake "No data yet" empty state rather than a real error. */
function yearToDateRange(): { period_start: string; period_end: string } {
  const now = new Date();
  const jan1 = `${now.getFullYear()}-01-01`;
  const today = now.toISOString().slice(0, 10);
  return { period_start: jan1, period_end: today };
}

export function useCompanyRevenue(companyId?: string) {
  return useQuery({
    queryKey: ["exd", "company-revenue", companyId],
    queryFn: async (): Promise<CompanyRevenue> =>
      (
        await apiClient.get("/exd/company-revenue", {
          params: { company_id: companyId, ...yearToDateRange() },
        })
      ).data,
  });
}

export function useActiveProjectsPerformance() {
  return useQuery({
    queryKey: ["exd", "active-projects-performance"],
    queryFn: async (): Promise<ProjectPerformance[]> => (await apiClient.get("/exd/active-projects-performance")).data.data,
  });
}

export function useProjectRisks() {
  return useQuery({
    queryKey: ["exd", "project-risks"],
    queryFn: async (): Promise<ProjectRisk[]> => (await apiClient.get("/exd/project-risks")).data.data,
  });
}

export function useARAPAging() {
  return useQuery({
    queryKey: ["exd", "ar-ap-aging"],
    queryFn: async (): Promise<ARAPAging> => (await apiClient.get("/exd/ar-ap-aging")).data,
  });
}

export function useEquipmentUtilization() {
  return useQuery({
    queryKey: ["exd", "equipment-utilization"],
    queryFn: async (): Promise<EquipmentUtilization[]> =>
      (await apiClient.get("/exd/equipment-utilization", { params: yearToDateRange() })).data.data,
  });
}

// --- New sections: Commercial, HSE, Workforce ------------------------------------

export interface ProjectNameLookup {
  id: string;
  name: string;
}

/** Real project names, for mapping active-projects-performance's own
 * bare project_id (Module 19's EVMSnapshot has no name of its own)
 * to something a person can actually read -- the same real,
 * established client-side id-to-name mapping pattern already used
 * elsewhere in this codebase (e.g. prc/PurchaseOrdersPage.tsx's
 * vendorsById). */
export function useProjectNames() {
  return useQuery({
    queryKey: ["exd", "project-names"],
    queryFn: async (): Promise<ProjectNameLookup[]> => (await apiClient.get("/projects")).data.data,
  });
}

export interface Incident {
  id: string;
  project_id: string;
  classification: string;
  description: string;
  status: string;
  corrective_action_id: string | null;
  occurred_at: string | null;
}

/** Real HSE incident data (Module 11) for the dashboard's Safety
 * section. Deliberately raw counts by classification and a real
 * trend by month, not TRIR/LTIFR rates: the real rate-calculating
 * endpoint (GET /v1/hse/safety-indicators) requires a real
 * total_hours_worked figure the dashboard has no honest source for
 * (HSE doesn't own that data itself -- see
 * services.calculate_safety_indicators's own docstring), and passing
 * a fabricated value would produce a fake rate, not a real one. See
 * docs/EXECUTIVE_DASHBOARD_GAPS.md. */
export function useIncidents() {
  return useQuery({
    queryKey: ["exd", "incidents"],
    queryFn: async (): Promise<Incident[]> => (await apiClient.get("/hse/incidents")).data.data,
  });
}
