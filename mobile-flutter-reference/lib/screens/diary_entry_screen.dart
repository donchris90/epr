import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:drift/drift.dart' as drift;
import 'package:uuid/uuid.dart';

import '../db/app_database.dart';
import '../sync/sync_service.dart';
import '../theme/app_theme.dart';

/// Captures today's Daily Site Diary (SRS 7.2.2) for one project.
/// Always saves locally first, then queues for sync -- the whole
/// point of offline-first: a save must never fail just because the
/// device has no signal. See sync/sync_service.dart for the upload
/// half, and backend/app/modules/mfa/services.py:_create_exe_daily_site_diary
/// for exactly what the server does with this once it arrives.
class DiaryEntryScreen extends StatefulWidget {
  final AppDatabase db;
  final SyncService syncService;
  final String projectId;
  final DateTime diaryDate;
  final DailySiteDiary? existing;

  const DiaryEntryScreen({
    super.key,
    required this.db,
    required this.syncService,
    required this.projectId,
    required this.diaryDate,
    this.existing,
  });

  @override
  State<DiaryEntryScreen> createState() => _DiaryEntryScreenState();
}

class _DiaryEntryScreenState extends State<DiaryEntryScreen> {
  late final TextEditingController _workforceController;
  late final TextEditingController _equipmentController;
  late final TextEditingController _narrativeController;
  bool _isSaving = false;

  @override
  void initState() {
    super.initState();
    _workforceController = TextEditingController(text: widget.existing?.workforcePresentCount?.toString() ?? '');
    _equipmentController = TextEditingController(text: widget.existing?.equipmentOnSiteSummary ?? '');
    _narrativeController = TextEditingController(text: widget.existing?.narrative ?? '');
  }

  @override
  void dispose() {
    _workforceController.dispose();
    _equipmentController.dispose();
    _narrativeController.dispose();
    super.dispose();
  }

  bool get _isEditingSyncedEntry => widget.existing?.status == 'synced';

  Future<void> _save() async {
    setState(() => _isSaving = true);

    // Reuses the existing local record's own clientUuid if editing a
    // draft already captured today, rather than minting a new one --
    // otherwise a second save of the same day's diary would look like
    // an entirely different record to the server's idempotency check.
    final clientRecordId = widget.existing?.clientUuid ?? const Uuid().v4();
    final dayStart = DateTime(widget.diaryDate.year, widget.diaryDate.month, widget.diaryDate.day);

    final workforceCount = int.tryParse(_workforceController.text.trim());
    final equipmentSummary = _equipmentController.text.trim();
    final narrative = _narrativeController.text.trim();

    final payload = {
      'project_id': widget.projectId,
      'diary_date': dayStart.toIso8601String().split('T').first, // YYYY-MM-DD, matches the server's db.Date field
      if (workforceCount != null) 'workforce_present_count': workforceCount,
      if (equipmentSummary.isNotEmpty) 'equipment_on_site_summary': equipmentSummary,
      if (narrative.isNotEmpty) 'narrative': narrative,
    };

    await widget.db.into(widget.db.dailySiteDiaries).insertOnConflictUpdate(
          DailySiteDiariesCompanion.insert(
            clientUuid: clientRecordId,
            projectId: widget.projectId,
            diaryDate: dayStart,
            workforcePresentCount: drift.Value(workforceCount),
            equipmentOnSiteSummary: drift.Value(equipmentSummary.isEmpty ? null : equipmentSummary),
            narrative: drift.Value(narrative.isEmpty ? null : narrative),
            status: const drift.Value('draft'),
          ),
        );

    await widget.db.into(widget.db.syncQueueEntries).insertOnConflictUpdate(
          SyncQueueEntriesCompanion.insert(
            id: const Uuid().v4(),
            targetModule: 'EXE',
            targetEntityType: 'exe_daily_site_diary',
            clientRecordId: clientRecordId,
            operation: 'create',
            payloadJson: jsonEncode(payload),
            deviceTimestamp: DateTime.now(),
          ),
        );

    // A real, immediate attempt if there's connectivity -- but the
    // save above already happened regardless of what this returns.
    // A failed or offline sync attempt here is not a failed save.
    final result = await widget.syncService.runSync();

    if (!mounted) return;
    setState(() => _isSaving = false);

    final message = result.skippedOffline
        ? 'Saved on this device. Will sync once you\'re back online.'
        : result.conflicted > 0
            ? 'Saved, but the server found a conflict — check the Conflicts screen.'
            : 'Saved and synced.';

    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Daily Site Diary')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (_isEditingSyncedEntry)
              Container(
                padding: const EdgeInsets.all(12),
                margin: const EdgeInsets.only(bottom: 16),
                decoration: BoxDecoration(
                  color: SiteForgeColors.amberDim,
                  borderRadius: BorderRadius.circular(3),
                ),
                child: const Text(
                  'This diary already synced. Changes here will be sent as a new '
                  'sync entry — the server does not yet support editing an '
                  'already-synced diary through this app; use the web app for that.',
                ),
              ),
            Text('Project: ${widget.projectId}', style: const TextStyle(color: SiteForgeColors.navy600)),
            Text(
              'Date: ${widget.diaryDate.toIso8601String().split('T').first}',
              style: const TextStyle(color: SiteForgeColors.navy600),
            ),
            const SizedBox(height: 20),
            TextField(
              controller: _workforceController,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'Workforce present today'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _equipmentController,
              maxLines: 3,
              decoration: const InputDecoration(labelText: 'Equipment on site', hintText: 'e.g. 2 excavators, 1 crane'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _narrativeController,
              maxLines: 6,
              decoration: const InputDecoration(labelText: 'Narrative', alignLabelWithHint: true),
            ),
            const SizedBox(height: 24),
            ElevatedButton(
              onPressed: _isSaving ? null : _save,
              child: _isSaving
                  ? const SizedBox(
                      height: 20,
                      width: 20,
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                    )
                  : const Text('Save'),
            ),
          ],
        ),
      ),
    );
  }
}
