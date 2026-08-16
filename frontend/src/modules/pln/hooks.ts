import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../api/client";

// --- WBS nodes (PLN-01) -------------------------------------------------------

export function useWBSNodes(projectId?: string) {
  return useQuery({
    queryKey: ["pln", "wbs-nodes", projectId],
    queryFn: async () =>
      (await apiClient.get("/pln/wbs-nodes", { params: projectId ? { project_id: projectId } : {} })).data.data,
  });
}

export function useCreateWBSNode() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { project_id?: string; parent_id?: string; code?: string; name: string; sort_order?: number }) =>
      apiClient.post("/pln/wbs-nodes", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pln", "wbs-nodes"] }),
  });
}

// --- Activities & CPM schedule (PLN-02, PLN-03, PLN-04) -----------------------

export function useProjectActivities(projectId?: string) {
  return useQuery({
    queryKey: ["pln", "activities", projectId],
    queryFn: async () => (await apiClient.get("/pln/activities", { params: { project_id: projectId } })).data.data,
    enabled: !!projectId,
  });
}

export function useAddActivity(wbsNodeId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { name: string; planned_start: string; duration_days: number }) =>
      apiClient.post(`/pln/wbs-nodes/${wbsNodeId}/activities`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pln", "activities"] }),
  });
}

export function useAddDependency() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { predecessor_id: string; successor_id: string; dependency_type?: string; lag_days?: number }) =>
      apiClient.post("/pln/activity-dependencies", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pln", "activities"] }),
  });
}

export function useRecalculateSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (wbsNodeId: string) => apiClient.post(`/pln/wbs-nodes/${wbsNodeId}/recalculate-schedule`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pln", "activities"] }),
  });
}

// --- Resource loading (PLN-05) -------------------------------------------------

export function useAddResourceAssignment(activityId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { resource_type: string; resource_name: string; quantity?: string; unit?: string }) =>
      apiClient.post(`/pln/activities/${activityId}/resource-assignments`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pln", "over-allocation"] }),
  });
}

export function useCheckOverAllocation(resourceName?: string) {
  return useQuery({
    queryKey: ["pln", "over-allocation", resourceName],
    queryFn: async () =>
      (await apiClient.get("/pln/resource-assignments/over-allocation", { params: { resource_name: resourceName } })).data,
    enabled: !!resourceName,
  });
}

// --- Baselines (PLN-06, PLN-11) -------------------------------------------------

export function useCreateBaseline() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { project_id?: string; wbs_root_id: string; label: string; mark_current?: boolean }) =>
      apiClient.post("/pln/baselines", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pln", "baselines"] }),
  });
}

export function useScheduleVariance(baselineId?: string, activityId?: string) {
  return useQuery({
    queryKey: ["pln", "variance", baselineId, activityId],
    queryFn: async () => (await apiClient.get(`/pln/baselines/${baselineId}/variance/${activityId}`)).data,
    enabled: !!baselineId && !!activityId,
  });
}

// --- Delay events (PLN-08) -------------------------------------------------------

export function useDelayEvents(projectId?: string) {
  return useQuery({
    queryKey: ["pln", "delay-events", projectId],
    queryFn: async () =>
      (await apiClient.get("/pln/delay-events", { params: projectId ? { project_id: projectId } : {} })).data.data,
  });
}

export function useCreateDelayEvent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      project_id?: string;
      activity_id?: string;
      cause_classification: string;
      description: string;
      delay_days: number;
      occurred_on: string;
    }) => apiClient.post("/pln/delay-events", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pln", "delay-events"] }),
  });
}
