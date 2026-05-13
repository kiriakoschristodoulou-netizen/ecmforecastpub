// lib/config/endpoints.dart
//
// All remote URLs the app reaches out to. Centralized here so we have
// one place to update when repos move or the telemetry worker URL
// changes.
//
// Personal build fetches from the PRIVATE repo (ecmforecast) via an
// embedded fine-grained PAT scoped to contents:read on that one repo.
// The PAT is injected at build time via --dart-define so it never
// lives in source.
//
// Friends build fetches from the PUBLIC repo (ecmforecastpub) with
// no authentication. Friends builds must never include the PAT.

import 'build_mode.dart';

/// All endpoint URLs the app uses, resolved per build mode.
class Endpoints {
  Endpoints._();

  // --- Public repo (no auth) ---
  // All builds read version.json from here (it's the single source of
  // truth for "what's the latest APK", regardless of build mode).
  static const String _publicRawBase =
      'https://raw.githubusercontent.com/kiriakoschristodoulou-netizen/ecmforecastpub/main';

  static const String publicEventsUrl =
      '$_publicRawBase/backend/output/events_public.json';

  static const String versionUrl =
      '$_publicRawBase/backend/output/version.json';

  /// Where the user is sent when they tap "Update". Points at the
  /// GitHub Releases page; specific version is appended at run time.
  static const String releasesUrl =
      'https://github.com/kiriakoschristodoulou-netizen/ecmforecastpub/releases';

  // --- Private repo (PAT-authenticated) ---
  // Personal build only. The PAT is injected via --dart-define at build
  // time. If empty (default), personal build will fail to fetch — by
  // design, the binary should not ship without the PAT baked in.
  static const String _privateRawBase =
      'https://raw.githubusercontent.com/kiriakoschristodoulou-netizen/ecmforecast/main';

  static const String _personalEventsPath =
      '/backend/output/events_personal.json';

  static const String _privateRepoPat =
      String.fromEnvironment('PRIVATE_REPO_PAT', defaultValue: '');

  // --- Telemetry worker (Cloudflare Workers, configured later) ---
  // /ping is called by all builds on launch. /stats is called by the
  // personal build only and is keyed with TELEMETRY_STATS_KEY.
  static const String telemetryBase =
      String.fromEnvironment('TELEMETRY_BASE',
          defaultValue: 'https://ecm-telemetry.workers.dev');

  static const String telemetryPingPath = '/ping';
  static const String telemetryStatsPath = '/stats';

  static const String _telemetryStatsKey =
      String.fromEnvironment('TELEMETRY_STATS_KEY', defaultValue: '');

  // --- Resolved URLs (the only things the rest of the app should call) ---

  /// The events.json URL to fetch for this build.
  /// Personal build: private repo (PAT-authenticated).
  /// Friends build: public repo (anonymous).
  static String get eventsUrl {
    if (isPersonalBuild) {
      return '$_privateRawBase$_personalEventsPath';
    }
    return publicEventsUrl;
  }

  /// The Authorization header value to use when fetching [eventsUrl].
  /// Returns null for friends build (no auth needed).
  /// Returns "Bearer <PAT>" for personal build.
  static String? get eventsAuthHeader {
    if (isPersonalBuild && _privateRepoPat.isNotEmpty) {
      return 'Bearer $_privateRepoPat';
    }
    return null;
  }

  /// True when the personal build has its PAT baked in. False indicates
  /// a misconfigured personal-build binary that should be reported as
  /// an error at startup.
  static bool get personalBuildHasCredentials =>
      isPersonalBuild && _privateRepoPat.isNotEmpty;

  /// Full telemetry ping URL (POSTed to on launch).
  static String get telemetryPingUrl => '$telemetryBase$telemetryPingPath';

  /// Full telemetry stats URL. Personal build only.
  /// Returns null on friends build (which must never call this).
  static String? get telemetryStatsUrl {
    if (!isPersonalBuild) return null;
    if (_telemetryStatsKey.isEmpty) return null;
    return '$telemetryBase$telemetryStatsPath?key=$_telemetryStatsKey';
  }
}
