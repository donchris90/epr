import 'package:flutter/material.dart';

import 'api/api_client.dart';
import 'screens/login_screen.dart';
import 'screens/today_screen.dart';
import 'theme/app_theme.dart';

/// SiteForge Mobile Field App (SRS Module 24).
///
/// Offline-first by design (SRS Section 2.4 / 3.5): the app maintains a
/// local SQLite database (see lib/db/) mirroring the subset of server
/// data relevant to the logged-in user's assigned projects, and queues
/// writes locally for background sync (see lib/sync/).
void main() {
  runApp(const SiteForgeApp());
}

class SiteForgeApp extends StatelessWidget {
  const SiteForgeApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SiteForge Field',
      theme: buildSiteForgeTheme(),
      home: const _AuthGate(),
    );
  }
}

/// Routes to TodayScreen if a token is already stored, otherwise
/// LoginScreen -- a real check, not just always starting at login.
class _AuthGate extends StatefulWidget {
  const _AuthGate();

  @override
  State<_AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<_AuthGate> {
  final _apiClient = ApiClient();
  bool _isLoading = true;
  bool _isLoggedIn = false;

  @override
  void initState() {
    super.initState();
    _check();
  }

  Future<void> _check() async {
    final loggedIn = await _apiClient.isLoggedIn;
    if (!mounted) return;
    setState(() {
      _isLoggedIn = loggedIn;
      _isLoading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    return _isLoggedIn ? TodayScreen(apiClient: _apiClient) : LoginScreen(apiClient: _apiClient);
  }
}
