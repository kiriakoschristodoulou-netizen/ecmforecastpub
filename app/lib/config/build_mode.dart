// lib/config/build_mode.dart
//
// Compile-time flag that distinguishes the personal build (KC's APK,
// with private feed + telemetry panel) from the friends build (public
// feed only, no telemetry UI).
//
// Set at build time:
//   flutter build apk --dart-define=BUILD_MODE=personal
//   flutter build apk --dart-define=BUILD_MODE=friends
//
// Unspecified default = friends (safer if someone ever clones and builds
// without specifying; the friends build cannot leak private content
// because the endpoint it points at doesn't have any).

/// The two faces of the app. Same codebase, different feed URLs and
/// different UI surface (the telemetry panel is gated on personal).
enum BuildMode {
  personal,
  friends;

  static BuildMode fromString(String? value) {
    switch (value) {
      case 'personal':
        return BuildMode.personal;
      case 'friends':
        return BuildMode.friends;
      default:
        return BuildMode.friends;
    }
  }
}

/// Resolved at compile time from `--dart-define=BUILD_MODE=...`.
/// Defaults to friends when unspecified.
const String _rawBuildMode =
    String.fromEnvironment('BUILD_MODE', defaultValue: 'friends');

/// The build mode this binary was compiled for. Read this anywhere in
/// the app to gate personal-only features.
final BuildMode currentBuildMode = BuildMode.fromString(_rawBuildMode);

/// True when this binary is the personal build. Use for gating the
/// telemetry panel, draft-event mode, and any other personal-only UI.
bool get isPersonalBuild => currentBuildMode == BuildMode.personal;

/// True when this binary is the friends build. Use for the friends-only
/// disclaimer phrasing in the About screen, etc.
bool get isFriendsBuild => currentBuildMode == BuildMode.friends;
