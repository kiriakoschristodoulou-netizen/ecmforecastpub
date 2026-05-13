// lib/providers/retrospective.dart
//
// Local-only record of HIT/MISS scores for past forecasts. Stored per
// device in SharedPreferences. Each user's scores are their own; never
// synced anywhere.
//
// State shape: Map<forecastId, RetrospectiveScore>. A forecast with no
// entry in the map is "unflagged" - the user has not scored it.

import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'preferences_provider.dart';

/// Two-tier user-recorded score for a past forecast.
enum RetrospectiveScore {
  hit,
  miss;

  /// Serialized form for SharedPreferences. Stable string regardless of
  /// future enum name changes.
  String get serialized {
    switch (this) {
      case RetrospectiveScore.hit:
        return 'hit';
      case RetrospectiveScore.miss:
        return 'miss';
    }
  }

  static RetrospectiveScore? fromSerialized(String? value) {
    switch (value) {
      case 'hit':
        return RetrospectiveScore.hit;
      case 'miss':
        return RetrospectiveScore.miss;
      default:
        return null;
    }
  }
}

/// Aggregate counts for the HIT-rate display.
class RetrospectiveRates {
  final int total;
  final int hits;

  const RetrospectiveRates({required this.total, required this.hits});

  /// Percentage 0..100. Returns 0 when total is 0 (call sites should
  /// special-case the zero-flagged state for messaging).
  double get percentage => total == 0 ? 0 : (hits * 100.0) / total;
}

class RetrospectiveNotifier
    extends StateNotifier<Map<String, RetrospectiveScore>> {
  RetrospectiveNotifier(this._prefs) : super(_load(_prefs));

  final SharedPreferences _prefs;
  static const _storageKey = 'retrospectives_v1';

  static Map<String, RetrospectiveScore> _load(SharedPreferences prefs) {
    final raw = prefs.getString(_storageKey);
    if (raw == null) return const {};
    try {
      final decoded = jsonDecode(raw);
      if (decoded is! Map) return const {};
      final result = <String, RetrospectiveScore>{};
      decoded.forEach((key, value) {
        if (key is String && value is String) {
          final score = RetrospectiveScore.fromSerialized(value);
          if (score != null) {
            result[key] = score;
          }
        }
      });
      return result;
    } catch (_) {
      // Corrupted storage - start fresh rather than crashing.
      return const {};
    }
  }

  Future<void> _save() async {
    final encoded = jsonEncode(
      state.map((k, v) => MapEntry(k, v.serialized)),
    );
    await _prefs.setString(_storageKey, encoded);
  }

  /// Set a forecast's score. Pass null to clear (user un-scores).
  Future<void> setScore(String forecastId, RetrospectiveScore? score) async {
    final next = Map<String, RetrospectiveScore>.from(state);
    if (score == null) {
      next.remove(forecastId);
    } else {
      next[forecastId] = score;
    }
    state = next;
    await _save();
  }

  /// Lookup helper for the UI.
  RetrospectiveScore? scoreFor(String forecastId) => state[forecastId];

  /// Counts for the HIT-rate display.
  /// Denominator counts only flagged forecasts (HIT or MISS).
  /// Unflagged past forecasts are excluded.
  RetrospectiveRates get rates {
    int hits = 0;
    for (final s in state.values) {
      if (s == RetrospectiveScore.hit) hits++;
    }
    return RetrospectiveRates(total: state.length, hits: hits);
  }
}

final retrospectiveProvider = StateNotifierProvider<RetrospectiveNotifier,
    Map<String, RetrospectiveScore>>((ref) {
  final prefs = ref.watch(sharedPreferencesProvider);
  return RetrospectiveNotifier(prefs);
});
