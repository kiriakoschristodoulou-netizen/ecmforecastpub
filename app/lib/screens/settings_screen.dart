// lib/screens/settings_screen.dart
//
// Settings hub. Sections:
//   - APPEARANCE: theme mode (light/dark/system)
//   - DATE FORMAT: radio choices, persisted via dateFormatProvider
//   - YOUR FORECASTING SCORE: HIT rate from local retrospectives
//   - OTHER: Archive + About

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/date_format_provider.dart';
import '../providers/events_provider.dart';
import '../providers/retrospective.dart';
import '../providers/theme_mode_provider.dart';
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
          const _SectionHeader('OTHER'),
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
