import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'screens/today_screen.dart';

/// SiteForge Mobile Field App (SRS Module 24).
///
/// Offline-first by design (SRS Section 2.4 / 3.5): the app maintains a
/// local SQLite database (see lib/db/) mirroring the subset of server
/// data relevant to the logged-in user's assigned projects, and queues
/// writes locally for background sync (see lib/sync/).
void main() {
  runApp(const ProviderScope(child: SiteForgeApp()));
}

class SiteForgeApp extends StatelessWidget {
  const SiteForgeApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SiteForge Field',
      theme: ThemeData(useMaterial3: true, colorSchemeSeed: const Color(0xFF1F6FEB)),
      home: const TodayScreen(),
    );
  }
}
