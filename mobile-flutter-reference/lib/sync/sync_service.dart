// Background sync service (SRS Section 3.5 / MFA-08, MFA-09).
//
// - Uploads queued local writes via POST /v1/mfa/sync-batch (the real
//   verified endpoint -- the old scaffold's comment guessed
//   /v1/sync/batch, which does not exist), each carrying its
//   client_record_id as the idempotency key so a retried request
//   cannot create a duplicate server record (verified server-side:
//   backend/tests/test_mfa_diary_sync.py's idempotency test).
// - There is no pull-sync endpoint in this backend at all -- MFA's
//   real scope (per its own module docstring) is push-only: device
//   captures -> server. This service does not pretend one exists.
// - Never silently drops a conflicting write; conflicts come back
//   from the server as status "conflict" and are stored locally in
//   ConflictRecords for user review (SRS business rule).
import 'dart:convert';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:drift/drift.dart';

import '../api/api_client.dart';
import '../db/app_database.dart';

/// The server's own real batch-size ceiling isn't documented in the
/// code checked for this pass -- 100 is a conservative, deliberately
/// small default chosen to keep any single request small on a likely-
/// poor field connection, not a verified server-enforced number. Worth
/// confirming against the real limit before this matters in practice.
const int kMaxBatchSize = 100;

class SyncService {
  final ApiClient _apiClient;
  final AppDatabase _db;
  final Connectivity _connectivity;
  final String deviceId;

  SyncService(this._apiClient, this._db, this._connectivity, {required this.deviceId});

  Future<bool> get isOnline async {
    final result = await _connectivity.checkConnectivity();
    return result.any((r) => r != ConnectivityResult.none);
  }

  /// Uploads all pending SyncQueueEntries, chunked to kMaxBatchSize.
  /// Returns the number of entries that ended up synced, so a caller
  /// (e.g. a manual "sync now" button) can show real feedback rather
  /// than a generic "done".
  Future<SyncRunResult> runSync() async {
    if (!await isOnline) {
      return SyncRunResult(attempted: 0, synced: 0, conflicted: 0, skippedOffline: true);
    }

    final pending = await (_db.select(_db.syncQueueEntries)..where((e) => e.status.equals('pending'))).get();
    if (pending.isEmpty) {
      return SyncRunResult(attempted: 0, synced: 0, conflicted: 0, skippedOffline: false);
    }

    var synced = 0;
    var conflicted = 0;

    for (var i = 0; i < pending.length; i += kMaxBatchSize) {
      final end = i + kMaxBatchSize > pending.length ? pending.length : i + kMaxBatchSize;
      final chunk = pending.sublist(i, end);

      // Mark this chunk "syncing" locally before the request, so a UI
      // watching syncQueueEntries can show real in-flight state, not
      // just "pending" the whole time the request is in the air.
      for (final entry in chunk) {
        await (_db.update(_db.syncQueueEntries)..where((e) => e.id.equals(entry.id)))
            .write(const SyncQueueEntriesCompanion(status: Value('syncing')));
      }

      final entries = chunk
          .map((e) => {
                'client_record_id': e.clientRecordId,
                'target_module': e.targetModule,
                'target_entity_type': e.targetEntityType,
                'operation': e.operation,
                'payload': jsonDecode(e.payloadJson),
                'device_timestamp': e.deviceTimestamp.toUtc().toIso8601String(),
              })
          .toList();

      try {
        final results = await _apiClient.submitSyncBatch(deviceId: deviceId, entries: entries);

        for (final result in results) {
          final matching = chunk.firstWhere((e) => e.clientRecordId == result.clientRecordId);

          await (_db.update(_db.syncQueueEntries)..where((e) => e.id.equals(matching.id))).write(
            SyncQueueEntriesCompanion(
              status: Value(result.status),
              rejectionReason: Value(result.rejectionReason),
            ),
          );

          if (result.status == 'synced') {
            synced++;
            if (matching.targetEntityType == 'exe_daily_site_diary') {
              await (_db.update(_db.dailySiteDiaries)..where((d) => d.clientUuid.equals(matching.clientRecordId)))
                  .write(DailySiteDiariesCompanion(
                status: const Value('synced'),
                serverRecordId: Value(result.serverRecordId),
              ));
            }
          } else if (result.status == 'conflict') {
            conflicted++;
          }
        }
      } on Exception {
        // A network-level failure mid-batch (not a per-entry conflict
        // response, an actual failed request -- dropped connection,
        // timeout, 5xx) -- leave this chunk's entries as "pending"
        // again so the next sync attempt picks them back up, rather
        // than stranding them at "syncing" forever.
        for (final entry in chunk) {
          await (_db.update(_db.syncQueueEntries)..where((e) => e.id.equals(entry.id)))
              .write(const SyncQueueEntriesCompanion(status: Value('pending')));
        }
      }
    }

    return SyncRunResult(attempted: pending.length, synced: synced, conflicted: conflicted, skippedOffline: false);
  }

  /// Pulls the server's current conflict list into the local cache,
  /// for on-device review (GET /v1/mfa/conflicts -- a real read, not
  /// a pull-sync of general data; see the module docstring above for
  /// why no such general pull endpoint exists).
  Future<void> refreshConflicts() async {
    if (!await isOnline) return;

    final serverConflicts = await _apiClient.getConflicts();
    for (final c in serverConflicts) {
      await _db.into(_db.conflictRecords).insertOnConflictUpdate(
            ConflictRecordsCompanion.insert(
              id: c['id'] as String,
              syncQueueEntryId: c['sync_queue_entry_id'] as String,
              conflictType: c['conflict_type'] as String,
              clientPayloadJson: jsonEncode(c['client_payload']),
              serverCurrentStateJson:
                  Value(c['server_current_state'] != null ? jsonEncode(c['server_current_state']) : null),
              status: Value(c['status'] as String? ?? 'unresolved'),
            ),
          );
    }
  }
}

class SyncRunResult {
  final int attempted;
  final int synced;
  final int conflicted;
  final bool skippedOffline;

  SyncRunResult({required this.attempted, required this.synced, required this.conflicted, required this.skippedOffline});
}
