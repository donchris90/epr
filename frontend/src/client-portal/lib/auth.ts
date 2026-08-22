// Deliberately separate storage keys from lib/auth.ts's own
// "access_token"/"refresh_token" -- a client-portal session and an
// internal staff session are structurally different credentials
// (backend/app/modules/clp/routes.py issues a token with its own
// `is_client: true` claim, via a wholly separate /v1/clp/auth/*
// endpoint family — see that module's docstring for why). Sharing a
// storage key would let a staff member who is also, say, testing the
// client portal in another tab silently clobber one session with the
// other. Same reasoning as PLATFORM_ADMIN_TOKEN_KEY in
// lib/platformAdminAuth.ts, extended to a real two-token
// (access + refresh) session rather than a single opaque token.
const ACCESS_TOKEN_KEY = "cp_access_token";
const REFRESH_TOKEN_KEY = "cp_refresh_token";
// Cached at login purely for display (sidebar/topbar) -- never used
// for any access-control decision, the backend/RLS is what's
// authoritative, this is cosmetic only.
const ORG_NAME_KEY = "cp_org_name";

export function getClientAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getClientRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function setClientTokens(accessToken: string, refreshToken: string) {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

export function setClientOrgName(name: string) {
  localStorage.setItem(ORG_NAME_KEY, name);
}

export function getClientOrgName(): string | null {
  return localStorage.getItem(ORG_NAME_KEY);
}

export function clearClientSession() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(ORG_NAME_KEY);
}

export function isClientAuthenticated(): boolean {
  return !!getClientAccessToken();
}
