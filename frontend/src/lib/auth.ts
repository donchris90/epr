const ACCESS_TOKEN_KEY = "access_token";
const REFRESH_TOKEN_KEY = "refresh_token";
const TENANT_LABEL_KEY = "tenant_label";

export function getToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function setTokens(accessToken: string, refreshToken: string, tenantLabel?: string) {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  if (tenantLabel) localStorage.setItem(TENANT_LABEL_KEY, tenantLabel);
}

/** Called by the refresh interceptor after a successful rotation --
 * updates both tokens without touching the stored tenant label. */
export function updateTokensAfterRefresh(accessToken: string, refreshToken: string) {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(TENANT_LABEL_KEY);
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

export function getTenantLabel(): string {
  return localStorage.getItem(TENANT_LABEL_KEY) || "Workspace";
}
