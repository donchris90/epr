// Local SQLite database mirroring server data for offline capture
// (SRS Section 3.5). Plain SQL via expo-sqlite -- API calls below
// verified directly against the installed package's own type
// definitions (node_modules/expo-sqlite/build/SQLiteDatabase.d.ts),
// not assumed from memory.
//
// Field names mirror the real backend exactly: verified against
// backend/app/modules/exe/models.py:DailySiteDiary and
// backend/app/modules/mfa/services.py:_create_exe_daily_site_diary,
// the real payload shape the server actually accepts.
import * as SQLite from "expo-sqlite";

export interface LocalDiary {
  client_uuid: string;
  project_id: string;
  diary_date: string; // YYYY-MM-DD
  workforce_present_count: number | null;
  equipment_on_site_summary: string | null;
  narrative: string | null;
  status: string; // draft | synced -- local tracking only; mirrors DIARY_STATUSES loosely
  server_record_id: string | null;
}

export interface LocalSyncQueueEntry {
  id: string;
  target_module: string;
  target_entity_type: string;
  client_record_id: string;
  operation: string;
  payload_json: string;
  device_timestamp: string;
  status: string; // pending | syncing | synced | conflict
  rejection_reason: string | null;
}

export interface LocalConflict {
  id: string;
  sync_queue_entry_id: string;
  conflict_type: string;
  client_payload_json: string;
  server_current_state_json: string | null;
  status: string; // unresolved | resolved
}

let dbInstance: SQLite.SQLiteDatabase | null = null;

export async function getDatabase(): Promise<SQLite.SQLiteDatabase> {
  if (dbInstance) return dbInstance;

  const db = await SQLite.openDatabaseAsync("siteforge_field.db");
  await db.execAsync(`
    PRAGMA journal_mode = WAL;

    CREATE TABLE IF NOT EXISTS daily_site_diaries (
      client_uuid TEXT PRIMARY KEY NOT NULL,
      project_id TEXT NOT NULL,
      diary_date TEXT NOT NULL,
      workforce_present_count INTEGER,
      equipment_on_site_summary TEXT,
      narrative TEXT,
      status TEXT NOT NULL DEFAULT 'draft',
      server_record_id TEXT
    );

    CREATE TABLE IF NOT EXISTS sync_queue_entries (
      id TEXT PRIMARY KEY NOT NULL,
      target_module TEXT NOT NULL,
      target_entity_type TEXT NOT NULL,
      client_record_id TEXT NOT NULL,
      operation TEXT NOT NULL,
      payload_json TEXT NOT NULL,
      device_timestamp TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'pending',
      rejection_reason TEXT
    );

    CREATE TABLE IF NOT EXISTS conflict_records (
      id TEXT PRIMARY KEY NOT NULL,
      sync_queue_entry_id TEXT NOT NULL,
      conflict_type TEXT NOT NULL,
      client_payload_json TEXT NOT NULL,
      server_current_state_json TEXT,
      status TEXT NOT NULL DEFAULT 'unresolved'
    );
  `);

  dbInstance = db;
  return db;
}

export async function upsertLocalDiary(db: SQLite.SQLiteDatabase, diary: LocalDiary): Promise<void> {
  await db.runAsync(
    `INSERT INTO daily_site_diaries
       (client_uuid, project_id, diary_date, workforce_present_count, equipment_on_site_summary, narrative, status, server_record_id)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?)
     ON CONFLICT(client_uuid) DO UPDATE SET
       workforce_present_count = excluded.workforce_present_count,
       equipment_on_site_summary = excluded.equipment_on_site_summary,
       narrative = excluded.narrative,
       status = excluded.status,
       server_record_id = excluded.server_record_id`,
    [
      diary.client_uuid,
      diary.project_id,
      diary.diary_date,
      diary.workforce_present_count,
      diary.equipment_on_site_summary,
      diary.narrative,
      diary.status,
      diary.server_record_id,
    ]
  );
}

export async function getDiaryForProjectAndDate(
  db: SQLite.SQLiteDatabase,
  projectId: string,
  diaryDate: string
): Promise<LocalDiary | null> {
  return db.getFirstAsync<LocalDiary>(
    `SELECT * FROM daily_site_diaries WHERE project_id = ? AND diary_date = ?`,
    [projectId, diaryDate]
  );
}

export async function insertSyncQueueEntry(db: SQLite.SQLiteDatabase, entry: LocalSyncQueueEntry): Promise<void> {
  await db.runAsync(
    `INSERT INTO sync_queue_entries
       (id, target_module, target_entity_type, client_record_id, operation, payload_json, device_timestamp, status, rejection_reason)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    [
      entry.id,
      entry.target_module,
      entry.target_entity_type,
      entry.client_record_id,
      entry.operation,
      entry.payload_json,
      entry.device_timestamp,
      entry.status,
      entry.rejection_reason,
    ]
  );
}

export async function getPendingSyncEntries(db: SQLite.SQLiteDatabase): Promise<LocalSyncQueueEntry[]> {
  return db.getAllAsync<LocalSyncQueueEntry>(`SELECT * FROM sync_queue_entries WHERE status = 'pending'`);
}

export async function updateSyncEntryStatus(
  db: SQLite.SQLiteDatabase,
  id: string,
  status: string,
  rejectionReason: string | null = null
): Promise<void> {
  await db.runAsync(`UPDATE sync_queue_entries SET status = ?, rejection_reason = ? WHERE id = ?`, [
    status,
    rejectionReason,
    id,
  ]);
}

export async function markDiarySyncedByClientUuid(
  db: SQLite.SQLiteDatabase,
  clientUuid: string,
  serverRecordId: string
): Promise<void> {
  await db.runAsync(`UPDATE daily_site_diaries SET status = 'synced', server_record_id = ? WHERE client_uuid = ?`, [
    serverRecordId,
    clientUuid,
  ]);
}

export async function countPendingSyncEntries(db: SQLite.SQLiteDatabase): Promise<number> {
  const row = await db.getFirstAsync<{ count: number }>(
    `SELECT COUNT(*) as count FROM sync_queue_entries WHERE status = 'pending'`
  );
  return row?.count ?? 0;
}

export async function countUnresolvedConflicts(db: SQLite.SQLiteDatabase): Promise<number> {
  const row = await db.getFirstAsync<{ count: number }>(
    `SELECT COUNT(*) as count FROM conflict_records WHERE status = 'unresolved'`
  );
  return row?.count ?? 0;
}

export async function upsertConflict(db: SQLite.SQLiteDatabase, conflict: LocalConflict): Promise<void> {
  await db.runAsync(
    `INSERT INTO conflict_records (id, sync_queue_entry_id, conflict_type, client_payload_json, server_current_state_json, status)
     VALUES (?, ?, ?, ?, ?, ?)
     ON CONFLICT(id) DO UPDATE SET status = excluded.status`,
    [
      conflict.id,
      conflict.sync_queue_entry_id,
      conflict.conflict_type,
      conflict.client_payload_json,
      conflict.server_current_state_json,
      conflict.status,
    ]
  );
}
