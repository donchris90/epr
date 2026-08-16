import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../api/client";

// Note: the backend exposes create/act routes for these entities but
// no list routes -- this module's UI works with the record just
// created/acted on (tracked in local component state) rather than a
// browsable list, which is an honest reflection of what's actually
// there today rather than a fabricated listing.

export function useCreateDesignSurface() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { project_id: string; name: string }) => apiClient.post("/svy/design-surfaces", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["svy"] }),
  });
}

export function useApproveDesignSurface() {
  return useMutation({
    mutationFn: (surfaceId: string) => apiClient.post(`/svy/design-surfaces/${surfaceId}/approve`),
  });
}

export function useCreateEarthworksVolume() {
  return useMutation({
    mutationFn: (payload: { project_id: string; design_surface_id?: string; cut_volume?: string; fill_volume?: string }) =>
      apiClient.post("/svy/earthworks-volumes", payload),
  });
}

export function useSubmitEarthworksForBilling() {
  return useMutation({
    mutationFn: (calcId: string) => apiClient.post(`/svy/earthworks-volumes/${calcId}/submit-for-billing`),
  });
}

export function useCreateAsBuiltRecord() {
  return useMutation({
    mutationFn: (payload: { project_id: string; scope_reference?: string; constructed_level?: string }) =>
      apiClient.post("/svy/as-built-records", payload),
  });
}

export function useLockAsBuiltRecord() {
  return useMutation({
    mutationFn: (recordId: string) => apiClient.post(`/svy/as-built-records/${recordId}/lock`),
  });
}
