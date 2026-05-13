// lib/providers/date_format_provider.dart
//
// User-selectable date format for display throughout the app.
// JSON schema always stores ISO 8601; formatting is per-user, per-device.

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'preferences_provider.dart';

/// One user-selectable date format. Each option pairs a display label
/// (what the Settings UI shows) with an intl pattern (what DateFormat uses).
class DateFormatChoice {
  final String displayLabel;
  final String pattern;

  const DateFormatChoice(this.displayLabel, this.pattern);
}

/// The fixed list of choices. Add new options here; the Settings screen
/// renders them as radio tiles in order.
const List<DateFormatChoice> dateFormatChoices = [
  DateFormatChoice('12 May 2026', 'd MMM yyyy'),
  DateFormatChoice('May 12, 2026', 'MMM d, yyyy'),
  DateFormatChoice('2026-05-12', 'yyyy-MM-dd'),
  DateFormatChoice('12/05/2026', 'dd/MM/yyyy'),
];

const String defaultDateFormatPattern = 'd MMM yyyy';

class DateFormatNotifier extends StateNotifier<String> {
  DateFormatNotifier(this._prefs) : super(_load(_prefs));

  final SharedPreferences _prefs;
  static const _storageKey = 'date_format_pattern_v1';

  static String _load(SharedPreferences prefs) {
    final stored = prefs.getString(_storageKey);
    if (stored == null) return defaultDateFormatPattern;
    // Validate against known patterns; fall back to default if stored
    // value is no longer in the choice list (forward-compat for choice
    // list changes).
    final known = dateFormatChoices.any((c) => c.pattern == stored);
    return known ? stored : defaultDateFormatPattern;
  }

  Future<void> setPattern(String pattern) async {
    state = pattern;
    await _prefs.setString(_storageKey, pattern);
  }
}

final dateFormatProvider =
    StateNotifierProvider<DateFormatNotifier, String>((ref) {
  final prefs = ref.watch(sharedPreferencesProvider);
  return DateFormatNotifier(prefs);
});
