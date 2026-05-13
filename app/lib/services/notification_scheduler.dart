// lib/services/notification_scheduler.dart
//
// Bridges EventsFeed to NotificationService. AppLifecycle calls sync()
// every time the feed updates; this cancels all pending notifications
// and re-schedules one 3-day-before reminder per upcoming forecast.
//
// The cancel-all approach is intentional: simpler than diffing old vs
// new schedules, and our notification volume is low (typically <20
// upcoming forecasts).

import 'package:intl/intl.dart';

import '../models/events_feed.dart';
import 'notification_service.dart';

class NotificationScheduler {
  NotificationScheduler._();

  /// Reminder fires N days before each forecast date.
  static const int _daysBeforeForecast = 3;

  /// Wall-clock time (local zone) when the reminder fires.
  static const int _reminderHour = 9;
  static const int _reminderMinute = 0;

  /// Cancel every pending notification, then re-schedule one per
  /// upcoming forecast still at least [_daysBeforeForecast] days out.
  /// Safe to call repeatedly.
  static Future<void> sync(EventsFeed feed) async {
    await NotificationService.cancelAll();

    final upcoming = feed.forecasts.where((f) => !f.isPast()).toList();
    int notificationId = 1;

    for (final forecast in upcoming) {
      final daysUntil = forecast.daysUntil();
      // If already inside the reminder window, no notification to schedule.
      if (daysUntil < _daysBeforeForecast) continue;

      final reminderDate = forecast.date.subtract(
        const Duration(days: _daysBeforeForecast),
      );
      final scheduledAt = DateTime(
        reminderDate.year,
        reminderDate.month,
        reminderDate.day,
        _reminderHour,
        _reminderMinute,
      );

      // Belt-and-suspenders: don't schedule a reminder for a past time.
      if (scheduledAt.isBefore(DateTime.now())) continue;

      final dateLabel = DateFormat('d MMM yyyy').format(forecast.date);
      final body = 'In $_daysBeforeForecast days \u2022 $dateLabel';

      await NotificationService.schedule(
        id: notificationId++,
        title: forecast.title,
        body: body,
        scheduledAt: scheduledAt,
        payload: forecast.id,
      );
    }
  }
}
