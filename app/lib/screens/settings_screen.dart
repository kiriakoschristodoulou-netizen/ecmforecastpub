// lib/screens/settings_screen.dart
//
// Settings hub. Sections:
//   - APPEARANCE: theme mode (light/dark/system)
//   - DATE FORMAT: radio choices, persisted via dateFormatProvider
//   - YOUR FORECASTING SCORE: HIT rate from local retrospectives
//   - TELEMETRY: personal-build only, fetched fresh on each Settings open
//   - OTHER: Update entry (conditional) + Archive + About

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../config/build_mode.dart';
import '../providers/date_format_provider.dart';
import '../providers/events_provider.dart';
import '../providers/retrospective.dart';
import '../providers/theme_mode_provider.dart';
import '../providers/update_provider.dart';
import '../services/stats_service.dart';
import '../theme/app_theme.dart';
import 'about_screen.dart';
import 'archive_screen.dart';

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final currentPattern = ref.watch(dateFormatProvider);
    final currentThemeMode = ref.watch(themeModeProvider);
    final scores = ref.watch(retrospectiveProvider);
    final rates = _computeRates(scores);
    final feedAsync = ref.watch(eventsFeedProvider);
    final updateAsync = ref.watch(updateStatusProvider);

    final archiveCount = feedAsync.maybeWhen(
      data: (feed) => feed.forecasts
          .where((f) => f.isPast() && f.daysUntil() < -60)
          .length,
      orElse: () => 0,
    );

    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(
        children: [
          const _SectionHeader('APPEARANCE'),
          RadioGroup<ThemeMode>(
            groupValue: currentThemeMode,
            onChanged: (value) {
              if (value != null) {
                ref.read(themeModeProvider.notifier).setMode(value);
              }
            },
            child: const Column(
              children: [
                RadioListTile<ThemeMode>(
                  dense: true,
                  title: Text('Light'),
                  value: ThemeMode.light,
                ),
                RadioListTile<ThemeMode>(
                  dense: true,
                  title: Text('Dark'),
                  value: ThemeMode.dark,
                ),
                RadioListTile<ThemeMode>(
                  dense: true,
                  title: Text('Follow system'),
                  value: ThemeMode.system,
                ),
              ],
            ),
          ),
          const _SectionHeader('DATE FORMAT'),
          RadioGroup<String>(
            groupValue: currentPattern,
            onChanged: (value) {
              if (value != null) {
                ref.read(dateFormatProvider.notifier).setPattern(value);
              }
            },
            child: Column(
              children: dateFormatChoices
                  .map(
                    (choice) => RadioListTile<String>(
                      dense: true,
                      title: Text(choice.displayLabel),
                      value: choice.pattern,
                    ),
                  )
                  .toList(),
            ),
          ),
          const _SectionHeader('YOUR FORECASTING SCORE'),
          _HitRateDisplay(rates: rates),
          if (isPersonalBuild) ...[
            const _SectionHeader('TELEMETRY'),
            const _TelemetryPanel(),
          ],
          const _SectionHeader('OTHER'),
          // Update entry: only shows when a newer version is published.
          // Reachable here as a fallback for users who dismissed the
          // home-screen update banner.
          updateAsync.maybeWhen(
            data: (status) {
              if (!status.hasUpdate) return const SizedBox.shrink();
              return ListTile(
                leading: const Icon(Icons.system_update),
                title: Text('Update available (v${status.latestVersion})'),
                subtitle: status.releaseNotes == null ||
                        status.releaseNotes!.isEmpty
                    ? null
                    : Text(
                        status.releaseNotes!,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                trailing: const Icon(Icons.open_in_new),
                onTap: () => _launchUpdateUrl(status.releaseUrl),
              );
            },
            orElse: () => const SizedBox.shrink(),
          ),
          ListTile(
            leading: const Icon(Icons.history),
            title: Text(
              archiveCount == 0
                  ? 'View archive'
                  : 'View archive ($archiveCount forecast'
                      '${archiveCount == 1 ? '' : 's'})',
            ),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const ArchiveScreen()),
            ),
          ),
          ListTile(
            leading: const Icon(Icons.info_outline),
            title: const Text('About'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const AboutScreen()),
            ),
          ),
          const SizedBox(height: 40),
        ],
      ),
    );
  }

  Future<void> _launchUpdateUrl(String url) async {
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }

  RetrospectiveRates _computeRates(Map<String, RetrospectiveScore> scores) {
    int hits = 0;
    for (final s in scores.values) {
      if (s == RetrospectiveScore.hit) hits++;
    }
    return RetrospectiveRates(total: scores.length, hits: hits);
  }
}

class _SectionHeader extends StatelessWidget {
  final String label;
  const _SectionHeader(this.label);

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 24, 16, 4),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w500,
          letterSpacing: 0.5,
          color: colors.sectionLabel,
        ),
      ),
    );
  }
}

class _HitRateDisplay extends StatelessWidget {
  final RetrospectiveRates rates;

  const _HitRateDisplay({required this.rates});

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    if (rates.total == 0) {
      return Padding(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
        child: Text(
          'No events scored yet. Tap HIT or MISS on past events to start tracking.',
          style: TextStyle(
            color: colors.hintText,
            height: 1.4,
            fontSize: 13,
          ),
        ),
      );
    }

    final percentage = rates.percentage.round();
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '${rates.hits}/${rates.total} past events HIT:',
            style: const TextStyle(fontSize: 14),
          ),
          const SizedBox(height: 4),
          Text(
            '$percentage%',
            style: const TextStyle(
              fontSize: 36,
              fontWeight: FontWeight.w500,
              height: 1.0,
            ),
          ),
        ],
      ),
    );
  }
}

/// Personal-build telemetry stats panel. Fetches on every build of the
/// Settings screen (every navigation in), so numbers are always current.
class _TelemetryPanel extends StatefulWidget {
  const _TelemetryPanel();

  @override
  State<_TelemetryPanel> createState() => _TelemetryPanelState();
}

class _TelemetryPanelState extends State<_TelemetryPanel> {
  late Future<StatsSnapshot?> _future;

  @override
  void initState() {
    super.initState();
    _future = StatsService.fetch();
  }

  void _refresh() {
    setState(() {
      _future = StatsService.fetch();
    });
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
      child: FutureBuilder<StatsSnapshot?>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return Row(
              children: [
                const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
                const SizedBox(width: 12),
                Text(
                  'Fetching stats...',
                  style: TextStyle(color: colors.hintText, fontSize: 13),
                ),
              ],
            );
          }
          if (snapshot.hasError) {
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Stats unavailable',
                  style: TextStyle(
                    color: colors.hintText,
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  '${snapshot.error}',
                  style: TextStyle(color: colors.hintText, fontSize: 11),
                ),
                const SizedBox(height: 8),
                TextButton(
                  onPressed: _refresh,
                  style: TextButton.styleFrom(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    minimumSize: const Size(0, 28),
                    textStyle: const TextStyle(fontSize: 12),
                  ),
                  child: const Text('Retry'),
                ),
              ],
            );
          }
          final stats = snapshot.data;
          if (stats == null) {
            // Personal build without STATS_KEY baked in.
            return Text(
              'Stats not configured for this build.',
              style: TextStyle(color: colors.hintText, fontSize: 12),
            );
          }
          return _StatsContent(stats: stats, onRefresh: _refresh);
        },
      ),
    );
  }
}

class _StatsContent extends StatelessWidget {
  final StatsSnapshot stats;
  final VoidCallback onRefresh;

  const _StatsContent({required this.stats, required this.onRefresh});

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;

    final versionLines = stats.versionDistribution.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _StatRow(label: 'Total installs', value: '${stats.totalInstalls}'),
        _StatRow(label: 'Active last 7 days', value: '${stats.activeLast7d}'),
        _StatRow(
            label: 'Active last 30 days', value: '${stats.activeLast30d}'),
        if (versionLines.isNotEmpty) ...[
          const SizedBox(height: 8),
          Text(
            'BY VERSION',
            style: TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w500,
              letterSpacing: 0.5,
              color: colors.sectionLabel,
            ),
          ),
          const SizedBox(height: 4),
          for (final entry in versionLines)
            _StatRow(
              label: entry.key,
              value: '${entry.value}',
              dense: true,
            ),
        ],
        const SizedBox(height: 8),
        Row(
          children: [
            Text(
              'Fetched ${_formatTime(stats.generatedAt)}',
              style: TextStyle(fontSize: 11, color: colors.hintText),
            ),
            const Spacer(),
            TextButton.icon(
              onPressed: onRefresh,
              icon: const Icon(Icons.refresh, size: 14),
              label: const Text('Refresh'),
              style: TextButton.styleFrom(
                padding:
                    const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                minimumSize: const Size(0, 28),
                textStyle: const TextStyle(fontSize: 12),
              ),
            ),
          ],
        ),
      ],
    );
  }

  String _formatTime(DateTime t) {
    final local = t.toLocal();
    final h = local.hour.toString().padLeft(2, '0');
    final m = local.minute.toString().padLeft(2, '0');
    return '$h:$m';
  }
}

class _StatRow extends StatelessWidget {
  final String label;
  final String value;
  final bool dense;

  const _StatRow({
    required this.label,
    required this.value,
    this.dense = false,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.symmetric(vertical: dense ? 1 : 3),
      child: Row(
        children: [
          Expanded(
            child: Text(
              label,
              style: TextStyle(fontSize: dense ? 12 : 13),
            ),
          ),
          Text(
            value,
            style: TextStyle(
              fontSize: dense ? 12 : 13,
              fontWeight: dense ? FontWeight.normal : FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }
}
