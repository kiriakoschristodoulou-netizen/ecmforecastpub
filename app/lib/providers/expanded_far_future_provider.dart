// lib/providers/expanded_far_future_provider.dart
//
// In-memory state for whether the user has expanded the "far future"
// section of the home screen (forecasts more than 10 years out).
//
// Resets on app restart by design: most users won't care about
// 2056/2104/2170 forecasts on every launch. Symmetric with
// expandedPastProvider (which hides forecasts >60 days old by default).

import 'package:flutter_riverpod/flutter_riverpod.dart';

/// True when far-future forecasts (>10 years from today) are shown.
/// False (default) hides them behind a "Show N far-future forecasts" toggle.
final expandedFarFutureProvider = StateProvider<bool>((ref) => false);
