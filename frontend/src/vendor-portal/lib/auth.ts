// Deliberately separate storage keys from every other session in
// this app -- a vendor-portal session is a structurally different
// credential (backend/app/modules/vnp/routes.py issues a token with
// its own `is_portal_user: true` claim, via a wholly separate
// /v1/vnp/auth/* endpoint family). Same real reasoning as
// subcontractor-portal/lib/auth.ts's own docstring.
const ACCESS_TOKEN_KEY = "vp_access_token";
const REFRESH_TOKEN_KEY = "vp_refresh_token";

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
 * meId() and replicated in subcontractor-portal/lib/auth.ts. */
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
