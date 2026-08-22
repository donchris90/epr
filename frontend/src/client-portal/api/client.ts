import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";
import {
  getClientAccessToken,
  getClientRefreshToken,
  setClientTokens,
  clearClientSession,
} from "../lib/auth";

// Same base URL resolution as api/client.ts. A genuinely separate
// axios instance from apiClient, not a reuse of it, for the same
// class of reason as platformAdminClient: this instance injects the
// client-portal token (not the staff access_token) and refreshes
// against /v1/clp/auth/refresh (not /v1/auth/refresh) — reusing
// apiClient's interceptor would refresh the wrong session against the
// wrong endpoint entirely, and (see backend/app/auth/routes.py) a
// client-issued refresh token is now explicitly rejected by the
// staff /v1/auth/refresh route regardless.
//
// baseURL is the bare API root (NOT .../clp): every CLP call in
// hooks.ts spells out its own "/clp/..." path, deliberately, because
// this same instance is also used for GET/PATCH /notifications --
// backend/app/notifications/routes.py scopes purely by the token's
// own user_id claim with no permission check at all (see that
// module's own docstring), so a client token is a legitimate caller
// of it completely unmodified, at its real top-level path, not a
// /clp-prefixed proxy of it.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/v1";

export const clientPortalClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

clientPortalClient.interceptors.request.use((config) => {
  const token = getClientAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export function getClientPortalErrorMessage(err: any): string {
  return err?.response?.data?.detail || err?.response?.data?.title || "Something went wrong.";
}

// --- Automatic access-token refresh on 401, same pattern (and same
// concurrency reasoning) as api/client.ts's own interceptor -------------------

let refreshPromise: Promise<string> | null = null;

interface RetryableConfig extends InternalAxiosRequestConfig {
  _retried?: boolean;
}

const REFRESH_EXEMPT_PATHS = ["/clp/auth/login", "/clp/auth/refresh"];

function isRefreshExempt(url?: string): boolean {
  return !!url && REFRESH_EXEMPT_PATHS.some((p) => url.includes(p));
}

function redirectToLogin() {
  clearClientSession();
  if (window.location.pathname !== "/portal/login") {
    window.location.href = "/portal/login?expired=1";
  }
}

async function performRefresh(): Promise<string> {
  const refreshToken = getClientRefreshToken();
  if (!refreshToken) {
    throw new Error("No refresh token available");
  }

  // A plain axios call, not clientPortalClient -- avoids re-entering
  // this same response interceptor if the refresh call itself 401s.
  const response = await axios.post(
    `${API_BASE_URL}/clp/auth/refresh`,
    {},
    { headers: { Authorization: `Bearer ${refreshToken}` } }
  );

  const { access_token, refresh_token } = response.data;
  if (typeof access_token !== "string" || typeof refresh_token !== "string") {
    throw new Error("Refresh response did not contain valid tokens");
  }

  setClientTokens(access_token, refresh_token);
  return access_token;
}

clientPortalClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as RetryableConfig | undefined;
    const isUnauthorized = error.response?.status === 401;
    const alreadyRetried = originalRequest?._retried;
    const exempt = isRefreshExempt(originalRequest?.url);

    if (!isUnauthorized || alreadyRetried || exempt || !originalRequest) {
      return Promise.reject(error);
    }

    originalRequest._retried = true;

    try {
      if (!refreshPromise) {
        refreshPromise = performRefresh().finally(() => {
          refreshPromise = null;
        });
      }
      const newAccessToken = await refreshPromise;
      originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
      return clientPortalClient(originalRequest);
    } catch (refreshError) {
      redirectToLogin();
      return Promise.reject(refreshError);
    }
  }
);
