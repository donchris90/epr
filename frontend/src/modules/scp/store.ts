import { create } from "zustand";
import type { PortalSession } from "./types";

/**
 * Who the portal is acting as, and which agreement is in focus.
 *
 * The SCP API in this codebase addresses a portal user by id in the
 * URL (/scp/portal-users/<id>/...) and runs under a normal staff JWT
 * holding scp:* permissions -- there is no portal login or "who am I"
 * endpoint yet. So the session is held client-side. Everything that
 * depends on that is isolated to this file and hooks.ts
 * (useMyAgreements + the portalUserId plumbing); when a real
 * portal-auth flow lands, only those two files need to change.
 *
 * sessionStorage, not localStorage: a portal identity should not
 * outlive the tab. Every access is try/catch'd since storage can throw
 * (private windows, blocked site data).
 */
const KEY = "scp_portal_session";

function load(): PortalSession | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed?.id && parsed?.subcontractor_id ? (parsed as PortalSession) : null;
  } catch {
    return null;
  }
}

function persist(s: PortalSession | null) {
  try {
    if (s) sessionStorage.setItem(KEY, JSON.stringify(s));
    else sessionStorage.removeItem(KEY);
  } catch {
    /* storage unavailable -- session simply won't survive a reload */
  }
}

interface ScpState {
  session: PortalSession | null;
  agreementId: string | null;
  setSession: (s: PortalSession) => void;
  clearSession: () => void;
  setAgreementId: (id: string | null) => void;
}

export const useScpStore = create<ScpState>((set) => ({
  session: load(),
  agreementId: null,
  setSession: (session) => {
    persist(session);
    set({ session, agreementId: null });
  },
  clearSession: () => {
    persist(null);
    set({ session: null, agreementId: null });
  },
  setAgreementId: (agreementId) => set({ agreementId }),
}));
