import { useEffect, useState } from "react";
import { subcontractorPortalClient, getSubcontractorPortalErrorMessage } from "./api/client";
import { getPortalUserId, getPortalRefreshToken, setPortalTokens, clearPortalSession } from "./lib/auth";
import type { SubcontractAgreement, ProgressEntry, PaymentCertificate, Claim, PortalUser } from "./types";

/** Real login, backed by POST /v1/scp/auth/login (built earlier this
 * session -- previously genuinely missing from the backend entirely,
 * see docs/SUBCONTRACTOR_VENDOR_PORTAL_GAPS.md). */
export async function loginSubcontractor(email: string, password: string): Promise<void> {
  const res = await subcontractorPortalClient.post("/scp/auth/login", { email, password });
  setPortalTokens(res.data.access_token, res.data.refresh_token);
}

export async function logoutSubcontractor(): Promise<void> {
  try {
    const refreshToken = getPortalRefreshToken();
    if (refreshToken) {
      await subcontractorPortalClient.post(
        "/scp/auth/logout",
        {},
        { headers: { Authorization: `Bearer ${refreshToken}` } }
      );
    }
  } catch {
    // Real, deliberate: logout still clears the local session even if
    // the real revoke call fails (network error, already-expired
    // token) -- the person's own browser session ends either way.
  } finally {
    clearPortalSession();
  }
}

export function useSubcontractorProfile() {
  const [profile, setProfile] = useState<PortalUser | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    subcontractorPortalClient
      .get("/scp/auth/me")
      .then((res) => setProfile(res.data))
      .catch((err) => setError(getSubcontractorPortalErrorMessage(err)));
  }, []);

  return { profile, error };
}

export async function changeSubcontractorPassword(currentPassword: string, newPassword: string): Promise<void> {
  await subcontractorPortalClient.post("/scp/auth/me/password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
}

/** Real agreement list, backed by GET
 * /v1/scp/portal-users/<id>/agreements (built alongside this
 * frontend -- previously genuinely missing; the only prior listing
 * endpoint was staff-only and tenant-wide with no subcontractor
 * filter at all). */
export function useAgreements() {
  const [agreements, setAgreements] = useState<SubcontractAgreement[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const userId = getPortalUserId();
    if (!userId) {
      setError("Not signed in.");
      setLoading(false);
      return;
    }
    subcontractorPortalClient
      .get(`/scp/portal-users/${userId}/agreements`)
      .then((res) => setAgreements(res.data.data))
      .catch((err) => setError(getSubcontractorPortalErrorMessage(err)))
      .finally(() => setLoading(false));
  }, []);

  return { agreements, error, loading };
}

export function useAgreement(agreementId: string | undefined) {
  const [agreement, setAgreement] = useState<SubcontractAgreement | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const userId = getPortalUserId();
    if (!userId || !agreementId) {
      setLoading(false);
      return;
    }
    subcontractorPortalClient
      .get(`/scp/portal-users/${userId}/agreements/${agreementId}`)
      .then((res) => setAgreement(res.data))
      .catch((err) => setError(getSubcontractorPortalErrorMessage(err)))
      .finally(() => setLoading(false));
  }, [agreementId]);

  return { agreement, error, loading };
}

/** Real progress-entry history, backed by GET
 * /v1/scp/portal-users/<id>/progress-entries?agreement_id=... (a real,
 * required query param -- the backend route raises a 400 without it,
 * confirmed directly against app/modules/scp/routes.py). */
export function useProgressEntries(agreementId: string | undefined) {
  const [entries, setEntries] = useState<ProgressEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  function reload() {
    const userId = getPortalUserId();
    if (!userId || !agreementId) return;
    subcontractorPortalClient
      .get(`/scp/portal-users/${userId}/progress-entries`, { params: { agreement_id: agreementId } })
      .then((res) => setEntries(res.data.data))
      .catch((err) => setError(getSubcontractorPortalErrorMessage(err)));
  }

  useEffect(reload, [agreementId]);

  return { entries, error, reload };
}

export async function submitProgress(input: { agreement_id: string; scope_item_id?: string; submitted_quantity: string }): Promise<ProgressEntry> {
  const userId = getPortalUserId();
  const res = await subcontractorPortalClient.post(`/scp/portal-users/${userId}/progress-entries`, input);
  return res.data;
}

export function usePaymentCertificates(agreementId: string | undefined) {
  const [certificates, setCertificates] = useState<PaymentCertificate[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const userId = getPortalUserId();
    if (!userId || !agreementId) return;
    subcontractorPortalClient
      .get(`/scp/portal-users/${userId}/payment-certificates`, { params: { agreement_id: agreementId } })
      .then((res) => setCertificates(res.data.data))
      .catch((err) => setError(getSubcontractorPortalErrorMessage(err)));
  }, [agreementId]);

  return { certificates, error };
}

export function useClaims(agreementId: string | undefined) {
  const [claims, setClaims] = useState<Claim[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  function reload() {
    const userId = getPortalUserId();
    if (!userId || !agreementId) return;
    subcontractorPortalClient
      .get(`/scp/portal-users/${userId}/claims`, { params: { agreement_id: agreementId } })
      .then((res) => setClaims(res.data.data))
      .catch((err) => setError(getSubcontractorPortalErrorMessage(err)));
  }

  useEffect(reload, [agreementId]);

  return { claims, error, reload };
}

export async function submitClaim(input: {
  agreement_id: string;
  claim_type: string;
  description: string;
  claimed_amount?: string;
  claimed_days?: number;
}): Promise<Claim> {
  const userId = getPortalUserId();
  const res = await subcontractorPortalClient.post(`/scp/portal-users/${userId}/claims`, input);
  return res.data;
}
