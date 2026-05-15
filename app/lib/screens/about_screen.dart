// lib/screens/about_screen.dart
//
// About screen. Content gated by build mode:
//   - Friends build: full disclaimer (locked per project notes session 2)
//   - Personal build: stripped-down version with build info + telemetry
//     stats placeholder (real telemetry panel is session 7)

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:package_info_plus/package_info_plus.dart';

import '../config/build_mode.dart';
import '../providers/events_provider.dart';
import '../theme/app_theme.dart';

class AboutScreen extends ConsumerWidget {
  const AboutScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      appBar: AppBar(title: const Text('About')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
        child: isPersonalBuild
            ? const _PersonalBuildAbout()
            : const _FriendsBuildAbout(),
      ),
    );
  }
}

class _FriendsBuildAbout extends StatelessWidget {
  const _FriendsBuildAbout();

  @override
  Widget build(BuildContext context) {
    return const Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'ECM Forecasting Alerts',
          style: TextStyle(fontSize: 18, fontWeight: FontWeight.w500),
        ),
        SizedBox(height: 12),
        _AboutParagraph(
          'ECM Forecasting Alerts is a personal project that aggregates publicly '
          'available forecasts and scheduled events of macroeconomic, geopolitical, '
          'and social significance.',
        ),
        SizedBox(height: 16),
        Text(
          'Sources include:',
          style: TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
        ),
        SizedBox(height: 4),
        _Bullet('Armstrong Economics (publicly available articles and RSS feed)'),
        _Bullet(
          'Public election calendars and institutional schedules '
          '(IMF, Federal Reserve, central banks, treaty bodies, etc.)',
        ),
        _Bullet('General news sources for current context'),
        SizedBox(height: 16),
        _AboutParagraph(
          'This app is independent and not affiliated with, endorsed by, or licensed '
          'by Armstrong Economics or any other source named above. All trademarks, '
          'names, and original content belong to their respective owners. Where this '
          'app references forecasts or analysis from external sources, attribution '
          'and links to the original are provided.',
        ),
        SizedBox(height: 16),
        _AboutParagraph(
          'The "why this might happen" analyses are produced by an AI language model '
          'synthesizing publicly available information. They are interpretive '
          'commentary, not original reporting, and should not be mistaken for the '
          'views of any cited source.',
        ),
        SizedBox(height: 16),
        _AboutParagraph(
          'This app is provided for informational and educational purposes only. '
          'Nothing in it constitutes financial, investment, legal, or political '
          'advice. Use your own judgment.',
        ),
        SizedBox(height: 16),
        _AboutParagraph(
          'No tracking. No ads. No account required. Anonymous usage statistics '
          '(install count, app version, launch dates) are collected via a random '
          'identifier generated on first install - no personal information, '
          'no device IDs, no location.',
        ),
        SizedBox(height: 24),
        _VersionInfo(),
      ],
    );
  }
}

class _PersonalBuildAbout extends ConsumerWidget {
  const _PersonalBuildAbout();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final feedAsync = ref.watch(eventsFeedProvider);
    final feedGenerated = feedAsync.maybeWhen(
      data: (feed) => feed.generatedAt.toIso8601String(),
      orElse: () => null,
    );
    final feedTypeName = feedAsync.maybeWhen(
      data: (feed) => feed.feedType.name,
      orElse: () => '-',
    );

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'ECM Forecasting Alerts (personal build)',
          style: TextStyle(fontSize: 18, fontWeight: FontWeight.w500),
        ),
        const SizedBox(height: 12),
        const Text(
          'Includes private-source synthesis and telemetry stats.',
          style: TextStyle(fontSize: 13, height: 1.5),
        ),
        const SizedBox(height: 16),
        _KeyValueRow(label: 'Feed', value: feedTypeName),
        if (feedGenerated != null)
          _KeyValueRow(label: 'Feed updated', value: feedGenerated),
        const SizedBox(height: 16),
        const _VersionInfo(),
        const SizedBox(height: 24),
        const Text(
          'Telemetry panel coming in a later release.',
          style: TextStyle(fontSize: 11, fontStyle: FontStyle.italic),
        ),
      ],
    );
  }
}

class _VersionInfo extends StatelessWidget {
  const _VersionInfo();

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<PackageInfo>(
      future: PackageInfo.fromPlatform(),
      builder: (context, snapshot) {
        if (!snapshot.hasData) return const SizedBox.shrink();
        final pkg = snapshot.data!;
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _KeyValueRow(
              label: 'Version',
              value: '${pkg.version} (build ${pkg.buildNumber})',
            ),
          ],
        );
      },
    );
  }
}

class _KeyValueRow extends StatelessWidget {
  final String label;
  final String value;

  const _KeyValueRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 110,
            child: Text(
              label,
              style: TextStyle(
                fontSize: 12,
                color: colors.hintText,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(fontSize: 12),
            ),
          ),
        ],
      ),
    );
  }
}

class _AboutParagraph extends StatelessWidget {
  final String text;
  const _AboutParagraph(this.text);

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: const TextStyle(fontSize: 13, height: 1.55),
    );
  }
}

class _Bullet extends StatelessWidget {
  final String text;
  const _Bullet(this.text);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(left: 12, top: 2, bottom: 2),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Padding(
            padding: EdgeInsets.only(top: 6, right: 8),
            child: Text(
              '\u2022',
              style: TextStyle(fontSize: 10),
            ),
          ),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(fontSize: 13, height: 1.5),
            ),
          ),
        ],
      ),
    );
  }
}
