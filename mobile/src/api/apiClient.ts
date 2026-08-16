// API client -- every endpoint here is verified against the real
// backend routes, not guessed. See:
//   backend/app/auth/routes.py        (login)
//   backend/app/modules/mfa/routes.py (sync-batch/sync-status/conflicts)
//
// Two real mistakes an earlier attempt at this app's scaffold made,
// corrected here: the sync endpoint is POST /v1/mfa/sync-batch, not
// /v1/sync/batch, and there is no pull-sync endpoint at all in this
// backend -- MFA's real scope (per its own module docstring) is
// push-only: device captures -> server. Nothing here pretends a pull
// endpoint exists.
import axios, { AxiosInstance, AxiosError } from "axios";
import * as SecureStore from "expo-secure-store";

// Set this to the real deployed API's base URL before building --
// e.g. "https://siteforge-api.onrender.com/v1".
export const API_BASE_URL = "https://siteforge-api.onrender.com/v1";

const ACCESS_TOKEN_KEY = "sf_access_token";
const REFRESH_TOKEN_KEY = "sf_refresh_token";

export interface SyncEntryInput {
  client_record_id: string;
  target_module: string;
  target_entity_type: string;
  operation: "create" | "update";
  payload: Record<string, unknown>;
  device_timestamp: string;
}

export interface SyncEntryResult {
  id: string;
  client_record_id: string;
  target_entity_type: string;
  status: "pending" | "synced" | "conflict" | "rejected";
  server_record_id: string | null;
  rejection_reason: string | null;
}

export interface ConflictRecord {
  id: string;
  sync_queue_entry_id: string;
  conflict_type: string;
  client_payload: Record<string, unknown>;
  server_current_state: Record<string, unknown> | null;
  status: "unresolved" | "resolved";
  resolution: Record<string, unknown> | null;
}

export class ApiClient {
  readonly http: AxiosInstance;

  constructor() {
    this.http = axios.create({ baseURL: API_BASE_URL, timeout: 15000 });

    this.http.interceptors.request.use(async (config) => {
      const token = await SecureStore.getItemAsync(ACCESS_TOKEN_KEY);
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });

    this.http.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        // A 401 here means the access token is expired or invalid --
        // this app does not attempt a silent refresh-and-retry yet
        // (the same real bug class documented in this project's own
        // web frontend history is worth being deliberate about, not
        // rushed: see README.md's session notes on the token-refresh
        // bug that once silently corrupted stored credentials by
        // hitting the wrong URL). For now: surface the failure, let
        // the UI route back to login rather than guess.
        return Promise.reject(error);
      }
    );
  }

  // --- Auth (backend/app/auth/routes.py) --------------------------------------

  async login(email: string, password: string): Promise<void> {
    const response = await this.http.post<{ access_token: string; refresh_token: string }>("/auth/login", {
      email,
      password,
    });
    await SecureStore.setItemAsync(ACCESS_TOKEN_KEY, response.data.access_token);
    await SecureStore.setItemAsync(REFRESH_TOKEN_KEY, response.data.refresh_token);
  }

  async logout(): Promise<void> {
    await SecureStore.deleteItemAsync(ACCESS_TOKEN_KEY);
    await SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY);
  }

  async isLoggedIn(): Promise<boolean> {
    const token = await SecureStore.getItemAsync(ACCESS_TOKEN_KEY);
    return token !== null;
  }

  // --- Sync (backend/app/modules/mfa/routes.py) --------------------------------

  /** Submits a batch of locally-captured records. Each entry is either
   * applied (status "synced") or surfaced as a conflict -- the real
   * server never silently drops one. */
  async submitSyncBatch(deviceId: string, entries: SyncEntryInput[]): Promise<SyncEntryResult[]> {
    const response = await this.http.post<{ data: SyncEntryResult[] }>("/mfa/sync-batch", {
      device_id: deviceId,
      entries,
    });
    return response.data.data;
  }

  async getSyncStatus(deviceId?: string): Promise<Record<string, number>> {
    const response = await this.http.get<Record<string, number>>("/mfa/sync-status", {
      params: deviceId ? { device_id: deviceId } : undefined,
    });
    return response.data;
  }

  async getConflicts(): Promise<ConflictRecord[]> {
    const response = await this.http.get<{ data: ConflictRecord[] }>("/mfa/conflicts");
    return response.data.data;
  }
}
