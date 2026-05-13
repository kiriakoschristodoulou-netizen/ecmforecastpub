// lib/providers/update_provider.dart
//
// Riverpod providers for the version-check flow.
// Fetched once on app start and on explicit invalidation; the home
// screen banner reads from updateStatusProvider.

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/update_service.dart';

final updateServiceProvider = Provider<UpdateService>((ref) {
  final service = UpdateService();
  ref.onDispose(service.dispose);
  return service;
});

/// Async provider for the current update status.
/// Null is never returned - either the future resolves with an
/// UpdateStatus (whether or not an update exists) or it errors.
/// UI reads via AsyncValue and ignores errors silently (a failed
/// update check shouldn't disrupt the app).
final updateStatusProvider = FutureProvider<UpdateStatus>((ref) async {
  final service = ref.watch(updateServiceProvider);
  return service.check();
});
