// lib/models/events_feed.dart
//
// Top-level container for the parsed events.json file.
// Whatever the feed_service.dart fetches from raw.githubusercontent.com
// gets parsed into one of these.

import 'forecast.dart';

/// The deserialized contents of an events.json file.
class EventsFeed {
  /// SemVer of the schema this file was generated against.
  /// App checks compatibility on parse via [isSupported].
  final String schemaVersion;

  /// When the pipeline produced this file. Shown in-app as "Updated N days ago".
  final DateTime generatedAt;

  /// Which feed this is — personal or public.
  /// The app's build flag should sanity-check it loaded the right file.
  final FeedType feedType;

  /// All forecasts past and future, unsorted.
  /// App sorts client-side for display.
  final List<Forecast> forecasts;

  const EventsFeed({
    required this.schemaVersion,
    required this.generatedAt,
    required this.feedType,
    required this.forecasts,
  });

  /// Parse from a JSON map matching the events.json schema v1.0.
  factory EventsFeed.fromJson(Map<String, dynamic> json) {
    final forecastList = (json['forecasts'] as List<dynamic>?) ?? const [];

    return EventsFeed(
      schemaVersion: json['schema_version'] as String,
      generatedAt: DateTime.parse(json['generated_at'] as String),
      feedType: FeedType.fromString(json['feed_type'] as String?),
      forecasts: forecastList
          .map((e) => Forecast.fromJson(e as Map<String, dynamic>))
          .toList(growable: false),
    );
  }

  /// True if this app build can parse [schemaVersion]. App checks the
  /// major version; minor bumps are additive and safe.
  bool get isSupported {
    final parts = schemaVersion.split('.');
    if (parts.isEmpty) return false;
    return parts.first == '1';
  }

  /// Forecasts sorted ascending by date (earliest first).
  List<Forecast> get sortedByDate {
    final copy = List<Forecast>.from(forecasts);
    copy.sort((a, b) => a.date.compareTo(b.date));
    return copy;
  }

  @override
  String toString() => 'EventsFeed(v$schemaVersion, ${feedType.name}, '
      '${forecasts.length} forecasts)';
}

/// Which side of the two-mode build a feed is from.
///
/// Forward-compatible: unknown values fall back to [public] (safer default
/// since the public feed has no sensitive content).
enum FeedType {
  personal,
  public;

  static FeedType fromString(String? value) {
    switch (value) {
      case 'personal':
        return FeedType.personal;
      case 'public':
        return FeedType.public;
      default:
        return FeedType.public;
    }
  }
}
