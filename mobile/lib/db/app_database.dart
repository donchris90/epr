// Local SQLite database (via Drift) mirroring server data for the
// logged-in user's assigned projects (SRS Section 3.5).
//
// Writes are queued locally with a client-generated UUID and a monotonic
// local timestamp, then synced via a batched POST /v1/sync/batch when
// connectivity is available (see lib/sync/sync_service.dart).
//
// TODO: run `dart run build_runner build` after defining tables below to
// generate app_database.g.dart.
import 'package:drift/drift.dart';

part 'app_database.g.dart';

/// Local mirror of a subset of daily_site_diaries (server table).
class DailySiteDiaries extends Table {
  TextColumn get clientUuid => text()(); // primary de-dupe key, matches server client_uuid
  TextColumn get projectId => text()();
  DateTimeColumn get diaryDate => dateTime()();
  TextColumn get weatherJson => text().nullable()();
  TextColumn get narrative => text().nullable()();
  BoolColumn get signed => boolean().withDefault(const Constant(false))();

  @override
  Set<Column> get primaryKey => {clientUuid};
}

/// Outbound queue of not-yet-synced local writes across all entity types.
class SyncQueueEntries extends Table {
  TextColumn get id => text()();
  TextColumn get entity => text()(); // e.g. "daily_site_diary"
  TextColumn get clientUuid => text()();
  TextColumn get operation => text()(); // create | update | delete
  TextColumn get payloadJson => text()();
  DateTimeColumn get clientTimestamp => dateTime()();
  TextColumn get status => text().withDefault(const Constant('pending'))(); // pending|syncing|synced|conflict

  @override
  Set<Column> get primaryKey => {id};
}

/// Conflicts surfaced by the server per the last-writer-wins-with-audit-trail
/// rule (SRS Section 3.5) — never silently discarded.
class ConflictRecords extends Table {
  TextColumn get id => text()();
  TextColumn get entity => text()();
  TextColumn get clientUuid => text()();
  TextColumn get localPayloadJson => text()();
  TextColumn get serverPayloadJson => text()();
  BoolColumn get resolved => boolean().withDefault(const Constant(false))();

  @override
  Set<Column> get primaryKey => {id};
}

@DriftDatabase(tables: [DailySiteDiaries, SyncQueueEntries, ConflictRecords])
class AppDatabase extends _$AppDatabase {
  AppDatabase(super.e);

  @override
  int get schemaVersion => 1;
}
