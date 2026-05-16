// lib/services/feed_service.dart
//
// Fetches and parses the events feed from raw.githubusercontent.com.
// Personal build uses the PAT to authenticate; friends build fetches
// anonymously. Both go through the same code path; the auth header
// difference is encapsulated in Endpoints.eventsAuthHeader.

import 'dart:async';
import 'dart:convert';
import 'dart:io' show SocketException;

import 'package:http/http.dart' as http;

import '../config/endpoints.dart';
import '../models/events_feed.dart';

/// Thrown when the feed fetch fails for any reason OTHER THAN being
/// offline. Wraps the underlying cause so the UI can surface a useful
/// message. Use [FeedOfflineException] for "no network" specifically.
class FeedFetchException implements Exception {
  final String message;
  final Object? cause;

  FeedFetchException(this.message, {this.cause});

  @override
  String toString() =>
      'FeedFetchException: $message${cause == null ? '' : ' (cause: $cause)'}';
}

/// Thrown when the device has no network connectivity. Distinct from
/// [FeedFetchException] so the UI can show a friendly offline message
/// rather than a technical error string.
class FeedOfflineException implements Exception {
  final Object? cause;

  FeedOfflineException({this.cause});

  @override
  String toString() => 'FeedOfflineException';
}

/// Stateless service responsible for fetching events.json over HTTP and
/// turning it into a typed [EventsFeed]. No caching here -- the provider
/// layer above handles cache-and-refresh.
class FeedService {
  /// Default fetch timeout. Network requests that take longer than this
  /// fail with a [FeedFetchException].
  static const Duration defaultTimeout = Duration(seconds: 15);

  final http.Client _client;
  final Duration _timeout;

  FeedService({http.Client? client, Duration? timeout})
      : _client = client ?? http.Client(),
        _timeout = timeout ?? defaultTimeout;

  /// Fetch the events feed for the current build mode.
  ///
  /// Personal build: hits the private repo with the PAT.
  /// Friends build: hits the public repo anonymously.
  Future<EventsFeed> fetchEvents() async {
    final url = Endpoints.eventsUrl;
    final authHeader = Endpoints.eventsAuthHeader;

    final headers = <String, String>{
      'Accept': 'application/json',
      if (authHeader != null) 'Authorization': authHeader,
    };

    http.Response response;
    try {
      response = await _client
          .get(Uri.parse(url), headers: headers)
          .timeout(_timeout);
    } on TimeoutException catch (e) {
      throw FeedFetchException(
          'Feed fetch timed out after ${_timeout.inSeconds}s',
          cause: e);
    } on SocketException catch (e) {
      // "Failed host lookup" (DNS unreachable) and "Network is
      // unreachable" both throw SocketException. Treated as offline
      // regardless of which underlying cause.
      throw FeedOfflineException(cause: e);
    } catch (e) {
      // Some platforms wrap SocketException inside http.ClientException
      // or similar. Sniff the message as a defensive fallback so
      // genuine offline failures still surface the friendly message.
      final s = e.toString();
      if (s.contains('SocketException') ||
          s.contains('Failed host lookup') ||
          s.contains('Network is unreachable')) {
        throw FeedOfflineException(cause: e);
      }
      throw FeedFetchException('Network error fetching feed', cause: e);
    }

    if (response.statusCode != 200) {
      throw FeedFetchException(
          'Feed returned HTTP ${response.statusCode} from $url');
    }

    final dynamic decoded;
    try {
      decoded = jsonDecode(response.body);
    } catch (e) {
      throw FeedFetchException('Feed body is not valid JSON', cause: e);
    }

    if (decoded is! Map<String, dynamic>) {
      throw FeedFetchException(
          'Feed root must be a JSON object, got ${decoded.runtimeType}');
    }

    try {
      return EventsFeed.fromJson(decoded);
    } catch (e) {
      throw FeedFetchException('Feed JSON failed schema parse', cause: e);
    }
  }

  /// Close the underlying HTTP client. Call this if the service was given
  /// a client it owns; otherwise the app's lifetime handles it.
  void dispose() {
    _client.close();
  }
}
