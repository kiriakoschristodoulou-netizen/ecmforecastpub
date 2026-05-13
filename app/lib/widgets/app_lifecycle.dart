// lib/widgets/app_lifecycle.dart
//
// Wraps the HomeScreen tree and performs two jobs:
//   1. On first frame: requests POST_NOTIFICATIONS permission (Android 13+)
//   2. On every feed update: reschedules notifications
//
// Lives between MaterialApp.home and HomeScreen so its ref.listen is
// active for the app's entire foreground lifetime.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/events_feed.dart';
import '../providers/events_provider.dart';
import '../services/notification_scheduler.dart';
import '../services/notification_service.dart';

class AppLifecycle extends ConsumerStatefulWidget {
  final Widget child;
  const AppLifecycle({super.key, required this.child});

  @override
  ConsumerState<AppLifecycle> createState() => _AppLifecycleState();
}

class _AppLifecycleState extends ConsumerState<AppLifecycle> {
  bool _permissionRequested = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _requestPermissionOnce();
    });
  }

  Future<void> _requestPermissionOnce() async {
    if (_permissionRequested) return;
    _permissionRequested = true;
    await NotificationService.requestPermission();
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
