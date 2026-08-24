import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../api/client";

/** Real types matching backend/app/modules/wfm/schemas.py exactly --
 * checked directly against the actual schemas before writing these. */
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

export interface CasualWorker {
  id: string;
  name: string;
  phone: string | null;
  id_number: string | null;
  daily_rate: string | null;
  status: string;
}

export interface AttendanceRecord {
  id: string;
  project_id: string;
  employee_id: string | null;
  casual_worker_id: string | null;
  attendance_date: string;
  check_in_at: string | null;
  check_out_at: string | null;
  capture_method: string;
}

export interface Timesheet {
  id: string;
  employee_id: string | null;
  casual_worker_id: string | null;
  project_id: string | null;
  activity_id: string | null;
  period_start: string;
  period_end: string;
  pay_basis: string;
  hours_or_units: string;
  rate_applied: string;
  gross_amount: string;
  status: "pending_approval" | "approved" | "rejected" | "returned" | "locked";
  approved_by: string | null;
  approved_at: string | null;
  payroll_run_id: string | null;
}

export interface LeaveRequest {
  id: string;
  employee_id: string;
  leave_type: string;
  start_date: string;
  end_date: string;
  reason: string | null;
  status: "pending" | "approved" | "rejected" | "cancelled";
  approved_by: string | null;
  approved_at: string | null;
}

export interface TrainingRecord {
  id: string;
  employee_id: string;
  course_name: string;
  provider: string | null;
  completion_date: string | null;
  expiry_date: string | null;
}

export interface Competency {
  id: string;
  employee_id: string;
  skill_or_equipment_type: string;
  proficiency_level: string | null;
  verified_by: string | null;
  verified_at: string | null;
}

export interface Certification {
  id: string;
  employee_id: string;
  certification_type: string;
  certificate_number: string | null;
  issued_at: string | null;
  expiry_date: string | null;
  issuing_body: string | null;
}

export interface PayrollLine {
  id: string;
  payroll_run_id: string;
  employee_id: string | null;
  casual_worker_id: string | null;
  gross_pay: string;
  deductions_breakdown: Record<string, string> | null;
  total_deductions: string;
  net_pay: string;
  bank_account_ref: string | null;
}

export interface PayrollRun {
  id: string;
  period_start: string;
  period_end: string;
  status: "draft" | "finalized";
  finalized_at: string | null;
  finalized_by: string | null;
  total_gross: string;
  total_deductions: string;
  total_net: string;
  lines: PayrollLine[];
}

// --- Employees ---------------------------------------------------------------

export function useEmployees() {
  return useQuery({
    queryKey: ["wfm", "employees"],
    queryFn: async (): Promise<Employee[]> => (await apiClient.get("/wfm/employees")).data.data,
  });
}

export function useEmployee(employeeId?: string) {
  return useQuery({
    queryKey: ["wfm", "employees", employeeId],
    queryFn: async (): Promise<Employee> => (await apiClient.get(`/wfm/employees/${employeeId}`)).data,
    enabled: !!employeeId,
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

export function useUpdateEmployee(employeeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<Pick<Employee, "name" | "role" | "trade" | "pay_grade" | "employment_type" | "monthly_rate">>) =>
      apiClient.put(`/wfm/employees/${employeeId}`, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["wfm", "employees", employeeId] });
      qc.invalidateQueries({ queryKey: ["wfm", "employees"] });
    },
  });
}

export function useTerminateEmployee(employeeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.post(`/wfm/employees/${employeeId}/terminate`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["wfm", "employees", employeeId] });
      qc.invalidateQueries({ queryKey: ["wfm", "employees"] });
    },
  });
}

export function useReactivateEmployee(employeeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.post(`/wfm/employees/${employeeId}/reactivate`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["wfm", "employees", employeeId] });
      qc.invalidateQueries({ queryKey: ["wfm", "employees"] });
    },
  });
}

export function useAssignProject(employeeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (project_id: string) => apiClient.post(`/wfm/employees/${employeeId}/assign-project`, { project_id }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["wfm", "employees", employeeId] }),
  });
}

export function useTransferProject(employeeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { from_project_id: string; to_project_id: string }) =>
      apiClient.post(`/wfm/employees/${employeeId}/transfer-project`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["wfm", "employees", employeeId] }),
  });
}

export function useLeaveBalance(employeeId?: string) {
  return useQuery({
    queryKey: ["wfm", "employees", employeeId, "leave-balance"],
    queryFn: async (): Promise<Record<string, number>> =>
      (await apiClient.get(`/wfm/employees/${employeeId}/leave-balance`)).data.days_taken_this_year_by_type,
    enabled: !!employeeId,
  });
}

// --- Casual workers ------------------------------------------------------------

export function useCasualWorkers() {
  return useQuery({
    queryKey: ["wfm", "casual-workers"],
    queryFn: async (): Promise<CasualWorker[]> => (await apiClient.get("/wfm/casual-workers")).data.data,
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

// --- Attendance ------------------------------------------------------------------

export function useAttendance(filters: { projectId?: string; employeeId?: string; date?: string } = {}) {
  return useQuery({
    queryKey: ["wfm", "attendance", filters],
    queryFn: async (): Promise<AttendanceRecord[]> =>
      (
        await apiClient.get("/wfm/attendance", {
          params: { project_id: filters.projectId, employee_id: filters.employeeId, attendance_date: filters.date },
        })
      ).data.data,
  });
}

export function useRecordAttendance() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { project_id: string; employee_id?: string; casual_worker_id?: string; attendance_date: string; check_in_at?: string; check_out_at?: string }) =>
      apiClient.post("/wfm/attendance", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["wfm", "attendance"] }),
  });
}

export function useCorrectAttendance() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ recordId, ...payload }: { recordId: string; check_in_at?: string; check_out_at?: string }) =>
      apiClient.put(`/wfm/attendance/${recordId}`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["wfm", "attendance"] }),
  });
}

export function useMarkAbsent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { project_id: string; attendance_date: string; employee_id?: string; casual_worker_id?: string }) =>
      apiClient.post("/wfm/attendance/mark-absent", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["wfm", "attendance"] }),
  });
}

// --- Timesheets --------------------------------------------------------------

export function useTimesheets(filters: { status?: string } = {}) {
  return useQuery({
    queryKey: ["wfm", "timesheets", filters],
    queryFn: async (): Promise<Timesheet[]> => (await apiClient.get("/wfm/timesheets", { params: filters })).data.data,
  });
}

export function useTimesheet(timesheetId?: string) {
  return useQuery({
    queryKey: ["wfm", "timesheets", "detail", timesheetId],
    queryFn: async (): Promise<Timesheet> => (await apiClient.get(`/wfm/timesheets/${timesheetId}`)).data,
    enabled: !!timesheetId,
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

export function useUpdateTimesheet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ timesheetId, ...payload }: { timesheetId: string; hours_or_units?: string; rate_applied?: string }) =>
      apiClient.put(`/wfm/timesheets/${timesheetId}`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["wfm", "timesheets"] }),
  });
}

export function useDecideTimesheet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ timesheetId, decision }: { timesheetId: string; decision: "approve" | "reject" | "return" | "resubmit" | "lock" }) =>
      apiClient.post(`/wfm/timesheets/${timesheetId}/${decision}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["wfm", "timesheets"] }),
  });
}

// --- Leave -----------------------------------------------------------------------

export function useLeaveRequests(filters: { employeeId?: string; status?: string } = {}) {
  return useQuery({
    queryKey: ["wfm", "leave-requests", filters],
    queryFn: async (): Promise<LeaveRequest[]> =>
      (await apiClient.get("/wfm/leave-requests", { params: { employee_id: filters.employeeId, status: filters.status } })).data.data,
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

export function useCancelLeaveRequest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (leaveId: string) => apiClient.post(`/wfm/leave-requests/${leaveId}/cancel`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["wfm", "leave-requests"] }),
  });
}

// --- Training, competencies, certifications ---------------------------------------

export function useAddTrainingRecord(employeeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { course_name: string; provider?: string; completion_date?: string; expiry_date?: string }) =>
      apiClient.post(`/wfm/employees/${employeeId}/training-records`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["wfm", "employees", employeeId] }),
  });
}

export function useExpiringTraining(withinDays = 30) {
  return useQuery({
    queryKey: ["wfm", "training-records", "expiring", withinDays],
    queryFn: async (): Promise<TrainingRecord[]> =>
      (await apiClient.get("/wfm/training-records/expiring", { params: { within_days: withinDays } })).data.data,
  });
}

export function useAddCompetency(employeeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { skill_or_equipment_type: string; proficiency_level?: string }) =>
      apiClient.post(`/wfm/employees/${employeeId}/competencies`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["wfm", "employees", employeeId] }),
  });
}

export function useAddCertification(employeeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { certification_type: string; certificate_number?: string; issued_at?: string; expiry_date?: string; issuing_body?: string }) =>
      apiClient.post(`/wfm/employees/${employeeId}/certifications`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["wfm", "employees", employeeId] }),
  });
}

export function useExpiringCertifications(withinDays = 30) {
  return useQuery({
    queryKey: ["wfm", "certifications", "expiring", withinDays],
    queryFn: async (): Promise<Certification[]> =>
      (await apiClient.get("/wfm/certifications/expiring", { params: { within_days: withinDays } })).data.data,
  });
}

// --- Payroll -----------------------------------------------------------------------

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
    queryFn: async (): Promise<PayrollRun> => (await apiClient.get(`/wfm/payroll-runs/${runId}`)).data,
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
