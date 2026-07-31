// Background sync service (SRS Section 3.5 / 6.3).
//
// - Uploads queued local writes via POST /v1/sync/batch (max 500 records
//   per batch, per Section 6.6), each carrying an Idempotency-Key so a
//   retried request cannot create a duplicate record.
// - Pulls incremental server changes via GET /v1/sync/pull?since=<cursor>.
// - Never silently drops a conflicting write; conflicts are stored in
//   ConflictRecords for user review (MFA business rule, Section 4.24).
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:dio/dio.dart';

class SyncService {
  final Dio _dio;
  final Connectivity _connectivity;

  SyncService(this._dio, this._connectivity);

  Future<bool> get isOnline async {
    final result = await _connectivity.checkConnectivity();
    return result.any((r) => r != ConnectivityResult.none);
  }

  /// Uploads all pending SyncQueueEntries, chunked to the server's max
  /// batch size, then pulls incremental changes.
  Future<void> runSync() async {
    if (!await isOnline) return;

    // TODO:
    // 1. Read pending SyncQueueEntries from AppDatabase (status == 'pending'),
    //    chunked to <= 500 records.
    // 2. POST each chunk to /v1/sync/batch with a per-record Idempotency-Key.
    // 3. Per response: mark 'accepted' entries synced, write 'conflict'
    //    entries into ConflictRecords for review, retry failures with
    //    exponential backoff.
    // 4. GET /v1/sync/pull?since=<last_server_cursor> and merge into local
    //    mirror tables.
  }
}
