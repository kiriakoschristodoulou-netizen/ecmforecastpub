// lib/screens/event_detail_screen.dart
//
// Full forecast detail view. All colors come from AppColors theme tokens.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:url_launcher/url_launcher.dart';

import '../models/forecast.dart';
import '../models/related_event.dart';
import '../providers/date_format_provider.dart';
import '../providers/retrospective.dart';
import '../theme/app_theme.dart';
import '../widgets/countdown_text.dart';

class EventDetailScreen extends ConsumerWidget {
  final Forecast forecast;

  const EventDetailScreen({super.key, required this.forecast});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final pattern = ref.watch(dateFormatProvider);
    final colors = context.appColors;
    final isPast = forecast.isPast();

    return Scaffold(
      appBar: AppBar(title: const Text('Forecast detail')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _HeroCard(
              forecast: forecast,
              dateFormatPattern: pattern,
              colors: colors,
            ),
            if (forecast.importanceJustification != null &&
                forecast.importanceJustification!.isNotEmpty) ...[
              const SizedBox(height: 16),
              _ImportanceJustificationCallout(
                text: forecast.importanceJustification!,
                colors: colors,
              ),
            ],
            const SizedBox(height: 18),
            _SectionLabel('WHY THIS MIGHT MATTER', colors: colors),
            const SizedBox(height: 6),
            Text(
              forecast.synthesis,
              style: TextStyle(
                fontSize: 13,
                height: 1.55,
                color: colors.bodyText,
              ),
            ),
            if (forecast.relatedEvents.isNotEmpty) ...[
              const SizedBox(height: 20),
              _SectionLabel('RELATED EVENTS IN THIS WINDOW',
                  colors: colors),
              const SizedBox(height: 6),
              ...forecast.relatedEvents.map(
                (e) => _RelatedEventTile(
                  event: e,
                  forecastDate: forecast.date,
                  colors: colors,
                ),
              ),
            ],
            const SizedBox(height: 20),
            _SectionLabel('FORECAST SOURCE', colors: colors),
            const SizedBox(height: 6),
            _SourceTile(source: forecast.source, colors: colors),
            if (isPast) ...[
              const SizedBox(height: 24),
              _ScorePanel(forecast: forecast, colors: colors),
            ],
          ],
        ),
      ),
    );
  }
}

class _HeroCard extends StatelessWidget {
  final Forecast forecast;
  final String dateFormatPattern;
  final AppColors colors;

  const _HeroCard({
    required this.forecast,
    required this.dateFormatPattern,
    required this.colors,
  });

  @override
  Widget build(BuildContext context) {
    final isPast = forecast.isPast();
    final isHigh = forecast.importance == Importance.high;
    final showConvergence = forecast.isConvergence && isHigh;

    final Color bg;
    final Color titleColor;
    final Color subtitleColor;

    if (isPast) {
      bg = colors.pastBg;
      titleColor = colors.pastTitle;
      subtitleColor = colors.pastSubtitle;
    } else if (isHigh) {
      bg = colors.nearestBg;
      titleColor = colors.nearestTitle;
      subtitleColor = colors.nearestSubtitle;
    } else {
      bg = colors.upcomingBg;
      titleColor = colors.upcomingTitle;
      subtitleColor = colors.upcomingSubtitle;
    }

    final dateFormatted =
        DateFormat(dateFormatPattern).format(forecast.date);
    final importanceLabel = forecast.importance == Importance.high
        ? 'High importance'
        : 'Normal importance';
    final hasSubtitle =
        forecast.subtitle != null && forecast.subtitle!.isNotEmpty;

    return Material(
      elevation: isHigh && !isPast ? 6 : 2,
      borderRadius: BorderRadius.circular(12),
      color: bg,
      surfaceTintColor: Colors.transparent,
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(12),
        ),
        padding: const EdgeInsets.all(16),
        child: Stack(
          children: [
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Padding(
                  padding: EdgeInsets.only(right: showConvergence ? 100 : 0),
                  child: Text(
                    '$dateFormatted \u2022 $importanceLabel',
                    style: TextStyle(fontSize: 11, color: subtitleColor),
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  forecast.title,
                  style: TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w500,
                    color: titleColor,
                    height: 1.25,
                  ),
                ),
                if (hasSubtitle) ...[
                  const SizedBox(height: 2),
                  Text(
                    forecast.subtitle!,
                    style: TextStyle(fontSize: 12, color: subtitleColor),
                  ),
                ],
                const SizedBox(height: 12),
                CountdownText(
                  daysUntil: forecast.daysUntil(),
                  size: CountdownSize.large,
                  numberColor: titleColor,
                  labelColor: subtitleColor,
                ),
              ],
            ),
            if (showConvergence)
              Positioned(
                top: 0,
                right: 0,
                child: _ConvergencePill(colors: colors),
              ),
          ],
        ),
      ),
    );
  }
}

class _ConvergencePill extends StatelessWidget {
  final AppColors colors;
  const _ConvergencePill({required this.colors});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(
        color: colors.convergenceBg,
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        'CONVERGENCE!',
        style: TextStyle(
          fontSize: 9,
          fontWeight: FontWeight.w500,
          letterSpacing: 0.6,
          color: colors.convergenceText,
        ),
      ),
    );
  }
}

class _ImportanceJustificationCallout extends StatelessWidget {
  final String text;
  final AppColors colors;

  const _ImportanceJustificationCallout({
    required this.text,
    required this.colors,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: colors.justificationBg,
        borderRadius: const BorderRadius.only(
          topRight: Radius.circular(8),
          bottomRight: Radius.circular(8),
        ),
        border: Border(
          left: BorderSide(
            color: colors.justificationAccent,
            width: 3,
          ),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            'WHY HIGH IMPORTANCE',
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w500,
              letterSpacing: 0.4,
              color: colors.justificationLabel,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            text,
            style: TextStyle(
              fontSize: 12,
              height: 1.5,
              color: colors.justificationText,
            ),
          ),
        ],
      ),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  final String label;
  final AppColors colors;

  const _SectionLabel(this.label, {required this.colors});

  @override
  Widget build(BuildContext context) {
    return Text(
      label,
      style: TextStyle(
        fontSize: 11,
        fontWeight: FontWeight.w500,
        letterSpacing: 0.5,
        color: colors.sectionLabel,
      ),
    );
  }
}

class _RelatedEventTile extends StatelessWidget {
  final RelatedEvent event;
  final DateTime forecastDate;
  final AppColors colors;

  const _RelatedEventTile({
    required this.event,
    required this.forecastDate,
    required this.colors,
  });

  String _relativeOffset() {
    final diffDays = event.date.difference(forecastDate).inDays;
    if (diffDays == 0) return 'same day';
    if (diffDays > 0) return '+$diffDays day${diffDays == 1 ? '' : 's'}';
    final ago = -diffDays;
    return '-$ago day${ago == 1 ? '' : 's'}';
  }

  Future<void> _openUrl(BuildContext context) async {
    final url = event.url;
    if (url == null || url.isEmpty) return;
    final uri = Uri.tryParse(url);
    if (uri == null) return;
    try {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } catch (_) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Could not open link')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final dateFormatted = DateFormat('d MMM').format(event.date);
    final tappable = event.url != null && event.url!.isNotEmpty;

    return InkWell(
      onTap: tappable ? () => _openUrl(context) : null,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 8),
        decoration: BoxDecoration(
          border: Border(
            bottom: BorderSide(color: colors.listDivider, width: 0.5),
          ),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    event.title,
                    style: TextStyle(
                      fontSize: 13,
                      color: colors.listText,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    '$dateFormatted \u2022 ${_relativeOffset()}',
                    style: TextStyle(
                      fontSize: 11,
                      color: colors.listSubtle,
                    ),
                  ),
                ],
              ),
            ),
            if (tappable)
              Padding(
                padding: const EdgeInsets.only(left: 8, top: 2),
                child: Icon(
                  Icons.open_in_new,
                  size: 14,
                  color: colors.listIcon,
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _SourceTile extends StatelessWidget {
  final ForecastSource source;
  final AppColors colors;

  const _SourceTile({required this.source, required this.colors});

  Future<void> _openUrl(BuildContext context) async {
    final url = source.url;
    if (url == null || url.isEmpty) return;
    final uri = Uri.tryParse(url);
    if (uri == null) return;
    try {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } catch (_) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Could not open link')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final tappable = source.url != null && source.url!.isNotEmpty;
    return InkWell(
      onTap: tappable ? () => _openUrl(context) : null,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Row(
          children: [
            Expanded(
              child: Text(
                source.name,
                style: TextStyle(
                  fontSize: 13,
                  color: colors.listText,
                ),
              ),
            ),
            if (tappable)
              Icon(
                Icons.open_in_new,
                size: 14,
                color: colors.listIcon,
              ),
          ],
        ),
      ),
    );
  }
}

class _ScorePanel extends ConsumerWidget {
  final Forecast forecast;
  final AppColors colors;

  const _ScorePanel({required this.forecast, required this.colors});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final score = ref.watch(retrospectiveProvider)[forecast.id];

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: colors.scorePanelBg,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'HOW DID IT PLAY OUT?',
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w500,
              letterSpacing: 0.5,
              color: colors.sectionLabel,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: _ScoreButton(
                  label: 'HIT',
                  active: score == RetrospectiveScore.hit,
                  activeBg: colors.hitButtonActive,
                  activeText: colors.hitButtonText,
                  inactiveBorder: colors.buttonInactiveBorder,
                  inactiveText: colors.buttonInactiveText,
                  onTap: () => _setScore(ref, RetrospectiveScore.hit),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _ScoreButton(
                  label: 'MISS',
                  active: score == RetrospectiveScore.miss,
                  activeBg: colors.missButtonActive,
                  activeText: colors.missButtonText,
                  inactiveBorder: colors.buttonInactiveBorder,
                  inactiveText: colors.buttonInactiveText,
                  onTap: () => _setScore(ref, RetrospectiveScore.miss),
                ),
              ),
            ],
          ),
          if (score != null) ...[
            const SizedBox(height: 6),
            TextButton(
              onPressed: () => _setScore(ref, null),
              style: TextButton.styleFrom(
                minimumSize: const Size.fromHeight(28),
                textStyle: const TextStyle(fontSize: 11),
                foregroundColor: colors.sectionLabel,
              ),
              child: const Text('Clear score'),
            ),
          ],
        ],
      ),
    );
  }

  void _setScore(WidgetRef ref, RetrospectiveScore? score) {
    ref.read(retrospectiveProvider.notifier).setScore(forecast.id, score);
  }
}

class _ScoreButton extends StatelessWidget {
  final String label;
  final bool active;
  final Color activeBg;
  final Color activeText;
  final Color inactiveBorder;
  final Color inactiveText;
  final VoidCallback onTap;

  const _ScoreButton({
    required this.label,
    required this.active,
    required this.activeBg,
    required this.activeText,
    required this.inactiveBorder,
    required this.inactiveText,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: active ? activeBg : Colors.transparent,
      borderRadius: BorderRadius.circular(6),
      child: InkWell(
        borderRadius: BorderRadius.circular(6),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 10),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(6),
            border: Border.all(
              color: active ? activeBg : inactiveBorder,
              width: 0.5,
            ),
          ),
          child: Center(
            child: Text(
              label,
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w500,
                letterSpacing: 0.5,
                color: active ? activeText : inactiveText,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
