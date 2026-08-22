import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";

// VITE_API_BASE_URL matters once frontend and backend are on separate
// domains (e.g. two separate Render services) -- a bare "/v1" only
// resolves correctly when both are on the same origin, which is true
// in local dev only because vite.config.ts's server.proxy forwards
// /v1 to the backend. Falls back to "/v1" so local dev and any
// same-origin deployment (e.g. behind a shared reverse proxy) keep
// working without needing this set at all.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/v1";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/**
 * Backend errors follow RFC 7807 Problem Details ({type, title, status,
 * detail, instance} — see backend/app/utils/errors.py). `detail` is
 * where business-rule specifics live (e.g. "Estimated total 5,500,000
 * exceeds remaining budget 5,000,000"); `title` is the fallback for
 * validation/generic errors that don't set one.
 */
export function getErrorMessage(err: any): string {
  return err?.response?.data?.detail || err?.response?.data?.title || "Something went wrong.";
}

/** True when the request never reached the server at all (offline,
 * DNS failure, CORS, timeout) -- axios sets no `response` in that
 * case, which is the one situation "check your connection" is
 * actually the right advice rather than a generic error. */
export function isNetworkError(err: any): boolean {
  return !!err?.isAxiosError && !err?.response;
}

export function getErrorStatus(err: any): number | undefined {
  return err?.response?.status;
}

/** Short, human title for a status code -- used by ErrorState/
 * QueryState so every screen describes 403/404/409/422/429/500 the
 * same way instead of each page inventing its own wording. 401/402
 * aren't listed: the response interceptor above already redirects
 * for those before a component ever sees the rejected promise. */
export function getErrorTitle(err: any): string {
  if (isNetworkError(err)) return "Network error";
  switch (getErrorStatus(err)) {
    case 403:
      return "You don't have permission to do this";
    case 404:
      return "Not found";
    case 409:
      return "This couldn't be completed";
    case 422:
      return "Check the highlighted fields";
    case 429:
      return "Too many requests";
    case 500:
    case 502:
    case 503:
    case 504:
      return "Something went wrong on our end";
    default:
      return "Something went wrong";
  }
}

/** One-line, situation-appropriate detail to pair with getErrorTitle.
 * Falls back to the backend's own RFC 7807 `detail`/`title` (see
 * getErrorMessage) for anything not called out with special wording
 * below (chiefly 422, where the backend's own detail is usually
 * already the most specific/correct message available). */
export function getErrorDetail(err: any): string {
  if (isNetworkError(err)) return "Check your internet connection and try again.";
  switch (getErrorStatus(err)) {
    case 403:
      return "Your account doesn't have access to this. Contact an administrator if you think this is wrong.";
    case 404:
      return "It may have been moved, deleted, or you may not have access to it.";
    case 409:
      return getErrorMessage(err) || "This conflicts with the current state of the record. Refresh and try again.";
    case 429:
      return "You've made too many requests. Wait a moment and try again.";
    case 500:
    case 502:
    case 503:
    case 504:
      return "This is on us, not you. Try again in a moment.";
    default:
      return getErrorMessage(err);
  }
}

/** Whether a retry action makes sense for this error. Permission and
 * validation errors won't resolve by retrying the same request. */
export function isRetryableError(err: any): boolean {
  const status = getErrorStatus(err);
  return isNetworkError(err) || status === undefined || ![403, 404, 422].includes(status);
}

export interface FieldError {
  field: string;
  message: string;
}

/** Extracts per-field validation errors from a 422 response so forms
 * can highlight the actual offending inputs instead of only showing
 * one generic banner. Backend validation errors (FastAPI/Pydantic
 * style, proxied through the RFC 7807 `detail`) commonly arrive as
 * either `detail: [{loc: [...,"field"], msg}]` or a plain object map
 * `{errors: {field: "message"}}` -- both are handled; anything else
 * yields an empty list and the caller falls back to getErrorMessage. */
export function getFieldErrors(err: any): FieldError[] {
  if (getErrorStatus(err) !== 422) return [];
  const data = err?.response?.data;
  if (Array.isArray(data?.detail)) {
    return data.detail
      .map((d: any) => {
        const loc = Array.isArray(d?.loc) ? d.loc : [];
        const field = loc[loc.length - 1];
        return field ? { field: String(field), message: d.msg || "Invalid value" } : null;
      })
      .filter((v: FieldError | null): v is FieldError => v !== null);
  }
  if (data?.errors && typeof data.errors === "object") {
    return Object.entries(data.errors).map(([field, message]) => ({ field, message: String(message) }));
  }
  return [];
}

// --- Automatic access-token refresh on 401 (SRS Section 6.2) ------------------
//
// The backend issues short-lived (15 min) access tokens by design, so
// a 401 partway through a session is the expected, common case, not
// an edge case -- every request needs a path to recover from it
// transparently rather than dumping the user back to the login screen
// every 15 minutes. The refresh token itself rotates on every use
// (see backend/app/auth/routes.py), so a successful refresh here
// updates BOTH stored tokens, not just the access token.
//
// Concurrency: several requests can hit a 401 around the same moment
// (e.g. a page firing multiple queries at once right as the token
// expires). Without de-duplication, each would try to refresh
// independently -- and since refresh tokens are single-use/rotating,
// only the first would succeed and every other concurrent refresh
// attempt would itself 401, incorrectly logging the user out. A
// single shared in-flight promise makes every concurrent 401 wait for
// the same refresh call and then retry with its result.
let refreshPromise: Promise<string> | null = null;

interface RetryableConfig extends InternalAxiosRequestConfig {
  _retried?: boolean;
}

const REFRESH_EXEMPT_PATHS = ["/auth/login", "/auth/refresh"];

function isRefreshExempt(url?: string): boolean {
  return !!url && REFRESH_EXEMPT_PATHS.some((p) => url.includes(p));
}

function redirectToLogin() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  localStorage.removeItem("tenant_label");
  if (window.location.pathname !== "/login") {
    window.location.href = "/login";
  }
}

// A 402 means the real backend enforcement
// (backend/app/middleware/tenant_context.py) found this tenant's
// trial/subscription has lapsed -- deliberately does NOT clear the
// stored tokens the way redirectToLogin does: the login itself is
// still perfectly valid, only this tenant's access is paused, and
// the subscription-expired page needs that same token to load
// /v1/billing/subscription (an exempt route) and let the user
// actually subscribe.
function redirectToSubscriptionExpired() {
  if (window.location.pathname !== "/subscription-expired") {
    window.location.href = "/subscription-expired";
  }
}

async function performRefresh(): Promise<string> {
  const refreshToken = localStorage.getItem("refresh_token");
  if (!refreshToken) {
    throw new Error("No refresh token available");
  }

  // A plain axios call, not apiClient -- going through apiClient here
  // would re-enter this same response interceptor if the refresh
  // itself ever 401s, which is exactly the recursive case this whole
  // mechanism needs to avoid. Must still use API_BASE_URL explicitly
  // though -- a bare "/v1/auth/refresh" only resolves correctly when
  // frontend and backend share an origin (true in local dev only, via
  // vite.config.ts's proxy). Once they're separate Render services,
  // a relative path here hits siteforge-web's own domain, which has
  // no such route -- Render's SPA rewrite rule then serves back
  // index.html instead of a 404, which gets destructured as
  // {access_token, refresh_token} and silently yields two undefined
  // values. Both get stored anyway (localStorage stringifies
  // undefined to the literal text "undefined"), and every subsequent
  // request sends that as a "Bearer undefined" Authorization header --
  // a token with zero dot-separated segments, which is exactly what
  // produced the real production symptom this fixes: every endpoint
  // works right after login, then fails identically everywhere,
  // silently, once the access token first expires and this refresh
  // path fires for the first time.
  const response = await axios.post(
    `${API_BASE_URL}/auth/refresh`,
    {},
    { headers: { Authorization: `Bearer ${refreshToken}` } }
  );

  const { access_token, refresh_token } = response.data;

  // Fail loudly rather than silently storing garbage -- this is
  // exactly the check that would have caught the bug above at the
  // source, and guards against any future cause of a malformed
  // refresh response (not just this one).
  if (typeof access_token !== "string" || typeof refresh_token !== "string") {
    throw new Error("Refresh response did not contain valid tokens");
  }

  localStorage.setItem("access_token", access_token);
  localStorage.setItem("refresh_token", refresh_token);
  return access_token;
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as RetryableConfig | undefined;

    if (error.response?.status === 402) {
      redirectToSubscriptionExpired();
      return Promise.reject(error);
    }

    const isUnauthorized = error.response?.status === 401;
    const alreadyRetried = originalRequest?._retried;
    const exempt = isRefreshExempt(originalRequest?.url);

    if (!isUnauthorized || alreadyRetried || exempt || !originalRequest) {
      return Promise.reject(error);
    }

    originalRequest._retried = true;

    try {
      // Join the in-flight refresh if one's already running, rather
      // than starting a second one.
      if (!refreshPromise) {
        refreshPromise = performRefresh().finally(() => {
          refreshPromise = null;
        });
      }
      const newAccessToken = await refreshPromise;

      originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
      return apiClient(originalRequest);
    } catch (refreshError) {
      // The refresh token itself is invalid, expired, or revoked --
      // there's no recovery path left except a fresh login.
      redirectToLogin();
      return Promise.reject(refreshError);
    }
  }
);
