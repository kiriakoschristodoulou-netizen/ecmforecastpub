// lib/providers/preferences_provider.dart
//
// Holds the SharedPreferences instance for all persistent state.
// Initialized in main() before runApp; provided via ProviderScope overrides.
//
// All other providers that need persistence (retrospective scores, date
// format setting, install UUID, etc.) read SharedPreferences through
// this provider rather than awaiting getInstance themselves.

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Read-only SharedPreferences access. Throws if not overridden in main().
/// This deliberate throw catches forgotten init at startup rather than at
/// the moment some screen first tries to read a setting.
final sharedPreferencesProvider = Provider<SharedPreferences>((ref) {
  throw UnimplementedError(
    'sharedPreferencesProvider must be overridden in main() before runApp.',
  );
});
