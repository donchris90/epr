import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:connectivity_plus/connectivity_plus.dart';

import '../api/api_client.dart';
import '../db/app_database.dart';
import '../sync/sync_service.dart';
import '../theme/app_theme.dart';
import 'diary_entry_screen.dart';
import 'conflicts_screen.dart';

/// "Today" screen — the mobile home (SRS 7.2.2, Daily Site Diary
/// Flow). Shows the current project's diary status and a persistent
/// offline/sync-status indicator (SRS 7.3 design note).
///
/// Real, honest limitation: project selection here is a plain manual
/// entry, not a picker backed by a verified "my assigned projects"
/// endpoint -- no such endpoint was found and confirmed in the real
/// backend during this pass. A field user types their project ID
/// once; it's remembered locally after that. Replacing this with a
/// real assignment-aware picker is a real, separate piece of
/// follow-up work, not attempted here.
class TodayScreen extends StatefulWidget {
  final ApiClient apiClient;

  const TodayScreen({super.key, required this.apiClient});

  @override
  State<TodayScreen> createState() => _TodayScreenState();
}

class _TodayScreenState extends State<TodayScreen> {
  static const _storage = FlutterSecureStorage();
  late final AppDatabase _db;
  late final SyncService _syncService;

  String? _projectId;
  DailySiteDiary? _todayDiary;
  int _pendingCount = 0;
  int _conflictCount = 0;
  bool _isOnline = true;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _db = AppDatabase();
    _syncService = SyncService(widget.apiClient, _db, Connectivity(), deviceId: 'mobile-device');
    _init();
  }

  Future<void> _init() async {
    final storedProjectId = await _storage.read(key: 'current_project_id');
    setState(() => _projectId = storedProjectId);
    await _refresh();
    setState(() => _isLoading = false);
  }

  Future<void> _refresh() async {
    final online = await _syncService.isOnline;

    DailySiteDiary? diary;
    if (_projectId != null) {
      diary = await _db.diaryForProjectAndDate(_projectId!, DateTime.now());
    }

    final pendingCount = await (_db.select(_db.syncQueueEntries)..where((e) => e.status.equals('pending'))).get();
    final conflictCount = await (_db.select(_db.conflictRecords)..where((c) => c.status.equals('unresolved'))).get();

    if (!mounted) return;
    setState(() {
      _isOnline = online;
      _todayDiary = diary;
      _pendingCount = pendingCount.length;
      _conflictCount = conflictCount.length;
    });
  }

  Future<void> _setProject(String projectId) async {
    await _storage.write(key: 'current_project_id', value: projectId);
    setState(() => _projectId = projectId);
    await _refresh();
  }

  Future<void> _openDiary() async {
    if (_projectId == null) return;
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => DiaryEntryScreen(
          db: _db,
          syncService: _syncService,
          projectId: _projectId!,
          diaryDate: DateTime.now(),
          existing: _todayDiary,
        ),
      ),
    );
    await _refresh();
  }

  Future<void> _manualSync() async {
    final result = await _syncService.runSync();
    await _syncService.refreshConflicts();
    if (!mounted) return;
    await _refresh();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          result.skippedOffline
              ? 'No connection — nothing to sync right now.'
              : 'Synced ${result.synced} of ${result.attempted}${result.conflicted > 0 ? ', ${result.conflicted} need review' : ''}.',
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Today'),
        actions: [
          IconButton(
            icon: const Icon(Icons.warning_amber_rounded),
            tooltip: 'Conflicts',
            onPressed: () async {
              await Navigator.of(context).push(MaterialPageRoute(builder: (_) => ConflictsScreen(apiClient: widget.apiClient)));
              await _refresh();
            },
          ),
          IconButton(icon: const Icon(Icons.sync), tooltip: 'Sync now', onPressed: _manualSync),
        ],
      ),
      body: Column(
        children: [
          SyncStatusBanner(pendingCount: _pendingCount, conflictCount: _conflictCount, isOnline: _isOnline),
          Expanded(
            child: _projectId == null ? _buildProjectPrompt() : _buildTodayBody(),
          ),
        ],
      ),
    );
  }

  Widget _buildProjectPrompt() {
    final controller = TextEditingController();
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text('Which project are you on today?', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
            const SizedBox(height: 12),
            TextField(controller: controller, decoration: const InputDecoration(labelText: 'Project ID')),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: () {
                final value = controller.text.trim();
                if (value.isNotEmpty) _setProject(value);
              },
              child: const Text('Continue'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTodayBody() {
    final status = _todayDiary?.status;
    final statusLabel = status == null
        ? 'Not started'
        : status == 'synced'
            ? 'Synced'
            : status == 'draft'
                ? 'Saved on this device, not yet synced'
                : status;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Project $_projectId', style: const TextStyle(color: SiteForgeColors.navy600)),
                const SizedBox(height: 8),
                const Text('Daily Site Diary', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                const SizedBox(height: 4),
                Text(statusLabel, style: const TextStyle(color: SiteForgeColors.steel)),
                const SizedBox(height: 16),
                ElevatedButton(
                  onPressed: _openDiary,
                  child: Text(_todayDiary == null ? 'Start today\'s diary' : 'Continue today\'s diary'),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        TextButton(
          onPressed: () async {
            await _storage.delete(key: 'current_project_id');
            setState(() => _projectId = null);
          },
          child: const Text('Change project'),
        ),
      ],
    );
  }
}
