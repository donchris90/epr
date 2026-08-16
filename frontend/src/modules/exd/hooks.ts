import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../../api/client";

export function useCompanyRevenue(companyId?: string) {
  return useQuery({
    queryKey: ["exd", "company-revenue", companyId],
    queryFn: async () => (await apiClient.get("/exd/company-revenue", { params: { company_id: companyId } })).data,
  });
}

export function useActiveProjectsPerformance() {
  return useQuery({
    queryKey: ["exd", "active-projects-performance"],
    queryFn: async () => (await apiClient.get("/exd/active-projects-performance")).data.data,
  });
}

export function useProjectRisks() {
  return useQuery({
    queryKey: ["exd", "project-risks"],
    queryFn: async () => (await apiClient.get("/exd/project-risks")).data.data,
  });
}

export function useARAPAging() {
  return useQuery({
    queryKey: ["exd", "ar-ap-aging"],
    queryFn: async () => (await apiClient.get("/exd/ar-ap-aging")).data,
  });
}

export function useEquipmentUtilization() {
  return useQuery({
    queryKey: ["exd", "equipment-utilization"],
    queryFn: async () => (await apiClient.get("/exd/equipment-utilization")).data.data,
  });
}
