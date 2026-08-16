// Local SQLite database (via Drift) mirroring server data for the
// logged-in user's assigned projects (SRS Section 3.5).
//
// Writes are queued locally with a client-generated UUID and a monotonic
// local timestamp, then synced via a batched POST /v1/mfa/sync-batch when
// connectivity is available (see lib/sync/sync_service.dart). Field names
// below are verified against the real backend, not guessed:
// backend/app/modules/exe/models.py:DailySiteDiary and
// backend/app/modules/mfa/services.py:_create_exe_daily_site_diary,
// which is the real payload shape the server actually accepts.
//
// Run `dart run build_runner build` after changing tables below to
// regenerate app_database.g.dart.
import 'package:drift/drift.dart';

part 'app_database.g.dart';

/// Local mirror of a subset of exe_daily_site_diaries (server table) --
/// both diaries pulled from the server for reference and diaries
/// captured offline, not yet synced.
class DailySiteDiaries extends Table {
  TextColumn get clientUuid => text()(); // primary de-dupe key, matches server client_record_id
  TextColumn get projectId => text()();
  DateTimeColumn get diaryDate => dateTime()();
  IntColumn get workforcePresentCount => integer().nullable()();
  TextColumn get equipmentOnSiteSummary => text().nullable()();
  TextColumn get narrative => text().nullable()();
  // Mirrors the real server status column exactly (draft|submitted|...) --
  // see DIARY_STATUSES in backend/app/modules/exe/models.py -- rather
  // than a boolean, since the real lifecycle has more than two states.
  TextColumn get status => text().withDefault(const Constant('draft'))();
  // Null until this device's copy has been confirmed synced -- see
  // SyncQueueEntries.status for the entry that carries this record.
  TextColumn get serverRecordId => text().nullable()();

  @override
  Set<Column> get primaryKey => {clientUuid};
}

/// Outbound queue of not-yet-synced local writes across all entity types.
class SyncQueueEntries extends Table {
  TextColumn get id => text()();
  TextColumn get targetModule => text()(); // e.g. "EXE", "HSE", "AST" -- matches SyncQueueEntry.target_module
  TextColumn get targetEntityType => text()(); // e.g. "exe_daily_site_diary" -- matches TARGET_ENTITY_TYPES
  TextColumn get clientRecordId => text()(); // idempotency key -- matches SyncQueueEntry.client_record_id
  TextColumn get operation => text()(); // create | update
  TextColumn get payloadJson => text()();
  DateTimeColumn get deviceTimestamp => dateTime()();
  TextColumn get status => text().withDefault(const Constant('pending'))(); // pending|syncing|synced|conflict
  TextColumn get rejectionReason => text().nullable()();

  @override
  Set<Column> get primaryKey => {id};
}

/// Conflicts surfaced by the server -- never silently discarded. Mirrors
/// backend/app/modules/mfa/models.py:ConflictRecord, fetched via
/// GET /v1/mfa/conflicts for on-device review.
class ConflictRecords extends Table {
  TextColumn get id => text()(); // server-assigned ConflictRecord.id
  TextColumn get syncQueueEntryId => text()();
  TextColumn get conflictType => text()(); // concurrent_update|validation_failure|permission_denied
  TextColumn get clientPayloadJson => text()();
  TextColumn get serverCurrentStateJson => text().nullable()();
  TextColumn get status => text().withDefault(const Constant('unresolved'))(); // unresolved|resolved

  @override
  Set<Column> get primaryKey => {id};
}

@DriftDatabase(tables: [DailySiteDiaries, SyncQueueEntries, ConflictRecords])
class AppDatabase extends _$AppDatabase {
  AppDatabase(super.e);

  @override
  int get schemaVersion => 1;

  /// Today's diary for a project, if one has been captured locally
  /// yet (offline-created or already pulled down after a prior sync).
  Future<DailySiteDiary?> diaryForProjectAndDate(String projectId, DateTime date) {
    final dayStart = DateTime(date.year, date.month, date.day);
    return (select(dailySiteDiaries)
          ..where((d) => d.projectId.equals(projectId) & d.diaryDate.equals(dayStart)))
        .getSingleOrNull();
  }

  Stream<List<SyncQueueEntry>> watchPendingSyncEntries() {
    return (select(syncQueueEntries)..where((e) => e.status.equals('pending'))).watch();
  }

  Stream<int> watchUnresolvedConflictCount() {
    final query = selectOnly(conflictRecords)..addColumns([conflictRecords.id.count()]);
    query.where(conflictRecords.status.equals('unresolved'));
    return query.map((row) => row.read(conflictRecords.id.count()) ?? 0).watchSingle();
  }
}
