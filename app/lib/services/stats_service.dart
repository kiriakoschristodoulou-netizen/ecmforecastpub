// lib/services/stats_service.dart
//
// Personal-build-only. Fetches /stats from the telemetry worker using
// the embedded STATS_KEY. Friends build never calls this - the stats
// URL getter returns null for them.

import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/endpoints.dart';

/// Snapshot of telemetry stats returned by the worker's /stats endpoint.
class StatsSnapshot {
  final int totalInstalls;
  final int activeLast7d;
  final int activeLast30d;
  final Map<String, int> versionDistribution;
  final DateTime generatedAt;

  const StatsSnapshot({
    required this.totalInstalls,
    required this.activeLast7d,
    required this.activeLast30d,
    required this.versionDistribution,
    required this.generatedAt,
  });
}

class StatsFetchException implements Exception {
  final String message;
  StatsFetchException(this.message);
  @override
  String toString() => 'StatsFetchException: $message';
}

class StatsService {
  static const Duration _timeout = Duration(seconds: 8);

  /// Fetch stats from the worker. Throws StatsFetchException on any
  /// failure (network, auth, parse). Returns null if stats are
  /// unavailable on this build (friends builds, or personal builds
  /// without the key baked in).
  static Future<StatsSnapshot?> fetch() async {
    final url = Endpoints.telemetryStatsUrl;
    if (url == null) return null;

    final http.Response response;
    try {
      response = await http
          .get(Uri.parse(url), headers: const {'Accept': 'application/json'})
          .timeout(_timeout);
    } on TimeoutException {
      throw StatsFetchException('Timed out after ${_timeout.inSeconds}s');
    } catch (e) {
      throw StatsFetchException('Network error: $e');
    }

    if (response.statusCode == 401) {
      throw StatsFetchException('Unauthorized (bad STATS_KEY?)');
    }
    if (response.statusCode != 200) {
      throw StatsFetchException('HTTP ${response.statusCode}');
    }

    dynamic decoded;
    try {
      decoded = jsonDecode(response.body);
    } catch (e) {
      throw StatsFetchException('Invalid JSON response');
    }
    if (decoded is! Map<String, dynamic>) {
      throw StatsFetchException('Stats payload is not an object');
    }

    final total = decoded['total_installs'];
    final a7 = decoded['active_last_7d'];
    final a30 = decoded['active_last_30d'];
    final dist = decoded['version_distribution'];
    final gen = decoded['generated_at'];

    if (total is! int || a7 is! int || a30 is! int) {
      throw StatsFetchException('Missing or malformed count fields');
    }
    if (dist is! Map) {
      throw StatsFetchException('Missing or malformed version_distribution');
    }
    if (gen is! String) {
      throw StatsFetchException('Missing or malformed generated_at');
    }

    final distTyped = <String, int>{};
    dist.forEach((k, v) {
      if (k is String && v is int) {
        distTyped[k] = v;
      }
    });

    final generatedAt = DateTime.tryParse(gen);
    if (generatedAt == null) {
      throw StatsFetchException('Unparseable generated_at');
    }

    return StatsSnapshot(
      totalInstalls: total,
      activeLast7d: a7,
      activeLast30d: a30,
      versionDistribution: distTyped,
      generatedAt: generatedAt,
    );
  }
}
