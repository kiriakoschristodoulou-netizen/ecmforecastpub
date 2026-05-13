// lib/services/update_service.dart
//
// Checks for newer app versions by fetching version.json from the public
// repo and comparing against the installed app's version.
//
// version.json is shared across both builds (personal and friends) - we
// publish all releases to the same GitHub Releases page and the version
// manifest tracks the latest of either build.

import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:package_info_plus/package_info_plus.dart';

import '../config/endpoints.dart';

/// Snapshot of update status at one point in time. Held by the provider.
class UpdateStatus {
  /// SemVer string of the version currently installed on this device.
  final String installedVersion;

  /// Build code (Android versionCode) currently installed.
  final int installedBuildCode;

  /// Latest SemVer published in version.json.
  final String latestVersion;

  /// Latest build code published in version.json.
  final int latestBuildCode;

  /// URL to send the user to when they tap "Update".
  /// Points at the GitHub Release page for the latest version.
  final String releaseUrl;

  /// Short human-readable change summary from version.json.
  final String? releaseNotes;

  const UpdateStatus({
    required this.installedVersion,
    required this.installedBuildCode,
    required this.latestVersion,
    required this.latestBuildCode,
    required this.releaseUrl,
    required this.releaseNotes,
  });

  /// True when the installed build code is strictly less than the
  /// published one. We use build code (monotonic integer) rather than
  /// SemVer parsing because integer comparison is unambiguous.
  bool get hasUpdate => installedBuildCode < latestBuildCode;
}

class UpdateCheckException implements Exception {
  final String message;
  final Object? cause;

  UpdateCheckException(this.message, {this.cause});

  @override
  String toString() =>
      'UpdateCheckException: $message${cause == null ? '' : ' (cause: $cause)'}';
}

class UpdateService {
  static const Duration _defaultTimeout = Duration(seconds: 10);

  final http.Client _client;
  final Duration _timeout;

  UpdateService({http.Client? client, Duration? timeout})
      : _client = client ?? http.Client(),
        _timeout = timeout ?? _defaultTimeout;

  /// Fetch the version manifest and compare to the installed app's version.
  Future<UpdateStatus> check() async {
    // Installed side - reading package_info is local and fast.
    final pkg = await PackageInfo.fromPlatform();
    final installedVersion = pkg.version;
    final installedBuildCode = int.tryParse(pkg.buildNumber) ?? 0;

    // Published side - fetch version.json.
    http.Response response;
    try {
      response = await _client
          .get(Uri.parse(Endpoints.versionUrl),
              headers: const {'Accept': 'application/json'})
          .timeout(_timeout);
    } on TimeoutException catch (e) {
      throw UpdateCheckException(
          'Version check timed out after ${_timeout.inSeconds}s',
          cause: e);
    } catch (e) {
      throw UpdateCheckException(
          'Network error fetching version manifest',
          cause: e);
    }

    if (response.statusCode != 200) {
      throw UpdateCheckException(
          'Version manifest returned HTTP ${response.statusCode}');
    }

    final dynamic decoded;
    try {
      decoded = jsonDecode(response.body);
    } catch (e) {
      throw UpdateCheckException(
          'Version manifest is not valid JSON', cause: e);
    }
    if (decoded is! Map<String, dynamic>) {
      throw UpdateCheckException(
          'Version manifest root must be an object');
    }

    final latestVersion = decoded['latest_app_version'] as String?;
    final latestBuildCode = decoded['latest_build_code'] as int?;
    final releaseUrl = decoded['release_url'] as String?;
    final releaseNotes = decoded['release_notes'] as String?;

    if (latestVersion == null ||
        latestBuildCode == null ||
        releaseUrl == null) {
      throw UpdateCheckException(
          'Version manifest is missing required fields');
    }

    return UpdateStatus(
      installedVersion: installedVersion,
      installedBuildCode: installedBuildCode,
      latestVersion: latestVersion,
      latestBuildCode: latestBuildCode,
      releaseUrl: releaseUrl,
      releaseNotes: releaseNotes,
    );
  }

  void dispose() {
    _client.close();
  }
}
