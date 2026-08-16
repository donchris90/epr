// Background sync service (SRS Section 3.5 / MFA-08, MFA-09).
//
// - Uploads queued local writes via POST /v1/mfa/sync-batch, each
//   carrying its client_record_id as the idempotency key so a
//   retried request cannot create a duplicate server record
//   (verified server-side: backend/tests/test_mfa_diary_sync.py's
//   idempotency test).
// - There is no pull-sync endpoint in this backend at all -- MFA's
//   real scope (per its own module docstring) is push-only: device
//   captures -> server. This service does not pretend one exists.
// - Never silently drops a conflicting write; conflicts come back
//   from the server as status "conflict" and are stored locally for
//   user review.
import * as SQLite from "expo-sqlite";
import * as Network from "expo-network";

import { ApiClient, SyncEntryInput } from "../api/apiClient";
import {
  getPendingSyncEntries,
  updateSyncEntryStatus,
  markDiarySyncedByClientUuid,
  upsertConflict,
  LocalSyncQueueEntry,
} from "../db/database";

// The server's own real batch-size ceiling isn't documented in the
// code checked for this pass -- 100 is a conservative, deliberately
// small default chosen to keep any single request small on a likely-
// poor field connection, not a verified server-enforced number.
const MAX_BATCH_SIZE = 100;

export interface SyncRunResult {
  attempted: number;
  synced: number;
  conflicted: number;
  skippedOffline: boolean;
}

export class SyncService {
  constructor(
    private readonly apiClient: ApiClient,
    private readonly db: SQLite.SQLiteDatabase,
    private readonly deviceId: string
  ) {}

  async isOnline(): Promise<boolean> {
    const state = await Network.getNetworkStateAsync();
    return state.isConnected === true && state.isInternetReachable !== false;
  }

  /** Uploads all pending sync queue entries, chunked to MAX_BATCH_SIZE. */
  async runSync(): Promise<SyncRunResult> {
    if (!(await this.isOnline())) {
      return { attempted: 0, synced: 0, conflicted: 0, skippedOffline: true };
    }

    const pending = await getPendingSyncEntries(this.db);
    if (pending.length === 0) {
      return { attempted: 0, synced: 0, conflicted: 0, skippedOffline: false };
    }

    let synced = 0;
    let conflicted = 0;

    for (let i = 0; i < pending.length; i += MAX_BATCH_SIZE) {
      const chunk = pending.slice(i, i + MAX_BATCH_SIZE);

      for (const entry of chunk) {
        await updateSyncEntryStatus(this.db, entry.id, "syncing");
      }

      const entries: SyncEntryInput[] = chunk.map((e) => ({
        client_record_id: e.client_record_id,
        target_module: e.target_module,
        target_entity_type: e.target_entity_type,
        operation: e.operation as "create" | "update",
        payload: JSON.parse(e.payload_json),
        device_timestamp: e.device_timestamp,
      }));

      try {
        const results = await this.apiClient.submitSyncBatch(this.deviceId, entries);

        for (const result of results) {
          const matching = chunk.find((e) => e.client_record_id === result.client_record_id);
          if (!matching) continue;

          await updateSyncEntryStatus(this.db, matching.id, result.status, result.rejection_reason);

          if (result.status === "synced") {
            synced++;
            if (matching.target_entity_type === "exe_daily_site_diary" && result.server_record_id) {
              await markDiarySyncedByClientUuid(this.db, matching.client_record_id, result.server_record_id);
            }
          } else if (result.status === "conflict") {
            conflicted++;
          }
        }
      } catch {
        // A network-level failure mid-batch (not a per-entry conflict
        // response, an actual failed request) -- leave this chunk's
        // entries as "pending" again so the next sync attempt picks
        // them back up, rather than stranding them at "syncing"
        // forever.
        for (const entry of chunk) {
          await updateSyncEntryStatus(this.db, entry.id, "pending");
        }
      }
    }

    return { attempted: pending.length, synced, conflicted, skippedOffline: false };
  }

  /** Pulls the server's current conflict list into the local cache,
   * for on-device review (GET /v1/mfa/conflicts -- a real read, not
   * a pull-sync of general data; see the module docstring above for
   * why no such general pull endpoint exists). */
  async refreshConflicts(): Promise<void> {
    if (!(await this.isOnline())) return;

    const serverConflicts = await this.apiClient.getConflicts();
    for (const c of serverConflicts) {
      await upsertConflict(this.db, {
        id: c.id,
        sync_queue_entry_id: c.sync_queue_entry_id,
        conflict_type: c.conflict_type,
        client_payload_json: JSON.stringify(c.client_payload),
        server_current_state_json: c.server_current_state ? JSON.stringify(c.server_current_state) : null,
        status: c.status,
      });
    }
  }
}

export type { LocalSyncQueueEntry };
