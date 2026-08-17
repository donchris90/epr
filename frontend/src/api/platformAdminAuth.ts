// Deliberately separate from lib/auth.ts's ACCESS_TOKEN_KEY. A
// platform-admin token and a tenant-user access_token are structurally
// different credentials (see backend/app/platform_admin/routes.py's
// module docstring -- no tenant_id claim, a real is_platform_admin
// claim instead) and must never share a storage key: if they did, a
// platform admin visiting the ordinary app, or a tenant user visiting
// this dashboard, could silently overwrite the other's session.
const PLATFORM_ADMIN_TOKEN_KEY = "platform_admin_token";

export function getPlatformAdminToken(): string | null {
  return localStorage.getItem(PLATFORM_ADMIN_TOKEN_KEY);
}

export function setPlatformAdminToken(token: string) {
  localStorage.setItem(PLATFORM_ADMIN_TOKEN_KEY, token);
}

export function clearPlatformAdminToken() {
  localStorage.removeItem(PLATFORM_ADMIN_TOKEN_KEY);
}

export function isPlatformAdminAuthenticated(): boolean {
  return !!getPlatformAdminToken();
}
