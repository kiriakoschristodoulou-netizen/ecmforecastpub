// lib/services/notification_service.dart
//
// Thin wrapper around flutter_local_notifications. Handles plugin init,
// timezone setup, permission request, channel creation, and the scheduling
// primitives the rest of the app uses.
//
// Design choices for v1:
//   - Inexact alarms only (no SCHEDULE_EXACT_ALARM permission dance).
//     For a "3 days before" reminder, being a few hours off is acceptable
//     and Android batches inexact alarms efficiently.
//   - Timezone hardcoded to Europe/Athens. Friends outside Greece will
//     see notifications shifted by their UTC offset. If this becomes a
//     real complaint, swap in flutter_timezone (one-file change here).

import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:timezone/data/latest_all.dart' as tz_data;
import 'package:timezone/timezone.dart' as tz;

class NotificationService {
  NotificationService._();

  static final FlutterLocalNotificationsPlugin _plugin =
      FlutterLocalNotificationsPlugin();

  static const String _channelId = 'forecast_reminders_v1';
  static const String _channelName = 'Forecast reminders';
  static const String _channelDescription =
      'Reminders 3 days before upcoming forecasts.';

  static bool _initialized = false;

  /// Initialize the plugin, timezone DB, and notification channel.
  /// Call once before runApp. Idempotent on repeat calls.
  static Future<void> init() async {
    if (_initialized) return;

    tz_data.initializeTimeZones();
    try {
      tz.setLocalLocation(tz.getLocation('Europe/Athens'));
    } catch (_) {
      // Defensive: if the zone db is broken, fall back to UTC so we
      // never crash at startup. Schedule precision will be off but
      // notifications still fire.
      tz.setLocalLocation(tz.UTC);
    }

    const androidSettings =
        AndroidInitializationSettings('@mipmap/ic_launcher');
    const settings = InitializationSettings(android: androidSettings);
    await _plugin.initialize(settings);

    // Pre-create the channel so the user sees it in app notification
    // settings even before any notification has fired.
    final android = _plugin.resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin>();
    await android?.createNotificationChannel(
      const AndroidNotificationChannel(
        _channelId,
        _channelName,
        description: _channelDescription,
        importance: Importance.high,
      ),
    );

    _initialized = true;
  }

  /// Request POST_NOTIFICATIONS permission on Android 13+.
  /// On older Android versions this is a no-op that returns true.
  /// Repeated calls after user denial show the system "Settings" path
  /// (Android handles the UX).
  static Future<bool> requestPermission() async {
    final android = _plugin.resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin>();
    if (android == null) return false;
    final granted = await android.requestNotificationsPermission();
    return granted ?? false;
  }

  /// Schedule a single notification. No-op if [scheduledAt] is in the past.
  /// Uses inexact alarms - no special permission needed.
  static Future<void> schedule({
    required int id,
    required String title,
    required String body,
    required DateTime scheduledAt,
    String? payload,
  }) async {
    if (scheduledAt.isBefore(DateTime.now())) return;

    final tzDateTime = tz.TZDateTime.from(scheduledAt, tz.local);

    await _plugin.zonedSchedule(
      id,
      title,
      body,
      tzDateTime,
      const NotificationDetails(
        android: AndroidNotificationDetails(
          _channelId,
          _channelName,
          channelDescription: _channelDescription,
          importance: Importance.high,
          priority: Priority.high,
        ),
      ),
      androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
      uiLocalNotificationDateInterpretation:
          UILocalNotificationDateInterpretation.absoluteTime,
      payload: payload,
    );
  }

  /// Cancel every pending notification. Used before bulk reschedule on
  /// feed refresh.
  static Future<void> cancelAll() async {
    await _plugin.cancelAll();
  }

  /// Debug helper - returns the currently scheduled notifications.
  /// Not used by production code; useful for inspection during testing.
  static Future<List<PendingNotificationRequest>> pendingRequests() async {
    return _plugin.pendingNotificationRequests();
  }
}
