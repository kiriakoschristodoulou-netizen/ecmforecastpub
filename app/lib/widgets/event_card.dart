// lib/widgets/event_card.dart
//
// One forecast card on the home screen. All visual state derives from
// the Forecast object plus the isPinned flag plus the user's local
// HIT/MISS retrospective (for past forecasts).
//
// All colors come from AppColors theme extension (light + dark palettes).

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../models/forecast.dart';
import '../providers/date_format_provider.dart';
import '../providers/retrospective.dart';
import '../theme/app_theme.dart';
import 'countdown_text.dart';

class EventCard extends ConsumerWidget {
  final Forecast forecast;
  final bool isPinned;
  final VoidCallback onTap;

  const EventCard({
    super.key,
    required this.forecast,
    required this.isPinned,
    required this.onTap,
  });

  bool get _isPast => forecast.isPast();
  bool get _isHighImportance => forecast.importance == Importance.high;
  bool get _showConvergence => forecast.isConvergence && _isHighImportance;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final colors = context.appColors;
    final RetrospectiveScore? score = _isPast
        ? ref.watch(retrospectiveProvider)[forecast.id]
        : null;
    final pattern = ref.watch(dateFormatProvider);
    final dateFormatted = DateFormat(pattern).format(forecast.date);

    final _CardVisuals v = _resolveVisuals(colors, score);

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Material(
        elevation: v.elevation,
        borderRadius: v.radius,
        color: v.bg,
        surfaceTintColor: Colors.transparent,
        child: InkWell(
          borderRadius: v.radius,
          onTap: onTap,
          child: Container(
            decoration: BoxDecoration(
              borderRadius: v.radius,
              border: Border.all(color: v.borderColor, width: v.borderWidth),
            ),
            padding: v.padding,
            child: Stack(
              children: [
                _buildBody(v, score, dateFormatted, colors),
                if (_showConvergence)
                  Positioned(
                    top: 0,
                    right: 0,
                    child: _ConvergenceBadge(colors: colors),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  _CardVisuals _resolveVisuals(AppColors colors, RetrospectiveScore? score) {
    if (_isPast) {
      Color bg;
      Color borderColor;
      switch (score) {
        case RetrospectiveScore.hit:
          bg = colors.pastHitBg;
          borderColor = colors.pastHitBorder;
        case RetrospectiveScore.miss:
          bg = colors.pastMissBg;
          borderColor = colors.pastMissBorder;
        case null:
          bg = colors.pastBg;
          borderColor = colors.pastBorder;
      }
      return _CardVisuals(
        bg: bg,
        borderColor: borderColor,
        titleColor: colors.pastTitle,
        subtitleColor: colors.pastSubtitle,
        elevation: 0,
        borderWidth: 0.5,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        radius: BorderRadius.circular(8),
        layout: _CardLayout.compact,
      );
    }
    if (isPinned) {
      return _CardVisuals(
        bg: colors.nearestBg,
        borderColor: colors.nearestBorder,
        titleColor: colors.nearestTitle,
        subtitleColor: colors.nearestSubtitle,
        elevation: 8,
        borderWidth: 1.5,
        padding: const EdgeInsets.all(16),
        radius: BorderRadius.circular(12),
        layout: _CardLayout.pinned,
      );
    }
    if (_isHighImportance) {
      return _CardVisuals(
        bg: colors.upcomingBg,
        borderColor: colors.upcomingBorder,
        titleColor: colors.upcomingTitle,
        subtitleColor: colors.upcomingSubtitle,
        elevation: 6,
        borderWidth: 0.5,
        padding: const EdgeInsets.all(14),
        radius: BorderRadius.circular(10),
        layout: _CardLayout.large,
      );
    }
    return _CardVisuals(
      bg: colors.upcomingBg,
      borderColor: colors.upcomingBorder,
      titleColor: colors.upcomingTitle,
      subtitleColor: colors.upcomingSubtitle,
      elevation: 2,
      borderWidth: 0.5,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      radius: BorderRadius.circular(8),
      layout: _CardLayout.compact,
    );
  }

  Widget _buildBody(_CardVisuals v, RetrospectiveScore? score,
      String dateFormatted, AppColors colors) {
    final daysUntil = forecast.daysUntil();
    final subtitleSuffix =
        (forecast.subtitle == null || forecast.subtitle!.isEmpty)
            ? ''
            : ' \u2022 ${forecast.subtitle}';
    final subtitleLine = '$dateFormatted$subtitleSuffix';

    switch (v.layout) {
      case _CardLayout.pinned:
        return _PinnedLayout(
          title: forecast.title,
          subtitle: subtitleLine,
          daysUntil: daysUntil,
          titleColor: v.titleColor,
          subtitleColor: v.subtitleColor,
          rightPadForBadge: _showConvergence,
        );
      case _CardLayout.large:
        return _LargeLayout(
          title: forecast.title,
          subtitle: subtitleLine,
          daysUntil: daysUntil,
          titleColor: v.titleColor,
          subtitleColor: v.subtitleColor,
          rightPadForBadge: _showConvergence,
        );
      case _CardLayout.compact:
        return _CompactLayout(
          title: forecast.title,
          subtitle: subtitleLine,
          daysUntil: daysUntil,
          titleColor: v.titleColor,
          subtitleColor: v.subtitleColor,
          isPast: _isPast,
          score: score,
          colors: colors,
        );
    }
  }
}

enum _CardLayout { pinned, large, compact }

class _CardVisuals {
  final Color bg;
  final Color borderColor;
  final Color titleColor;
  final Color subtitleColor;
  final double elevation;
  final double borderWidth;
  final EdgeInsets padding;
  final BorderRadius radius;
  final _CardLayout layout;

  const _CardVisuals({
    required this.bg,
    required this.borderColor,
    required this.titleColor,
    required this.subtitleColor,
    required this.elevation,
    required this.borderWidth,
    required this.padding,
    required this.radius,
    required this.layout,
  });
}

class _PinnedLayout extends StatelessWidget {
  final String title;
  final String subtitle;
  final int daysUntil;
  final Color titleColor;
  final Color subtitleColor;
  final bool rightPadForBadge;

  const _PinnedLayout({
    required this.title,
    required this.subtitle,
    required this.daysUntil,
    required this.titleColor,
    required this.subtitleColor,
    required this.rightPadForBadge,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          'UP NEXT',
          style: TextStyle(
            fontSize: 10,
            letterSpacing: 0.5,
            fontWeight: FontWeight.w500,
            color: titleColor,
          ),
        ),
        const SizedBox(height: 3),
        Padding(
          padding: EdgeInsets.only(right: rightPadForBadge ? 80 : 0),
          child: Text(
            title,
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w500,
              color: titleColor,
              height: 1.25,
            ),
          ),
        ),
        const SizedBox(height: 4),
        Text(
          subtitle,
          style: TextStyle(fontSize: 12, color: subtitleColor),
        ),
        const SizedBox(height: 10),
        CountdownText(
          daysUntil: daysUntil,
          size: CountdownSize.large,
          numberColor: titleColor,
          labelColor: subtitleColor,
        ),
      ],
    );
  }
}

class _LargeLayout extends StatelessWidget {
  final String title;
  final String subtitle;
  final int daysUntil;
  final Color titleColor;
  final Color subtitleColor;
  final bool rightPadForBadge;

  const _LargeLayout({
    required this.title,
    required this.subtitle,
    required this.daysUntil,
    required this.titleColor,
    required this.subtitleColor,
    required this.rightPadForBadge,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Padding(
          padding: EdgeInsets.only(right: rightPadForBadge ? 80 : 0),
          child: Text(
            title,
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w500,
              color: titleColor,
              height: 1.25,
            ),
          ),
        ),
        const SizedBox(height: 3),
        Text(
          subtitle,
          style: TextStyle(fontSize: 11, color: subtitleColor),
        ),
        const SizedBox(height: 8),
        CountdownText(
          daysUntil: daysUntil,
          size: CountdownSize.normal,
          numberColor: titleColor,
          labelColor: subtitleColor,
        ),
      ],
    );
  }
}

class _CompactLayout extends StatelessWidget {
  final String title;
  final String subtitle;
  final int daysUntil;
  final Color titleColor;
  final Color subtitleColor;
  final bool isPast;
  final RetrospectiveScore? score;
  final AppColors colors;

  const _CompactLayout({
    required this.title,
    required this.subtitle,
    required this.daysUntil,
    required this.titleColor,
    required this.subtitleColor,
    required this.isPast,
    required this.score,
    required this.colors,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                title,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w500,
                  color: titleColor,
                  height: 1.25,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 2),
              Text(
                subtitle,
                style: TextStyle(fontSize: 11, color: subtitleColor),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        ),
        const SizedBox(width: 8),
        _CompactSideElement(
          isPast: isPast,
          daysUntil: daysUntil,
          score: score,
          titleColor: titleColor,
          subtitleColor: subtitleColor,
          colors: colors,
        ),
      ],
    );
  }
}

class _CompactSideElement extends StatelessWidget {
  final bool isPast;
  final int daysUntil;
  final RetrospectiveScore? score;
  final Color titleColor;
  final Color subtitleColor;
  final AppColors colors;

  const _CompactSideElement({
    required this.isPast,
    required this.daysUntil,
    required this.score,
    required this.titleColor,
    required this.subtitleColor,
    required this.colors,
  });

  @override
  Widget build(BuildContext context) {
    if (!isPast) {
      return CountdownText(
        daysUntil: daysUntil,
        size: CountdownSize.compact,
        numberColor: titleColor,
        labelColor: subtitleColor,
      );
    }

    if (score == RetrospectiveScore.hit) {
      return _ScorePill(
        label: 'HIT',
        bg: colors.hitPillBg,
        textColor: colors.hitPillText,
      );
    }
    if (score == RetrospectiveScore.miss) {
      return _ScorePill(
        label: 'MISS',
        bg: colors.missPillBg,
        textColor: colors.missPillText,
      );
    }
    return Text(
      'Tap to score',
      style: TextStyle(
        fontSize: 10,
        color: subtitleColor.withValues(alpha: 0.8),
        fontStyle: FontStyle.italic,
      ),
    );
  }
}

class _ScorePill extends StatelessWidget {
  final String label;
  final Color bg;
  final Color textColor;

  const _ScorePill({
    required this.label,
    required this.bg,
    required this.textColor,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w500,
          letterSpacing: 0.4,
          color: textColor,
        ),
      ),
    );
  }
}

class _ConvergenceBadge extends StatelessWidget {
  final AppColors colors;
  const _ConvergenceBadge({required this.colors});

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
