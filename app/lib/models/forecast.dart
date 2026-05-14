// lib/models/forecast.dart
//
// The top-level entity in events.json. Each forecast renders as a card on
// the home screen. Forecasts come from two sources merged at the backend:
//   - Chart-derived ECM cycle dates (manual_events.json)
//   - Blog-derived synthesized forecasts (synthesis_results.json)
//
// Schema v1.0 with additive fields (category, tag, origin). Old field
// names ("date") and new ("event_date") are both accepted to keep the
// parser forward/backward compatible across pipeline iterations.

import 'related_event.dart';

/// One forecasted date and its synthesized commentary.
class Forecast {
  /// Stable unique slug. Format examples:
  ///   ecm-wave-change-2026-07-01    (chart-derived)
  ///   blog-386802                   (blog-derived, wp_id prefixed)
  /// Used as the key for the user's local HIT/MISS retrospective record.
  /// MUST NOT change between pipeline runs for the same forecast.
  final String id;

  /// The forecast target date.
  final DateTime date;

  /// Short headline shown on the card.
  final String title;

  /// Optional context line under the title.
  final String? subtitle;

  /// Top-level category. Drives the colored badge on each card.
  final ForecastCategory category;

  /// More specific in-category tag (e.g. "wave_change", "nato_inflection").
  /// Free-form string, not enum-constrained because the taxonomy grows
  /// organically as new chart types are added.
  final String? tag;

  /// Three-tier importance level. High importance = larger card.
  final Importance importance;

  /// True when the forecast has 2+ related events (all within +/-5 days
  /// by schema rule). Triggers the CONVERGENCE! badge.
  final bool isConvergence;

  /// One-sentence explanation of why importance was set. Shown in detail view.
  final String? importanceJustification;

  /// The LLM-generated "why this might matter" content. Plain text.
  final String synthesis;

  /// Originating source for the forecast.
  final ForecastSource source;

  /// Supporting events within +/-5 days of [date].
  final List<RelatedEvent> relatedEvents;

  /// Where this forecast came from in the pipeline (chart, blog, or unknown).
  /// Useful for analytics and debugging; not surfaced in card UI by default.
  final ForecastOrigin origin;

  const Forecast({
    required this.id,
    required this.date,
    required this.title,
    this.subtitle,
    required this.category,
    this.tag,
    required this.importance,
    required this.isConvergence,
    this.importanceJustification,
    required this.synthesis,
    required this.source,
    this.relatedEvents = const [],
    this.origin = ForecastOrigin.unknown,
  });

  /// Parse from a JSON map. Accepts both legacy "date" and new "event_date"
  /// keys; the backend currently emits "event_date" but older files may
  /// still be in circulation.
  factory Forecast.fromJson(Map<String, dynamic> json) {
    final relatedList = json['related_events'] as List<dynamic>?;

    final rawDate = (json['event_date'] ?? json['date']) as String;

    return Forecast(
      id: json['id'] as String,
      date: DateTime.parse(rawDate),
      title: json['title'] as String,
      subtitle: json['subtitle'] as String?,
      category: ForecastCategory.fromString(json['category'] as String?),
      tag: json['tag'] as String?,
      importance: Importance.fromString(json['importance'] as String?),
      isConvergence: json['is_convergence'] as bool? ?? false,
      importanceJustification: json['importance_justification'] as String?,
      synthesis: (json['synthesis'] as String?) ?? '',
      source: ForecastSource.fromJson(
          (json['source'] as Map<String, dynamic>?) ?? const {}),
      relatedEvents: relatedList == null
          ? const []
          : relatedList
              .map((e) => RelatedEvent.fromJson(e as Map<String, dynamic>))
              .toList(growable: false),
      origin: ForecastOrigin.fromString(json['origin'] as String?),
    );
  }

  /// True when the forecast date is strictly before "now".
  bool isPast({DateTime? now}) {
    final ref = now ?? DateTime.now();
    return date.isBefore(DateTime(ref.year, ref.month, ref.day));
  }

  /// Whole days from "today" until [date]. Negative for past forecasts.
  int daysUntil({DateTime? now}) {
    final ref = now ?? DateTime.now();
    final today = DateTime(ref.year, ref.month, ref.day);
    final target = DateTime(date.year, date.month, date.day);
    return target.difference(today).inDays;
  }

  @override
  String toString() =>
      'Forecast(${date.toIso8601String().substring(0, 10)}, $title, '
      '${importance.name}, ${category.name}'
      '${isConvergence ? ', CONVERGENCE' : ''})';
}

/// Three-tier importance level. (Was two-tier in v0; added medium and low
/// when the chart-derived feed brought a richer importance spectrum.)
///
/// Forward-compatible: unknown values from JSON fall back to [medium].
/// Legacy "normal" maps to [medium] for backward compat with older feeds.
enum Importance {
  high,
  medium,
  low,
  normal;

  static Importance fromString(String? value) {
    switch (value) {
      case 'high':
        return Importance.high;
      case 'medium':
        return Importance.medium;
      case 'low':
        return Importance.low;
      case 'normal':
        return Importance.medium;
      default:
        return Importance.medium;
    }
  }
}

/// Categorical tag for a top-level forecast.
///
/// These map directly to backend categories produced by build_public_feed.py
/// (see backend/scraper/build_public_feed.py for the unified taxonomy).
///
/// Forward-compatible: unknown values from JSON fall back to [other].
enum ForecastCategory {
  /// Foundational ECM 8.6-year wave inflection points (wave changes,
  /// peaks, troughs). Also includes the Euro Wave #2 dates.
  ecmPanic,

  /// Pi cycle (31.4-year) targets within ECM waves.
  ecmPiTarget,

  /// NATO, treaty bodies, and other near-term geopolitical cycle dates.
  geopoliticalCycle,

  /// 150.8-year Cycle of War, 309.6-year Cycle of Religious Conflict.
  /// These are the centuries-scale meta-cycles.
  longCycle,

  /// Asset-class-specific panic cycles from monthly/yearly timing arrays
  /// (Dow, Gold, Yuan, Greek bond, AE War Index, etc.).
  assetPanicCycle,

  /// One-off natural disaster forecasts (asteroids, earthquakes, etc.).
  naturalDisasters,

  /// Fallback when JSON value doesn't match any known category.
  other;

  static ForecastCategory fromString(String? value) {
    switch (value) {
      case 'ecm_panic':
        return ForecastCategory.ecmPanic;
      case 'ecm_pi_target':
        return ForecastCategory.ecmPiTarget;
      case 'geopolitical_cycle':
        return ForecastCategory.geopoliticalCycle;
      case 'long_cycle':
        return ForecastCategory.longCycle;
      case 'asset_panic_cycle':
        return ForecastCategory.assetPanicCycle;
      case 'natural_disasters':
        return ForecastCategory.naturalDisasters;
      default:
        return ForecastCategory.other;
    }
  }

  /// Short uppercase label shown on the category badge in event cards.
  String get badgeLabel {
    switch (this) {
      case ForecastCategory.ecmPanic:
        return 'ECM';
      case ForecastCategory.ecmPiTarget:
        return 'PI CYCLE';
      case ForecastCategory.geopoliticalCycle:
        return 'GEOPOLITICAL';
      case ForecastCategory.longCycle:
        return 'LONG CYCLE';
      case ForecastCategory.assetPanicCycle:
        return 'ASSET PANIC';
      case ForecastCategory.naturalDisasters:
        return 'NATURAL';
      case ForecastCategory.other:
        return 'OTHER';
    }
  }
}

/// Origin of the forecast within the backend pipeline.
///
/// Forward-compatible: unknown falls back to [unknown].
enum ForecastOrigin {
  chart,
  blog,
  unknown;

  static ForecastOrigin fromString(String? value) {
    switch (value) {
      case 'chart':
        return ForecastOrigin.chart;
      case 'blog':
        return ForecastOrigin.blog;
      default:
        return ForecastOrigin.unknown;
    }
  }
}

/// The originating source of a forecast.
class ForecastSource {
  final String name;
  final String? url;

  const ForecastSource({required this.name, this.url});

  factory ForecastSource.fromJson(Map<String, dynamic> json) {
    return ForecastSource(
      name: (json['name'] as String?) ?? '',
      url: json['url'] as String?,
    );
  }

  @override
  String toString() => 'ForecastSource($name${url == null ? '' : ', $url'})';
}
