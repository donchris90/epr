import 'dart:convert';

import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../theme/app_theme.dart';

/// Shows every unresolved conflict for this tenant, fetched fresh
/// from the server (GET /v1/mfa/conflicts) -- deliberately not read
/// from the local cache alone, since a conflict is exactly the kind
/// of thing where a stale local view is actively unhelpful.
///
/// Real, honest limitation: this screen displays conflicts and lets
/// a user see both sides (their own captured data vs. what the
/// server actually has), but does not yet call
/// POST /v1/mfa/conflicts/<id>/resolve -- that write action needs a
/// real UI for constructing a resolution payload matching what each
/// conflict_type actually needs, which is real, separate follow-up
/// work, not attempted here. Today, resolving a conflict means going
/// to the web app.
class ConflictsScreen extends StatefulWidget {
  final ApiClient apiClient;

  const ConflictsScreen({super.key, required this.apiClient});

  @override
  State<ConflictsScreen> createState() => _ConflictsScreenState();
}

class _ConflictsScreenState extends State<ConflictsScreen> {
  List<Map<String, dynamic>> _conflicts = [];
  bool _isLoading = true;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });
    try {
      final conflicts = await widget.apiClient.getConflicts();
      if (!mounted) return;
      setState(() => _conflicts = conflicts.where((c) => c['status'] == 'unresolved').toList());
    } catch (_) {
      if (!mounted) return;
      setState(() => _errorMessage = 'Could not load conflicts. Check your connection.');
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Conflicts')),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _isLoading
            ? const Center(child: CircularProgressIndicator())
            : _errorMessage != null
                ? Center(child: Text(_errorMessage!))
                : _conflicts.isEmpty
                    ? ListView(
                        children: const [
                          Padding(
                            padding: EdgeInsets.all(32),
                            child: Text('No unresolved conflicts.', textAlign: TextAlign.center),
                          ),
                        ],
                      )
                    : ListView.builder(
                        padding: const EdgeInsets.all(16),
                        itemCount: _conflicts.length,
                        itemBuilder: (context, index) => _ConflictCard(conflict: _conflicts[index]),
                      ),
      ),
    );
  }
}

class _ConflictCard extends StatelessWidget {
  final Map<String, dynamic> conflict;

  const _ConflictCard({required this.conflict});

  @override
  Widget build(BuildContext context) {
    final clientPayload = conflict['client_payload'] as Map<String, dynamic>?;
    final serverState = conflict['server_current_state'] as Map<String, dynamic>?;
    final conflictType = conflict['conflict_type'] as String? ?? 'unknown';

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(color: SiteForgeColors.brickDim, borderRadius: BorderRadius.circular(3)),
                  child: Text(
                    conflictType.replaceAll('_', ' '),
                    style: const TextStyle(color: SiteForgeColors.brick, fontWeight: FontWeight.w600, fontSize: 12),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            const Text('What you captured:', style: TextStyle(fontWeight: FontWeight.w600)),
            Text(clientPayload != null ? const JsonEncoder.withIndent('  ').convert(clientPayload) : '—'),
            if (serverState != null) ...[
              const SizedBox(height: 8),
              const Text('What the server has:', style: TextStyle(fontWeight: FontWeight.w600)),
              Text(const JsonEncoder.withIndent('  ').convert(serverState)),
            ],
            const SizedBox(height: 8),
            const Text(
              'Resolving this isn\'t available in the app yet — please use the web app to decide what happens next.',
              style: TextStyle(color: SiteForgeColors.navy600, fontStyle: FontStyle.italic),
            ),
          ],
        ),
      ),
    );
  }
}
