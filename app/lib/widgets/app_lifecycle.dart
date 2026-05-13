// lib/widgets/app_lifecycle.dart
//
// Wraps the HomeScreen tree and performs three jobs:
//   1. On first frame: requests POST_NOTIFICATIONS permission (Android 13+)
//   2. On first frame: fires telemetry ping (anonymous install + version)
//   3. On every feed update: reschedules notifications
//
// Lives between MaterialApp.home and HomeScreen so its ref.listen is
// active for the app's entire foreground lifetime.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/events_feed.dart';
import '../providers/events_provider.dart';
import '../providers/preferences_provider.dart';
import '../services/notification_scheduler.dart';
import '../services/notification_service.dart';
import '../services/telemetry_service.dart';

class AppLifecycle extends ConsumerStatefulWidget {
  final Widget child;
  const AppLifecycle({super.key, required this.child});

  @override
  ConsumerState<AppLifecycle> createState() => _AppLifecycleState();
}

class _AppLifecycleState extends ConsumerState<AppLifecycle> {
  bool _startupTasksRan = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _runStartupTasks();
    });
  }

  Future<void> _runStartupTasks() async {
    if (_startupTasksRan) return;
    _startupTasksRan = true;

    // Permission request first - if user grants it, notifications can
    // start scheduling immediately when the feed loads.
    await NotificationService.requestPermission();

    // Telemetry ping - fire and forget. Generates UUID on first launch
    // and sends an anonymous install + version record to the worker.
    final prefs = ref.read(sharedPreferencesProvider);
    await TelemetryService.sendPing(prefs);
  }

  @override
  Widget build(BuildContext context) {
    ref.listen<AsyncValue<EventsFeed>>(eventsFeedProvider, (previous, next) {
      next.whenData((feed) {
        NotificationScheduler.sync(feed);
      });
    });
    return widget.child;
  }
}
