// API client -- every endpoint here is verified against the real
// backend routes, not guessed. See:
//   backend/app/auth/routes.py       (login/refresh)
//   backend/app/modules/mfa/routes.py (sync-batch/sync-status/conflicts)
//
// Correcting two real mistakes the original scaffold's comments made:
// the sync endpoint is POST /v1/mfa/sync-batch, not /v1/sync/batch,
// and there is no pull-sync endpoint at all in this backend -- MFA's
// real scope (per its own module docstring) is push-only: device
// captures -> server. Nothing here pretends a pull endpoint exists.
import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Set this to the real deployed API's base URL before building --
/// e.g. "https://siteforge-api.onrender.com/v1". Left as a plain
/// constant rather than a build-time --dart-define for now, matching
/// how small this app is; revisit once there's a real staging vs.
/// production distinction to configure.
const String kApiBaseUrl = "https://siteforge-api.onrender.com/v1";

class ApiClient {
  final Dio dio;
  final FlutterSecureStorage _storage;

  ApiClient({FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage(),
        dio = Dio(BaseOptions(baseUrl: kApiBaseUrl, connectTimeout: const Duration(seconds: 15))) {
    dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        final token = await _storage.read(key: 'access_token');
        if (token != null) options.headers['Authorization'] = 'Bearer $token';
        handler.next(options);
      },
      onError: (error, handler) async {
        // A 401 here means the access token is expired or invalid --
        // this app does not attempt a silent refresh-and-retry yet
        // (the same real bug class documented in this project's own
        // web frontend history is worth being deliberate about, not
        // rushed: see README.md's session notes on the token-refresh
        // bug that silently corrupted stored credentials for months).
        // For now: surface the failure, let the UI route back to
        // login rather than guess.
        handler.next(error);
      },
    ));
  }

  // --- Auth (backend/app/auth/routes.py) --------------------------------------

  Future<void> login(String email, String password) async {
    final response = await dio.post('/auth/login', data: {'email': email, 'password': password});
    final accessToken = response.data['access_token'] as String;
    final refreshToken = response.data['refresh_token'] as String;
    await _storage.write(key: 'access_token', value: accessToken);
    await _storage.write(key: 'refresh_token', value: refreshToken);
  }

  Future<void> logout() async {
    await _storage.delete(key: 'access_token');
    await _storage.delete(key: 'refresh_token');
  }

  Future<bool> get isLoggedIn async => (await _storage.read(key: 'access_token')) != null;

  // --- Sync (backend/app/modules/mfa/routes.py) --------------------------------

  /// Submits a batch of locally-captured records. Each entry is either
  /// applied (status "synced") or surfaced as a conflict -- the real
  /// server never silently drops one; see SyncBatchResult below for
  /// how to read the response.
  Future<List<SyncEntryResult>> submitSyncBatch({
    required String deviceId,
    required List<Map<String, dynamic>> entries,
  }) async {
    final response = await dio.post('/mfa/sync-batch', data: {'device_id': deviceId, 'entries': entries});
    final data = response.data['data'] as List;
    return data.map((e) => SyncEntryResult.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<Map<String, int>> getSyncStatus({String? deviceId}) async {
    final response = await dio.get('/mfa/sync-status', queryParameters: deviceId != null ? {'device_id': deviceId} : null);
    return Map<String, int>.from(response.data as Map);
  }

  Future<List<Map<String, dynamic>>> getConflicts() async {
    final response = await dio.get('/mfa/conflicts');
    return List<Map<String, dynamic>>.from(response.data['data'] as List);
  }
}

/// Mirrors backend/app/modules/mfa/schemas.py:SyncQueueEntrySchema's
/// real dumped fields exactly.
class SyncEntryResult {
  final String id;
  final String clientRecordId;
  final String targetEntityType;
  final String status; // pending | synced | conflict | rejected
  final String? serverRecordId;
  final String? rejectionReason;

  SyncEntryResult({
    required this.id,
    required this.clientRecordId,
    required this.targetEntityType,
    required this.status,
    this.serverRecordId,
    this.rejectionReason,
  });

  factory SyncEntryResult.fromJson(Map<String, dynamic> json) => SyncEntryResult(
        id: json['id'] as String,
        clientRecordId: json['client_record_id'] as String,
        targetEntityType: json['target_entity_type'] as String,
        status: json['status'] as String,
        serverRecordId: json['server_record_id'] as String?,
        rejectionReason: json['rejection_reason'] as String?,
      );
}
