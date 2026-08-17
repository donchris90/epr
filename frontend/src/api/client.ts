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
