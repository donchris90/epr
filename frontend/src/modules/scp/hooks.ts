import { useMutation, useQuery, useQueryClient, useQueries } from "@tanstack/react-query";
import { apiClient } from "../../api/client";
import { useScpStore } from "./store";
import type {
  Agreement,
  Claim,
  ClaimType,
  PaymentCertificate,
  PortalSession,
  ProgressEntry,
  ScopeItem,
  Subcontractor,
} from "./types";

function usePortalUserId(): string | undefined {
  return useScpStore((s) => s.session?.id);
}

// --- Access / identity -----------------------------------------------------------

export function useSubcontractorOptions() {
  return useQuery({
    queryKey: ["scp", "subcontractor-options"],
    queryFn: async () => (await apiClient.get("/sub/subcontractors")).data.data as Subcontractor[],
  });
}

export function useRegisterPortalUser() {
  return useMutation({
    mutationFn: async (payload: { subcontractor_id: string; email: string }) =>
      (await apiClient.post("/scp/portal-users", payload)).data as PortalSession & { is_active: boolean },
  });
}

// --- Agreements --------------------------------------------------------------------

/**
 * The SCP API has no "list my agreements" endpoint (every SCP read
 * requires agreement_id up front), so agreements come from Module 12's
 * list and are narrowed to this subcontractor client-side. That needs
 * sub:read, which a real external subcontractor login should not hold --
 * this is the one function to replace with a dedicated
 * GET /scp/portal-users/<id>/agreements once that exists. Ownership is
 * still enforced server-side on every SCP call regardless.
 */
export function useMyAgreements() {
  const subcontractorId = useScpStore((s) => s.session?.subcontractor_id);
  return useQuery({
    queryKey: ["scp", "agreements", subcontractorId],
    enabled: !!subcontractorId,
    queryFn: async () => {
      const all = (await apiClient.get("/sub/agreements")).data.data as Agreement[];
      return all.filter((a) => a.subcontractor_id === subcontractorId);
    },
  });
}

export function useScopeItems(agreementId?: string | null) {
  return useQuery({
    queryKey: ["scp", "scope-items", agreementId],
    enabled: !!agreementId,
    queryFn: async () => (await apiClient.get(`/sub/agreements/${agreementId}/scope-items`)).data.data as ScopeItem[],
  });
}

// --- Progress -------------------------------------------------------------------------

export function useProgressEntries(agreementId?: string | null) {
  const portalUserId = usePortalUserId();
  return useQuery({
    queryKey: ["scp", portalUserId, "progress", agreementId],
    enabled: !!portalUserId && !!agreementId,
    queryFn: async () =>
      (await apiClient.get(`/scp/portal-users/${portalUserId}/progress-entries`, { params: { agreement_id: agreementId } }))
        .data.data as ProgressEntry[],
  });
}

export function useSubmitProgress() {
  const qc = useQueryClient();
  const portalUserId = usePortalUserId();
  return useMutation({
    mutationFn: async (payload: { agreement_id: string; scope_item_id: string | null; submitted_quantity: string }) =>
      (await apiClient.post(`/scp/portal-users/${portalUserId}/progress-entries`, payload)).data as ProgressEntry,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["scp", portalUserId, "progress"] }),
  });
}

// --- Payment certificates (read-only) ---------------------------------------------------

/** Drafts are internal working documents; only issued certificates are shown to a subcontractor. */
const issuedOnly = (rows: PaymentCertificate[]) => rows.filter((c) => c.status !== "draft");

export function usePaymentCertificates(agreementId?: string | null) {
  const portalUserId = usePortalUserId();
  return useQuery({
    queryKey: ["scp", portalUserId, "certificates", agreementId],
    enabled: !!portalUserId && !!agreementId,
    queryFn: async () =>
      (await apiClient.get(`/scp/portal-users/${portalUserId}/payment-certificates`, { params: { agreement_id: agreementId } }))
        .data.data as PaymentCertificate[],
    select: issuedOnly,
  });
}

// --- Claims ---------------------------------------------------------------------------------

export function useClaims(agreementId?: string | null) {
  const portalUserId = usePortalUserId();
  return useQuery({
    queryKey: ["scp", portalUserId, "claims", agreementId],
    enabled: !!portalUserId && !!agreementId,
    queryFn: async () =>
      (await apiClient.get(`/scp/portal-users/${portalUserId}/claims`, { params: { agreement_id: agreementId } })).data.data as Claim[],
  });
}

export function useSubmitClaim() {
  const qc = useQueryClient();
  const portalUserId = usePortalUserId();
  return useMutation({
    mutationFn: async (payload: {
      agreement_id: string;
      claim_type: ClaimType;
      description: string;
      claimed_amount: string | null;
      claimed_days: number | null;
    }) => (await apiClient.post(`/scp/portal-users/${portalUserId}/claims`, payload)).data as Claim,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["scp", portalUserId, "claims"] }),
  });
}

// --- Dashboard roll-up (all of this subcontractor's agreements) --------------------------------

function useRollup<T>(kind: "progress-entries" | "payment-certificates" | "claims", key: string, agreementIds: string[]) {
  const portalUserId = usePortalUserId();
  return useQueries({
    queries: agreementIds.map((agreementId) => ({
      queryKey: ["scp", portalUserId, key, agreementId],
      enabled: !!portalUserId,
      queryFn: async () =>
        (await apiClient.get(`/scp/portal-users/${portalUserId}/${kind}`, { params: { agreement_id: agreementId } })).data.data as T[],
    })),
    combine: (results) => ({
      data: results.flatMap((r) => r.data ?? []),
      isLoading: results.some((r) => r.isLoading),
      isError: results.some((r) => r.isError),
    }),
  });
}

export function usePortalRollup(agreementIds: string[]) {
  const progress = useRollup<ProgressEntry>("progress-entries", "progress", agreementIds);
  const certificates = useRollup<PaymentCertificate>("payment-certificates", "certificates", agreementIds);
  const claims = useRollup<Claim>("claims", "claims", agreementIds);
  return {
    progress: progress.data,
    certificates: issuedOnly(certificates.data),
    claims: claims.data,
    isLoading: progress.isLoading || certificates.isLoading || claims.isLoading,
    isError: progress.isError || certificates.isError || claims.isError,
  };
}
