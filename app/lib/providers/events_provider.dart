// lib/providers/events_provider.dart
//
// Riverpod providers that expose the events feed to the UI.
//
// The service layer (FeedService) is stateless and reusable.
// The provider layer wraps it with caching and lifecycle management.

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/events_feed.dart';
import '../services/feed_service.dart';

/// Singleton FeedService instance shared across the app.
/// Created once; the underlying http.Client is reused.
final feedServiceProvider = Provider<FeedService>((ref) {
  final service = FeedService();
  ref.onDispose(service.dispose);
  return service;
});

/// Async provider that fetches the events feed on first read and on
/// every invalidation. UI consumes this via `ref.watch(eventsFeedProvider)`
/// and gets an `AsyncValue<EventsFeed>` to render loading / error / data.
///
/// To force a refresh (e.g., pull-to-refresh gesture):
///   ref.invalidate(eventsFeedProvider);
final eventsFeedProvider = FutureProvider<EventsFeed>((ref) async {
  final service = ref.watch(feedServiceProvider);
  return service.fetchEvents();
});
