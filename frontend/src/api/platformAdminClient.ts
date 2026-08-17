import axios from "axios";
import { getPlatformAdminToken, clearPlatformAdminToken } from "../lib/platformAdminAuth";

// Same base URL resolution as api/client.ts (see that file's comment
// on VITE_API_BASE_URL) -- a genuinely separate axios instance though,
// not a reuse of apiClient, for two real reasons:
//   1. apiClient's request interceptor injects the *tenant-user*
//      access_token; platform-admin requests need the separate
//      platform_admin_token instead (see lib/platformAdminAuth.ts).
//   2. apiClient's response interceptor tries to refresh on 401 using
//      the tenant refresh-token flow (/auth/refresh). The platform-
//      admin login route (backend/app/platform_admin/routes.py) issues
//      only an access_token, no refresh_token -- there is nothing to
//      refresh, so reusing that interceptor here would just throw
//      inside performRefresh() on every 401 instead of doing the right
//      thing, which is: clear the token and send the admin back to
//      /platform-admin/login.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/v1";

export const platformAdminClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

platformAdminClient.interceptors.request.use((config) => {
  const token = getPlatformAdminToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

platformAdminClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const isLoginCall = error.config?.url?.includes("/platform-admin/auth/login");
    if (error.response?.status === 401 && !isLoginCall) {
      clearPlatformAdminToken();
      if (window.location.pathname !== "/platform-admin/login") {
        window.location.href = "/platform-admin/login";
      }
    }
    return Promise.reject(error);
  }
);

export function getPlatformAdminErrorMessage(err: any): string {
  return err?.response?.data?.detail || err?.response?.data?.title || "Something went wrong.";
}
