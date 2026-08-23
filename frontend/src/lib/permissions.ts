/** Real permission access from the current staff session's own JWT --
 * the same manual-decode pattern already established in
 * client-portal/hooks.ts's meId(), applied here for the main
 * (internal staff) app, which previously had no equivalent utility at
 * all: every existing page just let the backend's 403 surface as a
 * plain error, with nothing hiding UI proactively based on
 * permissions.
 *
 * This is a UX convenience only -- the real authorization boundary is
 * @require_permission on the backend (backend/app/workflow/routes.py),
 * which rejects an unauthorized request regardless of what this
 * function returns. Never trust this alone for anything that matters. */
function decodeAccessToken(): Record<string, unknown> | null {
  const token = localStorage.getItem("access_token");
  if (!token) return null;
  try {
    return JSON.parse(atob(token.split(".")[1]));
  } catch {
    return null;
  }
}

export function getMyPermissions(): string[] {
  const payload = decodeAccessToken();
  const permissions = payload?.permissions;
  return Array.isArray(permissions) ? permissions : [];
}

/** A caller holding the real "*" wildcard permission (see
 * backend/app/org/services.py's own privilege-escalation guard, which
 * treats "*" as full access) can do anything -- checked here the same
 * way the backend does, not just an exact string match. */
export function hasPermission(permission: string): boolean {
  const permissions = getMyPermissions();
  return permissions.includes("*") || permissions.includes(permission);
}
