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
  bool get _showConvergence => forecast.isConvergence;

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
          category: forecast.category,
          colors: colors,
        );
      case _CardLayout.large:
        return _LargeLayout(
          title: forecast.title,
          subtitle: subtitleLine,
          daysUntil: daysUntil,
          titleColor: v.titleColor,
          subtitleColor: v.subtitleColor,
          rightPadForBadge: _showConvergence,
          category: forecast.category,
          colors: colors,
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
            category: forecast.category,
            showConvergence: _showConvergence,
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

/// Small colored pill showing the forecast category. Color tokens come
/// from AppColors so dark mode works correctly. Hidden for [other].
class _CategoryBadge extends StatelessWidget {
  final ForecastCategory category;
  final AppColors colors;

  const _CategoryBadge({
    required this.category,
    required this.colors,
  });

  @override
  Widget build(BuildContext context) {
    // Don't show a badge for the "other" fallback - it adds noise.
    if (category == ForecastCategory.other) return const SizedBox.shrink();

    final (Color bg, Color text) = _resolveColors();
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(3),
      ),
      child: Text(
        category.badgeLabel,
        style: TextStyle(
          fontSize: 9,
          fontWeight: FontWeight.w600,
          letterSpacing: 0.4,
          color: text,
        ),
      ),
    );
  }

  (Color, Color) _resolveColors() {
    switch (category) {
      case ForecastCategory.ecmPanic:
        return (colors.catEcmPanicBg, colors.catEcmPanicText);
      case ForecastCategory.ecmPiTarget:
        return (colors.catPiTargetBg, colors.catPiTargetText);
      case ForecastCategory.geopoliticalCycle:
        return (colors.catGeopoliticalBg, colors.catGeopoliticalText);
      case ForecastCategory.longCycle:
        return (colors.catLongCycleBg, colors.catLongCycleText);
      case ForecastCategory.assetPanicCycle:
        return (colors.catAssetPanicBg, colors.catAssetPanicText);
      case ForecastCategory.naturalDisasters:
        return (colors.catNaturalBg, colors.catNaturalText);
      case ForecastCategory.other:
        return (colors.catOtherBg, colors.catOtherText);
    }
  }
}

class _PinnedLayout extends StatelessWidget {
  final String title;
  final String subtitle;
  final int daysUntil;
  final Color titleColor;
  final Color subtitleColor;
  final bool rightPadForBadge;
  final ForecastCategory category;
  final AppColors colors;

  const _PinnedLayout({
    required this.title,
    required this.subtitle,
    required this.daysUntil,
    required this.titleColor,
    required this.subtitleColor,
    required this.rightPadForBadge,
    required this.category,
    required this.colors,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          crossAxisAlignment: CrossAxisAlignment.center,
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
            // Don't show category badge to the right when the CONVERGENCE
            // badge is occupying that corner.
            if (!rightPadForBadge)
              _CategoryBadge(category: category, colors: colors),
          ],
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
  final ForecastCategory category;
  final AppColors colors;

  const _LargeLayout({
    required this.title,
    required this.subtitle,
    required this.daysUntil,
    required this.titleColor,
    required this.subtitleColor,
    required this.rightPadForBadge,
    required this.category,
    required this.colors,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        // Category badge as small top-left pill (only when CONVERGENCE
        // isn't taking the top-right).
        if (!rightPadForBadge &&
            category != ForecastCategory.other) ...[
          _CategoryBadge(category: category, colors: colors),
          const SizedBox(height: 6),
        ],
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
  final ForecastCategory category;
  final bool showConvergence;

  const _CompactLayout({
    required this.title,
    required this.subtitle,
    required this.daysUntil,
    required this.titleColor,
    required this.subtitleColor,
    required this.isPast,
    required this.score,
    required this.colors,
    required this.category,
    required this.showConvergence,
  });

@override
  Widget build(BuildContext context) {
    final hasBadge = category != ForecastCategory.other;

    final titleAndSubtitle = Column(
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
        Row(
          children: [
            if (hasBadge) ...[
              _CategoryBadge(category: category, colors: colors),
              const SizedBox(width: 6),
            ],
            Flexible(
              child: Text(
                subtitle,
                style: TextStyle(fontSize: 11, color: subtitleColor),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
      ],
    );

    final sideElement = _CompactSideElement(
      isPast: isPast,
      daysUntil: daysUntil,
      score: score,
      titleColor: titleColor,
      subtitleColor: subtitleColor,
      colors: colors,
    );

    // When CONVERGENCE badge occupies the top-right corner, the side
    // element (days/score) drops to a second row so they don't overlap.
    // Otherwise, the layout is the original side-by-side Row.
    if (showConvergence) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          titleAndSubtitle,
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerRight,
            child: sideElement,
          ),
        ],
      );
    }

    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Expanded(child: titleAndSubtitle),
        const SizedBox(width: 8),
        sideElement,
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

class _ConvergenceBadge extends StatefulWidget {
  final AppColors colors;
  const _ConvergenceBadge({required this.colors});

  @override
  State<_ConvergenceBadge> createState() => _ConvergenceBadgeState();
}

class _ConvergenceBadgeState extends State<_ConvergenceBadge>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _opacity;
  late final Animation<double> _scale;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    )..repeat(reverse: true);
    final curved = CurvedAnimation(
      parent: _controller,
      curve: Curves.easeInOut,
    );
    _opacity = Tween<double>(begin: 1.0, end: 0.55).animate(curved);
    _scale = Tween<double>(begin: 1.0, end: 1.06).animate(curved);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: _opacity,
      child: ScaleTransition(
        scale: _scale,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
          decoration: BoxDecoration(
            color: widget.colors.convergenceBg,
            borderRadius: BorderRadius.circular(4),
          ),
          child: Text(
            'CONVERGENCE!',
            style: TextStyle(
              fontSize: 9,
              fontWeight: FontWeight.w500,
              letterSpacing: 0.6,
              color: widget.colors.convergenceText,
            ),
          ),
        ),
      ),
    );
  }
}