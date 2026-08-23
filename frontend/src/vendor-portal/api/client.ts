import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";
import { getPortalAccessToken, getPortalRefreshToken, setPortalTokens, clearPortalSession } from "../lib/auth";

// A genuinely separate axios instance -- same reasoning as
// subcontractor-portal/api/client.ts and client-portal/api/client.ts's
// own docstrings: this instance injects the vendor-portal token and
// refreshes against /v1/vnp/auth/refresh specifically.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/v1";

export const vendorPortalClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

vendorPortalClient.interceptors.request.use((config) => {
  const token = getPortalAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export function getVendorPortalErrorMessage(err: any): string {
  return err?.response?.data?.detail || err?.response?.data?.title || "Something went wrong.";
}

// --- Automatic access-token refresh on 401, same pattern as every other
// portal's own interceptor in this codebase -------------------------------

let refreshPromise: Promise<string> | null = null;

interface RetryableConfig extends InternalAxiosRequestConfig {
  _retried?: boolean;
}

const REFRESH_EXEMPT_PATHS = ["/vnp/auth/login", "/vnp/auth/refresh"];

function isRefreshExempt(url?: string): boolean {
  return !!url && REFRESH_EXEMPT_PATHS.some((p) => url.includes(p));
}

function redirectToLogin() {
  clearPortalSession();
  if (window.location.pathname !== "/vendor/login") {
    window.location.href = "/vendor/login?expired=1";
  }
}

async function performRefresh(): Promise<string> {
  const refreshToken = getPortalRefreshToken();
  if (!refreshToken) {
    throw new Error("No refresh token available");
  }

  // A plain axios call, not vendorPortalClient -- avoids re-entering
  // this same response interceptor if the refresh call itself 401s.
  const response = await axios.post(
    `${API_BASE_URL}/vnp/auth/refresh`,
    {},
    { headers: { Authorization: `Bearer ${refreshToken}` } }
  );

  const { access_token, refresh_token } = response.data;
  if (typeof access_token !== "string" || typeof refresh_token !== "string") {
    throw new Error("Refresh response did not contain valid tokens");
  }

  setPortalTokens(access_token, refresh_token);
  return access_token;
}

vendorPortalClient.interceptors.response.use(
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
      return vendorPortalClient(originalRequest);
    } catch (refreshError) {
      redirectToLogin();
      return Promise.reject(refreshError);
    }
  }
);
