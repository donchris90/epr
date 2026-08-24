import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../api/client";

/** Real type matching backend/app/modules/wfm/schemas.py's own
 * EmployeeSchema exactly -- checked directly before writing this. */
export interface Employee {
  id: string;
  name: string;
  employee_number: string | null;
  role: string | null;
  trade: string | null;
  pay_grade: string | null;
  employment_type: "permanent" | "contract";
  monthly_rate: string | null;
  assigned_project_ids: string[] | null;
  status: string;
}

export function useEmployees() {
  return useQuery({
    queryKey: ["wfm", "employees"],
    queryFn: async (): Promise<Employee[]> => (await apiClient.get("/wfm/employees")).data.data,
  });
}

export function useCreateEmployee() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { name: string; role?: string; trade?: string; employment_type?: string; monthly_rate?: string }) =>
      apiClient.post("/wfm/employees", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["wfm", "employees"] }),
  });
}

export function useCasualWorkers() {
  return useQuery({
    queryKey: ["wfm", "casual-workers"],
    queryFn: async () => (await apiClient.get("/wfm/casual-workers")).data.data,
  });
}

export function useCreateCasualWorker() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { name: string; phone?: string; daily_rate?: string }) =>
      apiClient.post("/wfm/casual-workers", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["wfm", "casual-workers"] }),
  });
}

export function useTimesheets() {
  return useQuery({
    queryKey: ["wfm", "timesheets"],
    queryFn: async () => (await apiClient.get("/wfm/timesheets")).data.data,
  });
}

export function useGenerateTimesheet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      employee_id?: string;
      casual_worker_id?: string;
      period_start: string;
      period_end: string;
      pay_basis?: string;
      hours_or_units: string;
      rate_applied: string;
    }) => apiClient.post("/wfm/timesheets", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["wfm", "timesheets"] }),
  });
}

export function useDecideTimesheet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ timesheetId, decision }: { timesheetId: string; decision: "approve" | "reject" }) =>
      apiClient.post(`/wfm/timesheets/${timesheetId}/${decision}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["wfm", "timesheets"] }),
  });
}

export function useLeaveRequests() {
  return useQuery({
    queryKey: ["wfm", "leave-requests"],
    queryFn: async () => (await apiClient.get("/wfm/leave-requests")).data.data,
  });
}

export function useCreateLeaveRequest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { employee_id: string; leave_type: string; start_date: string; end_date: string; reason?: string }) =>
      apiClient.post("/wfm/leave-requests", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["wfm", "leave-requests"] }),
  });
}

export function useDecideLeaveRequest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ leaveId, decision }: { leaveId: string; decision: "approved" | "rejected" }) =>
      apiClient.post(`/wfm/leave-requests/${leaveId}/decide`, { decision }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["wfm", "leave-requests"] }),
  });
}

export function useExpiringCertifications() {
  return useQuery({
    queryKey: ["wfm", "certifications", "expiring"],
    queryFn: async () => (await apiClient.get("/wfm/certifications/expiring")).data.data,
  });
}

export function usePayrollRuns() {
  return useQuery({
    queryKey: ["wfm", "payroll-runs"],
    queryFn: async () => (await apiClient.get("/wfm/payroll-runs")).data,
    enabled: false, // no list route exists; kept for future use
  });
}

export function useGeneratePayrollRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { period_start: string; period_end: string }) => apiClient.post("/wfm/payroll-runs", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["wfm", "payroll-runs"] }),
  });
}

export function usePayrollRun(runId?: string) {
  return useQuery({
    queryKey: ["wfm", "payroll-runs", runId],
    queryFn: async () => (await apiClient.get(`/wfm/payroll-runs/${runId}`)).data,
    enabled: !!runId,
  });
}

export function useFinalizePayrollRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (runId: string) => apiClient.post(`/wfm/payroll-runs/${runId}/finalize`),
    onSuccess: (_data, runId) => qc.invalidateQueries({ queryKey: ["wfm", "payroll-runs", runId] }),
  });
}
