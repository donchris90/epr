import 'package:flutter/material.dart';

/// "Today" screen — the mobile home, per SRS Section 7.2.2 (Daily Site
/// Diary Flow). Shows the current project's diary status
/// (not started / in progress / signed) and a persistent, unmissable
/// offline-status indicator (Section 7.3 design note).
class TodayScreen extends StatelessWidget {
  const TodayScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Today')),
      body: const Center(
        child: Padding(
          padding: EdgeInsets.all(24.0),
          child: Text(
            'SiteForge Field — scaffolding in progress.\n\n'
            'TODO: diary status card, quick-actions '
            '(diary entry, material scan, attendance), '
            'and a persistent sync-status banner.',
            textAlign: TextAlign.center,
          ),
        ),
      ),
    );
  }
}
