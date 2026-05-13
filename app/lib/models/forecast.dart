// lib/models/forecast.dart
//
// The top-level entity in events.json. Each forecast renders as a card on
// the home screen. Forecasts are sourced from Armstrong Economics
// (ECM turning points, Panic Cycles, Directional Changes, sovereign debt
// cycles, etc.). Supporting scheduled events live inside relatedEvents.

import 'related_event.dart';

/// One forecasted date and its synthesized commentary.
class Forecast {
  /// Stable unique slug. Format: source-type-YYYY-MM-DD.
  /// Used as the key for the user's local HIT/MISS retrospective record.
  /// MUST NOT change between pipeline runs for the same forecast.
  final String id;

  /// The forecast target date.
  final DateTime date;

  /// Short headline shown on the card (under ~40 chars).
  final String title;

  /// Optional context line under the title (e.g. "Armstrong ECM").
  final String? subtitle;

  /// Categorical tag.
  final ForecastCategory category;

  /// Two-tier importance level. High importance = larger card.
  final Importance importance;

  /// True when the forecast has 2+ related events (all within ±5 days
  /// by schema rule). Triggers the CONVERGENCE! badge.
  final bool isConvergence;

  /// One-sentence explanation of why importance was set. Shown in detail view.
  /// Required when LLM bumped from normal to high; otherwise optional.
  final String? importanceJustification;

  /// The LLM-generated "why this might matter" content. Multi-paragraph.
  /// Plain text, no markdown.
  final String synthesis;

  /// Originating source for the forecast.
  final ForecastSource source;

  /// Supporting events within ±5 days of [date]. Empty list when none.
  final List<RelatedEvent> relatedEvents;

  const Forecast({
    required this.id,
    required this.date,
    required this.title,
    this.subtitle,
    required this.category,
    required this.importance,
    required this.isConvergence,
    this.importanceJustification,
    required this.synthesis,
    required this.source,
    this.relatedEvents = const [],
  });

  /// Parse from a JSON map matching the events.json schema v1.0.
  factory Forecast.fromJson(Map<String, dynamic> json) {
    final relatedList = json['related_events'] as List<dynamic>?;

    return Forecast(
      id: json['id'] as String,
      date: DateTime.parse(json['date'] as String),
      title: json['title'] as String,
      subtitle: json['subtitle'] as String?,
      category: ForecastCategory.fromString(json['category'] as String?),
      importance: Importance.fromString(json['importance'] as String?),
      isConvergence: json['is_convergence'] as bool? ?? false,
      importanceJustification: json['importance_justification'] as String?,
      synthesis: json['synthesis'] as String,
      source: ForecastSource.fromJson(
          json['source'] as Map<String, dynamic>),
      relatedEvents: relatedList == null
          ? const []
          : relatedList
              .map((e) => RelatedEvent.fromJson(e as Map<String, dynamic>))
              .toList(growable: false),
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
      '${importance.name}${isConvergence ? ', CONVERGENCE' : ''})';
}

/// Two-tier importance level.
///
/// Forward-compatible: unknown values from JSON fall back to [normal].
enum Importance {
  high,
  normal;

  static Importance fromString(String? value) {
    switch (value) {
      case 'high':
        return Importance.high;
      case 'normal':
        return Importance.normal;
      default:
        return Importance.normal;
    }
  }
}

/// Categorical tag for a top-level forecast.
///
/// Forward-compatible: unknown values from JSON fall back to [other].
enum ForecastCategory {
  ecmTurningPoint,
  ecmDirectionalChange,
  ecmPanicCycle,
  armstrongSovereignDebt,
  armstrongWarCycle,
  armstrongCurrency,
  armstrongOther,
  other;

  static ForecastCategory fromString(String? value) {
    switch (value) {
      case 'ecm_turning_point':
        return ForecastCategory.ecmTurningPoint;
      case 'ecm_directional_change':
        return ForecastCategory.ecmDirectionalChange;
      case 'ecm_panic_cycle':
        return ForecastCategory.ecmPanicCycle;
      case 'armstrong_sovereign_debt':
        return ForecastCategory.armstrongSovereignDebt;
      case 'armstrong_war_cycle':
        return ForecastCategory.armstrongWarCycle;
      case 'armstrong_currency':
        return ForecastCategory.armstrongCurrency;
      case 'armstrong_other':
        return ForecastCategory.armstrongOther;
      default:
        return ForecastCategory.other;
    }
  }

  /// True if this category is rule-baseline HIGH importance per the
  /// importance pipeline. Note: actual importance can also be bumped by
  /// the LLM or forced HIGH by convergence; this only reflects the rule.
  bool get isRuleBaselineHigh {
    switch (this) {
      case ForecastCategory.ecmTurningPoint:
      case ForecastCategory.ecmDirectionalChange:
      case ForecastCategory.ecmPanicCycle:
      case ForecastCategory.armstrongSovereignDebt:
      case ForecastCategory.armstrongWarCycle:
        return true;
      case ForecastCategory.armstrongCurrency:
      case ForecastCategory.armstrongOther:
      case ForecastCategory.other:
        return false;
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
      name: json['name'] as String,
      url: json['url'] as String?,
    );
  }

  @override
  String toString() => 'ForecastSource($name${url == null ? '' : ', $url'})';
}
