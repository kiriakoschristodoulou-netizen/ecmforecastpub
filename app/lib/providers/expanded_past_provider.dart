// lib/providers/expanded_past_provider.dart
//
// Whether the user has tapped "Show earlier forecasts" to reveal past
// forecasts on the home screen. Default: collapsed (past hidden).
// State does not persist across app restarts - opening the app shows
// upcoming first, every time.

import 'package:flutter_riverpod/flutter_riverpod.dart';

final expandedPastProvider = StateProvider<bool>((ref) => false);
