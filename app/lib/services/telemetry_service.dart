// lib/services/telemetry_service.dart
//
// Anonymous install telemetry. On first launch, generates a v4 UUID
// and persists it in SharedPreferences. On every launch, POSTs that
// UUID + the app version to the telemetry worker.
//
// No personal data ever leaves the device:
//   - install_uuid is randomly generated on first launch
//   - app_version comes from package_info_plus (whatever's in pubspec)
//   - nothing else is sent
//
// Failures are silent. A failed ping (no network, server down, etc.)
// shouldn't disrupt the user; we just skip and try again next launch.

import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:package_info_plus/package_info_plus.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

import '../config/endpoints.dart';

class TelemetryService {
  TelemetryService._();

  static const String _installUuidKey = 'install_uuid_v1';
  static const Duration _pingTimeout = Duration(seconds: 6);

  /// In-memory cache of the install UUID. Loaded lazily on first read.
  static String? _cachedInstallUuid;

  /// Returns the install UUID, generating + persisting one on first call.
  /// Same UUID for the life of the install (until app data is cleared).
  static Future<String> getInstallUuid(SharedPreferences prefs) async {
    if (_cachedInstallUuid != null) return _cachedInstallUuid!;

    final stored = prefs.getString(_installUuidKey);
    if (stored != null && stored.isNotEmpty) {
      _cachedInstallUuid = stored;
      return stored;
    }

    final fresh = const Uuid().v4();
    await prefs.setString(_installUuidKey, fresh);
    _cachedInstallUuid = fresh;
    return fresh;
  }

  /// Send a single ping to the telemetry worker. Silent on failure.
  /// Call once per app launch from AppLifecycle.
  static Future<void> sendPing(SharedPreferences prefs) async {
    try {
      final uuid = await getInstallUuid(prefs);
      final pkg = await PackageInfo.fromPlatform();

      final body = jsonEncode({
        'install_uuid': uuid,
        'app_version': pkg.version,
      });

      await http
          .post(
            Uri.parse(Endpoints.telemetryPingUrl),
            headers: const {'Content-Type': 'application/json'},
            body: body,
          )
          .timeout(_pingTimeout);
      // We don't inspect the response. Worker returns 204 on success
      // and 400 on validation failure - both are "we tried", which is
      // all we want from a fire-and-forget ping.
    } catch (_) {
      // Silent: network errors, timeouts, server errors all swallowed.
      // The install UUID was already generated/persisted above, so the
      // next launch will retry.
    }
  }
}
