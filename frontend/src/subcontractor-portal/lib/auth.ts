// Deliberately separate storage keys from lib/auth.ts (staff) and
// client-portal/lib/auth.ts (client) -- a subcontractor-portal
// session is a structurally different credential (backend/app/modules/scp/routes.py
// issues a token with its own `is_portal_user: true` claim, via a
// wholly separate /v1/scp/auth/* endpoint family). Sharing a storage
// key with either would let one session silently clobber the other
// if someone had both open in different tabs.
const ACCESS_TOKEN_KEY = "sp_access_token";
const REFRESH_TOKEN_KEY = "sp_refresh_token";

export function getPortalAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getPortalRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function setPortalTokens(accessToken: string, refreshToken: string) {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

export function clearPortalSession() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

export function isPortalAuthenticated(): boolean {
  return !!getPortalAccessToken();
}

/** Real, minimal identity read from the token itself -- same manual
 * JWT-decode pattern established in client-portal/hooks.ts's own
 * meId(), reused here rather than a separate profile fetch just to
 * know "who am I" for routing/ownership-scoped API calls. */
export function getPortalUserId(): string {
  const token = getPortalAccessToken();
  if (!token) return "";
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return payload.user_id || payload.sub || "";
  } catch {
    return "";
  }
}
