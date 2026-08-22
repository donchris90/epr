import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { clientPortalClient } from "./api/client";
import { getClientAccessToken } from "./lib/auth";

// --- Auth ------------------------------------------------------------------

export function useClientLogin() {
  return useMutation({
    mutationFn: (payload: { email: string; password: string }) =>
      clientPortalClient.post("/clp/auth/login", payload),
  });
}

export function useClientMe() {
  return useQuery({
    queryKey: ["cp", "me"],
    queryFn: async () => (await clientPortalClient.get("/clp/auth/me")).data,
    enabled: !!getClientAccessToken(),
    retry: false,
  });
}

export function useChangeClientPassword() {
  return useMutation({
    mutationFn: (payload: { current_password: string; new_password: string }) =>
      clientPortalClient.post("/clp/auth/me/password", payload),
  });
}

// --- Dashboard / projects ---------------------------------------------------

export function useClientProjects() {
  return useQuery({
    queryKey: ["cp", "projects"],
    queryFn: async () => (await clientPortalClient.get(`/clp/client-users/${meId()}/projects`)).data.data,
    enabled: !!getClientAccessToken(),
  });
}

export function useClientProject(projectId?: string) {
  return useQuery({
    queryKey: ["cp", "projects", projectId],
    queryFn: async () => (await clientPortalClient.get(`/clp/client-users/${meId()}/projects/${projectId}`)).data,
    enabled: !!projectId,
  });
}

export function useClientProgress(projectId?: string) {
  return useQuery({
    queryKey: ["cp", "projects", projectId, "progress"],
    queryFn: async () =>
      (await clientPortalClient.get(`/clp/client-users/${meId()}/projects/${projectId}/progress`)).data,
    enabled: !!projectId,
  });
}

export function useClientSchedule(projectId?: string) {
  return useQuery({
    queryKey: ["cp", "projects", projectId, "schedule"],
    queryFn: async () =>
      (await clientPortalClient.get(`/clp/client-users/${meId()}/projects/${projectId}/schedule`)).data.data,
    enabled: !!projectId,
  });
}

export function useClientSiteMedia(projectId?: string) {
  return useQuery({
    queryKey: ["cp", "projects", projectId, "site-media"],
    queryFn: async () =>
      (await clientPortalClient.get(`/clp/client-users/${meId()}/projects/${projectId}/site-media`)).data,
    enabled: !!projectId,
  });
}

// --- Documents & drawings ----------------------------------------------------

export function useClientDocuments(projectId?: string, docType?: string) {
  return useQuery({
    queryKey: ["cp", "projects", projectId, "documents", docType ?? "all"],
    queryFn: async () =>
      (
        await clientPortalClient.get(`/clp/client-users/${meId()}/projects/${projectId}/documents`, {
          params: docType ? { doc_type: docType } : undefined,
        })
      ).data.data,
    enabled: !!projectId,
  });
}

export function useClientDocumentDownload() {
  return useMutation({
    mutationFn: async ({ projectId, documentId }: { projectId: string; documentId: string }) =>
      (
        await clientPortalClient.get(
          `/clp/client-users/${meId()}/projects/${projectId}/documents/${documentId}/download`
        )
      ).data.download_url as string,
  });
}

// --- Certificates, variations, invoices --------------------------------------

export function useClientCertificates(projectId?: string) {
  return useQuery({
    queryKey: ["cp", "projects", projectId, "certificates"],
    queryFn: async () =>
      (await clientPortalClient.get(`/clp/client-users/${meId()}/projects/${projectId}/certificates`)).data.data,
    enabled: !!projectId,
  });
}

export function useClientVariationOrders(projectId?: string) {
  return useQuery({
    queryKey: ["cp", "projects", projectId, "variation-orders"],
    queryFn: async () =>
      (await clientPortalClient.get(`/clp/client-users/${meId()}/projects/${projectId}/variation-orders`)).data.data,
    enabled: !!projectId,
  });
}

export function useClientInvoices(projectId?: string) {
  return useQuery({
    queryKey: ["cp", "projects", projectId, "invoices"],
    queryFn: async () =>
      (await clientPortalClient.get(`/clp/client-users/${meId()}/projects/${projectId}/invoices`)).data.data,
    enabled: !!projectId,
  });
}

// --- Approvals -----------------------------------------------------------------

export function useDecideVariationOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      vo_id,
      project_id,
      decision,
      notes,
    }: {
      vo_id: string;
      project_id: string;
      decision: "approved" | "rejected";
      notes?: string;
    }) =>
      clientPortalClient.post(`/clp/client-users/${meId()}/variation-orders/${vo_id}/decide`, {
        project_id,
        decision,
        notes,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cp"] }),
  });
}

export function useDecideCertificate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      certificate_id,
      project_id,
      decision,
      notes,
    }: {
      certificate_id: string;
      project_id: string;
      decision: "approved" | "rejected";
      notes?: string;
    }) =>
      clientPortalClient.post(`/clp/client-users/${meId()}/certificates/${certificate_id}/decide`, {
        project_id,
        decision,
        notes,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cp"] }),
  });
}

export function useClientApprovalActions() {
  return useQuery({
    queryKey: ["cp", "approval-actions"],
    queryFn: async () => (await clientPortalClient.get(`/clp/client-users/${meId()}/approval-actions`)).data.data,
    enabled: !!getClientAccessToken(),
  });
}

// --- Issues / Messages (ClientRequest, RFI) -----------------------------------

export function useClientRequests(projectId?: string) {
  return useQuery({
    queryKey: ["cp", "requests", projectId ?? "all"],
    queryFn: async () =>
      (
        await clientPortalClient.get(`/clp/client-users/${meId()}/requests`, {
          params: projectId ? { project_id: projectId } : undefined,
        })
      ).data.data,
    enabled: !!getClientAccessToken(),
  });
}

export function useSubmitClientRequest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { project_id: string; request_type: "rfi" | "service_request"; description: string }) =>
      clientPortalClient.post(`/clp/client-users/${meId()}/requests`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cp", "requests"] }),
  });
}

// --- Notifications (real /v1/notifications, unmodified -- see api/client.ts) --

export function useClientNotifications() {
  return useQuery({
    queryKey: ["cp", "notifications"],
    queryFn: async () => (await clientPortalClient.get("/notifications")).data.data,
    enabled: !!getClientAccessToken(),
    refetchInterval: 60_000,
  });
}

export function useMarkNotificationRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (notificationId: string) => clientPortalClient.post(`/notifications/${notificationId}/read`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cp", "notifications"] }),
  });
}

// --- Internal helper ----------------------------------------------------------
//
// Every CLP route is shaped /clp/client-users/<client_user_id>/...
// (see backend/app/modules/clp/routes.py) -- the backend's own
// `_get_client_user_or_404` rejects any id here that isn't the
// caller's own (a client token may only ever act as itself), so this
// always resolves to "self" from the JWT itself rather than trusting
// a cached profile fetch that might not have completed yet.
function meId(): string {
  const token = getClientAccessToken();
  if (!token) return "";
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return payload.user_id || payload.sub || "";
  } catch {
    return "";
  }
}
