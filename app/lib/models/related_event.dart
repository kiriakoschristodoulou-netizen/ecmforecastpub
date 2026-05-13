// lib/models/related_event.dart
//
// A scheduled real-world event that clusters near a forecast date.
// Never appears as a standalone card; only inside a Forecast's relatedEvents list.

/// One scheduled event in the vicinity (±5 days) of a forecast date.
class RelatedEvent {
  /// The date of this scheduled event.
  final DateTime date;

  /// Short human-readable description (under ~50 chars typically).
  final String title;

  /// Categorical tag for filtering and styling.
  final RelatedEventCategory category;

  /// Optional link to an authoritative source for this event.
  final String? url;

  const RelatedEvent({
    required this.date,
    required this.title,
    required this.category,
    this.url,
  });

  /// Parse from a JSON map matching the events.json schema v1.0.
  factory RelatedEvent.fromJson(Map<String, dynamic> json) {
    return RelatedEvent(
      date: DateTime.parse(json['date'] as String),
      title: json['title'] as String,
      category: RelatedEventCategory.fromString(json['category'] as String?),
      url: json['url'] as String?,
    );
  }

  @override
  String toString() =>
      'RelatedEvent(${date.toIso8601String().substring(0, 10)}, $title)';
}

/// Categorical tag for a related (supporting) event.
///
/// Forward-compatible: any unknown string from the JSON falls back to [other]
/// so old apps don't crash when new categories are added in future schema versions.
enum RelatedEventCategory {
  election,
  centralBank,
  sovereignDebt,
  treaty,
  summit,
  military,
  economicData,
  other;

  /// Parse from the schema's snake_case string. Unknown values fall back to [other].
  static RelatedEventCategory fromString(String? value) {
    switch (value) {
      case 'election':
        return RelatedEventCategory.election;
      case 'central_bank':
        return RelatedEventCategory.centralBank;
      case 'sovereign_debt':
        return RelatedEventCategory.sovereignDebt;
      case 'treaty':
        return RelatedEventCategory.treaty;
      case 'summit':
        return RelatedEventCategory.summit;
      case 'military':
        return RelatedEventCategory.military;
      case 'economic_data':
        return RelatedEventCategory.economicData;
      default:
        return RelatedEventCategory.other;
    }
  }
}
