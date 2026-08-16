import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../api/client";

// --- Companies (FIN-12) ----------------------------------------------------------

export function useCompanies() {
  return useQuery({
    queryKey: ["fin", "companies"],
    queryFn: async () => (await apiClient.get("/fin/companies")).data.data,
  });
}

export function useCreateCompany() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { name: string; functional_currency?: string; is_default?: boolean }) =>
      apiClient.post("/fin/companies", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["fin", "companies"] }),
  });
}

// --- Chart of accounts (FIN-01) ---------------------------------------------------

export function useChartOfAccounts() {
  return useQuery({
    queryKey: ["fin", "chart-of-accounts"],
    queryFn: async () => (await apiClient.get("/fin/chart-of-accounts")).data.data,
  });
}

export function useCreateAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { code: string; name: string; account_type: string }) =>
      apiClient.post("/fin/chart-of-accounts", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["fin", "chart-of-accounts"] }),
  });
}

// --- Budget control (FIN-04, business rule) ---------------------------------------

export function useCreateBudgetPolicy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { cost_category?: string; enforcement_mode: string }) =>
      apiClient.post("/fin/budget-control-policies", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["fin", "budget-policies"] }),
  });
}

export function useCheckBudgetControl() {
  return useMutation({
    mutationFn: (payload: { cost_code: string; cost_category?: string; posting_amount: string; cbs_budget_amount: string }) =>
      apiClient.post("/fin/budget-control/check", payload),
  });
}

// --- Accounts Payable / Receivable (FIN-02, FIN-03) -------------------------------

export function useAPInvoices(status?: string) {
  return useQuery({
    queryKey: ["fin", "ap-invoices", status],
    queryFn: async () => (await apiClient.get("/fin/ap-invoices", { params: status ? { status } : {} })).data.data,
  });
}

export function usePostAPInvoice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      company_id: string;
      source_module: string;
      invoice_number: string;
      amount: string;
      expense_account_id: string;
      payable_account_id: string;
      cost_code?: string;
      cost_category?: string;
      cbs_budget_amount?: string;
    }) => apiClient.post("/fin/ap-invoices", payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["fin", "ap-invoices"] });
      qc.invalidateQueries({ queryKey: ["fin", "journal-entries"] });
    },
  });
}

export function useARInvoices(status?: string) {
  return useQuery({
    queryKey: ["fin", "ar-invoices", status],
    queryFn: async () => (await apiClient.get("/fin/ar-invoices", { params: status ? { status } : {} })).data.data,
  });
}

export function usePostARInvoice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      company_id: string;
      source_module: string;
      invoice_number: string;
      amount: string;
      receivable_account_id: string;
      revenue_account_id: string;
    }) => apiClient.post("/fin/ar-invoices", payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["fin", "ar-invoices"] });
      qc.invalidateQueries({ queryKey: ["fin", "journal-entries"] });
    },
  });
}

// --- Journal entries & manual exception (business rule) ---------------------------

export function useJournalEntries(sourceModule?: string) {
  return useQuery({
    queryKey: ["fin", "journal-entries", sourceModule],
    queryFn: async () =>
      (await apiClient.get("/fin/journal-entries", { params: sourceModule ? { source_module: sourceModule } : {} })).data
        .data,
  });
}

export function usePostManualException() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      company_id: string;
      description: string;
      entry_date?: string;
      lines: { account_id: string; debit_amount?: string; credit_amount?: string }[];
    }) => apiClient.post("/fin/journal-entries/manual-exception", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["fin", "journal-entries"] }),
  });
}

// --- Project costing (FIN-10) -----------------------------------------------------

export function useProjectCostSummary(projectId?: string) {
  return useQuery({
    queryKey: ["fin", "project-cost-summary", projectId],
    queryFn: async () => (await apiClient.get("/fin/project-cost-summary", { params: { project_id: projectId } })).data.data,
    enabled: !!projectId,
  });
}

// --- Financial statements (FIN-09) ------------------------------------------------

export function useGenerateIncomeStatement() {
  return useMutation({
    mutationFn: (payload: { company_id?: string; period_start: string; period_end: string }) =>
      apiClient.post("/fin/financial-statements/income-statement", payload),
  });
}
