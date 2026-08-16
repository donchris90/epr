// Matches frontend/src/styles/tokens.css exactly -- the same
// blueprint-navy, caution-amber design language as the web app,
// not a generic Material default. Replaces the old scaffold's
// unrelated colorSchemeSeed(0xFF1F6FEB).
import 'package:flutter/material.dart';

class SiteForgeColors {
  static const navy950 = Color(0xFF0B121B);
  static const navy900 = Color(0xFF101A26);
  static const navy800 = Color(0xFF172333);
  static const navy700 = Color(0xFF223247);
  static const navy600 = Color(0xFF34495F);
  static const navy400 = Color(0xFF7690A6);
  static const navy200 = Color(0xFFC3D2DE);

  static const paper = Color(0xFFF7F8F6);
  static const paperDim = Color(0xFFECEEEA);
  static const line = Color(0xFFDDE1DE);

  static const amber = Color(0xFFD99A2B);
  static const amberDim = Color(0xFFF2E2BD);
  static const steel = Color(0xFF3B6E8F);
  static const steelDim = Color(0xFFDBE8EF);
  static const green = Color(0xFF3F8F5F);
  static const greenDim = Color(0xFFDCEFE2);
  static const brick = Color(0xFFB8452E);
  static const brickDim = Color(0xFFF5DDD6);
}

ThemeData buildSiteForgeTheme() {
  final colorScheme = ColorScheme.fromSeed(
    seedColor: SiteForgeColors.navy900,
    primary: SiteForgeColors.navy900,
    secondary: SiteForgeColors.amber,
    error: SiteForgeColors.brick,
    surface: SiteForgeColors.paper,
  );

  return ThemeData(
    useMaterial3: true,
    colorScheme: colorScheme,
    scaffoldBackgroundColor: SiteForgeColors.paper,
    appBarTheme: const AppBarTheme(
      backgroundColor: SiteForgeColors.navy900,
      foregroundColor: Colors.white,
      elevation: 0,
    ),
    cardTheme: CardThemeData(
      color: Colors.white,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(3),
        side: const BorderSide(color: SiteForgeColors.line),
      ),
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: SiteForgeColors.navy900,
        foregroundColor: Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(3)),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: Colors.white,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(3),
        borderSide: const BorderSide(color: SiteForgeColors.line),
      ),
    ),
  );
}

/// A small, fixed-position banner showing pending/conflict counts --
/// deliberately always visible when there's anything outstanding,
/// not tucked into a settings screen. A field user needs to know at
/// a glance whether today's captures have actually reached the
/// server yet.
class SyncStatusBanner extends StatelessWidget {
  final int pendingCount;
  final int conflictCount;
  final bool isOnline;

  const SyncStatusBanner({super.key, required this.pendingCount, required this.conflictCount, required this.isOnline});

  @override
  Widget build(BuildContext context) {
    if (pendingCount == 0 && conflictCount == 0 && isOnline) return const SizedBox.shrink();

    final Color background;
    final String message;
    if (conflictCount > 0) {
      background = SiteForgeColors.brickDim;
      message = '$conflictCount item${conflictCount == 1 ? '' : 's'} need${conflictCount == 1 ? 's' : ''} your review';
    } else if (!isOnline) {
      background = SiteForgeColors.amberDim;
      message = 'Offline — $pendingCount item${pendingCount == 1 ? '' : 's'} waiting to sync';
    } else {
      background = SiteForgeColors.steelDim;
      message = 'Syncing $pendingCount item${pendingCount == 1 ? '' : 's'}…';
    }

    return Container(
      width: double.infinity,
      color: background,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      child: Text(message, style: const TextStyle(fontWeight: FontWeight.w600)),
    );
  }
}
