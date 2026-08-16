import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../api/client";

// --- Diaries (EXE-01, EXE-12, business rule: sign -> read-only) -------------

export function useDiaries(projectId?: string) {
  return useQuery({
    queryKey: ["exe", "diaries", projectId],
    queryFn: async () =>
      (await apiClient.get("/exe/diaries", { params: projectId ? { project_id: projectId } : {} })).data.data,
  });
}

export function useDiary(diaryId?: string) {
  return useQuery({
    queryKey: ["exe", "diaries", "detail", diaryId],
    queryFn: async () => (await apiClient.get(`/exe/diaries/${diaryId}`)).data,
    enabled: !!diaryId,
  });
}

export function useCreateDiary() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      project_id: string;
      diary_date: string;
      workforce_present_count?: number;
      equipment_on_site_summary?: string;
      narrative?: string;
    }) => apiClient.post("/exe/diaries", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["exe", "diaries"] }),
  });
}

export function useUpdateDiary(diaryId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { workforce_present_count?: number; equipment_on_site_summary?: string; narrative?: string }) =>
      apiClient.put(`/exe/diaries/${diaryId}`, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["exe", "diaries", "detail", diaryId] });
      qc.invalidateQueries({ queryKey: ["exe", "diaries"] });
    },
  });
}

export function useSignDiary(diaryId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.post(`/exe/diaries/${diaryId}/sign`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["exe", "diaries", "detail", diaryId] });
      qc.invalidateQueries({ queryKey: ["exe", "diaries"] });
    },
  });
}

export function useCountersignDiary(diaryId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.post(`/exe/diaries/${diaryId}/countersign`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["exe", "diaries", "detail", diaryId] });
      qc.invalidateQueries({ queryKey: ["exe", "diaries"] });
    },
  });
}

export function useAddAmendment(diaryId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (description: string) => apiClient.post(`/exe/diaries/${diaryId}/amendments`, { description }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["exe", "diaries", "detail", diaryId, "amendments"] }),
  });
}

export function useAmendments(diaryId?: string) {
  return useQuery({
    queryKey: ["exe", "diaries", "detail", diaryId, "amendments"],
    queryFn: async () => (await apiClient.get(`/exe/diaries/${diaryId}/amendments`)).data.data,
    enabled: !!diaryId,
  });
}

// --- Weather (EXE-04) ---------------------------------------------------------

export function useAddWeatherRecord(diaryId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { condition?: string; temperature_c?: string; rainfall_mm?: string; wind_kph?: string }) =>
      apiClient.post(`/exe/diaries/${diaryId}/weather`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["exe", "diaries", "detail", diaryId, "weather"] }),
  });
}

export function useWeatherRecords(diaryId?: string) {
  return useQuery({
    queryKey: ["exe", "diaries", "detail", diaryId, "weather"],
    queryFn: async () => (await apiClient.get(`/exe/diaries/${diaryId}/weather`)).data.data,
    enabled: !!diaryId,
  });
}

// --- Labor & equipment usage (EXE-09) -----------------------------------------

export function useAddLaborUsage(diaryId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { trade: string; headcount: number; hours_worked: string }) =>
      apiClient.post(`/exe/diaries/${diaryId}/labor-usage`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["exe", "diaries", "detail", diaryId, "labor"] }),
  });
}

export function useLaborUsage(diaryId?: string) {
  return useQuery({
    queryKey: ["exe", "diaries", "detail", diaryId, "labor"],
    queryFn: async () => (await apiClient.get(`/exe/diaries/${diaryId}/labor-usage`)).data.data,
    enabled: !!diaryId,
  });
}

export function useAddEquipmentUsage(diaryId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { equipment_identifier: string; hours_used: string; operator_name?: string }) =>
      apiClient.post(`/exe/diaries/${diaryId}/equipment-usage`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["exe", "diaries", "detail", diaryId, "equipment"] }),
  });
}

export function useEquipmentUsage(diaryId?: string) {
  return useQuery({
    queryKey: ["exe", "diaries", "detail", diaryId, "equipment"],
    queryFn: async () => (await apiClient.get(`/exe/diaries/${diaryId}/equipment-usage`)).data.data,
    enabled: !!diaryId,
  });
}

// --- Progress entries (EXE-05) -------------------------------------------------

export function useProgressEntries(activityId?: string) {
  return useQuery({
    queryKey: ["exe", "progress-entries", activityId],
    queryFn: async () =>
      (await apiClient.get("/exe/progress-entries", { params: activityId ? { activity_id: activityId } : {} })).data
        .data,
  });
}

export function useAddProgressEntry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      activity_id: string;
      diary_id?: string;
      measurement_type: string;
      value: string;
      unit?: string;
    }) => apiClient.post("/exe/progress-entries", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["exe", "progress-entries"] }),
  });
}

// --- Work completed (EXE-06, business rule: warns on overage) -----------------

export function useAddWorkCompleted() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      boq_item_id: string;
      quantity: string;
      contracted_quantity: string;
      unit?: string;
      diary_id?: string;
    }) => apiClient.post("/exe/work-completed", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["exe", "work-completed"] }),
  });
}

// --- Site issues (EXE-07) -------------------------------------------------------

export function useSiteIssues(projectId?: string, status?: string) {
  return useQuery({
    queryKey: ["exe", "site-issues", projectId, status],
    queryFn: async () =>
      (
        await apiClient.get("/exe/site-issues", {
          params: { ...(projectId ? { project_id: projectId } : {}), ...(status ? { status } : {}) },
        })
      ).data.data,
  });
}

export function useCreateSiteIssue() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      project_id: string;
      diary_id?: string;
      category?: string;
      severity?: string;
      description: string;
      due_date?: string;
    }) => apiClient.post("/exe/site-issues", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["exe", "site-issues"] }),
  });
}

export function useEscalateOverdueIssues() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.post("/exe/site-issues/escalate-overdue"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["exe", "site-issues"] }),
  });
}

// --- Inspection logs (EXE-11) ----------------------------------------------------

export function useInspectionLogs(outcome?: string) {
  return useQuery({
    queryKey: ["exe", "inspection-logs", outcome],
    queryFn: async () =>
      (await apiClient.get("/exe/inspection-logs", { params: outcome ? { outcome } : {} })).data.data,
  });
}

export function useAddInspectionLog(diaryId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      inspected_item: string;
      outcome: string;
      itp_reference?: string;
      inspector_name?: string;
      notes?: string;
    }) => apiClient.post("/exe/inspection-logs", { diary_id: diaryId, ...payload }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["exe", "inspection-logs"] });
      if (diaryId) qc.invalidateQueries({ queryKey: ["exe", "diaries", "detail", diaryId] });
    },
  });
}
