// lib/screens/home_screen.dart
//
// Main home screen. Layout:
//   - [Personal builds only] PERSONAL BUILD banner
//   - Update banner (when new version available, dismissible)
//   - "Show N earlier forecasts" button (when past forecasts exist)
//   - Past forecasts (when expanded)
//   - Today divider
//   - Pinned nearest upcoming card
//   - Other upcoming forecasts

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:url_launcher/url_launcher.dart';

import '../config/build_mode.dart';
import '../models/events_feed.dart';
import '../models/forecast.dart';
import '../providers/events_provider.dart';
import '../providers/expanded_past_provider.dart';
import '../providers/update_provider.dart';
import '../services/update_service.dart';
import '../theme/app_theme.dart';
import '../widgets/event_card.dart';
import 'event_detail_screen.dart';
import 'settings_screen.dart';

/// In-memory dismissal flag. Resets on app restart.
final updateBannerDismissedProvider = StateProvider<bool>((ref) => false);

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final feedAsync = ref.watch(eventsFeedProvider);
    final updateAsync = ref.watch(updateStatusProvider);
    final bannerDismissed = ref.watch(updateBannerDismissedProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('ECM Forecasting Alerts'),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings_outlined),
            tooltip: 'Settings',
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const SettingsScreen()),
            ),
          ),
        ],
      ),
      body: Column(
        children: [
          // Friends builds: no banner (final UX).
          // Personal builds: keep the indicator so we always know which APK is running.
          if (isPersonalBuild) const _PersonalBuildBanner(),
          updateAsync.maybeWhen(
            data: (status) {
              if (!status.hasUpdate || bannerDismissed) {
                return const SizedBox.shrink();
              }
              return _UpdateBanner(
                status: status,
                onDismiss: () => ref
                    .read(updateBannerDismissedProvider.notifier)
                    .state = true,
              );
            },
            orElse: () => const SizedBox.shrink(),
          ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: () async {
                ref.invalidate(eventsFeedProvider);
                ref.invalidate(updateStatusProvider);
                await ref.read(eventsFeedProvider.future);
              },
              child: feedAsync.when(
                loading: () => const _LoadingScroll(),
                error: (err, _) => _ErrorScroll(error: err),
                data: (feed) => _ForecastList(feed: feed),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _PersonalBuildBanner extends StatelessWidget {
  const _PersonalBuildBanner();

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final bg = isDark ? const Color(0xFF4A3A0F) : Colors.amber.shade200;
    final fg =
        isDark ? const Color(0xFFE8D7B3) : Colors.amber.shade900;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: 4),
      color: bg,
      child: Text(
        'PERSONAL BUILD',
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w500,
          letterSpacing: 0.5,
          color: fg,
        ),
        textAlign: TextAlign.center,
      ),
    );
  }
}

class _UpdateBanner extends StatelessWidget {
  final UpdateStatus status;
  final VoidCallback onDismiss;

  const _UpdateBanner({required this.status, required this.onDismiss});

  Future<void> _openReleaseUrl(BuildContext context) async {
    final uri = Uri.tryParse(status.releaseUrl);
    if (uri == null) return;
    try {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } catch (_) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Could not open release page')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    return Container(
      width: double.infinity,
      color: colors.updateBannerBg,
      padding: const EdgeInsets.fromLTRB(12, 8, 8, 8),
      child: Row(
        children: [
          Icon(Icons.system_update_alt,
              size: 18, color: colors.updateBannerAccent),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  'Update available: v${status.latestVersion}',
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                    color: colors.updateBannerTextStrong,
                  ),
                ),
                if (status.releaseNotes != null &&
                    status.releaseNotes!.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Text(
                      status.releaseNotes!,
                      style: TextStyle(
                        fontSize: 11,
                        color: colors.updateBannerText,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
              ],
            ),
          ),
          TextButton(
            onPressed: () => _openReleaseUrl(context),
            style: TextButton.styleFrom(
              foregroundColor: colors.updateBannerAccent,
              padding:
                  const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              minimumSize: const Size(0, 32),
              textStyle: const TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w500,
              ),
            ),
            child: const Text('UPDATE'),
          ),
          IconButton(
            icon: const Icon(Icons.close, size: 16),
            tooltip: 'Dismiss',
            color: colors.updateBannerTextStrong,
            constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
            padding: EdgeInsets.zero,
            onPressed: onDismiss,
          ),
        ],
      ),
    );
  }
}

class _ForecastList extends ConsumerWidget {
  final EventsFeed feed;

  const _ForecastList({required this.feed});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final expanded = ref.watch(expandedPastProvider);
    final all = feed.sortedByDate;

    final past = all.where((f) => f.isPast()).toList();
    final upcoming = all.where((f) => !f.isPast()).toList();

    final mainPast = past.where((f) => f.daysUntil() >= -60).toList();

    final nearest = upcoming.isNotEmpty ? upcoming.first : null;
    final restUpcoming =
        upcoming.length <= 1 ? const <Forecast>[] : upcoming.sublist(1);

    return ListView(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      physics: const AlwaysScrollableScrollPhysics(),
      children: [
        if (mainPast.isNotEmpty) ...[
          _EarlierToggleButton(
            count: mainPast.length,
            expanded: expanded,
            onTap: () => ref.read(expandedPastProvider.notifier).state =
                !expanded,
          ),
          if (expanded) ...[
            const SizedBox(height: 4),
            ...mainPast.map((f) => EventCard(
                  forecast: f,
                  isPinned: false,
                  onTap: () => _openDetail(context, f),
                )),
          ],
        ],
        if (mainPast.isNotEmpty || upcoming.isNotEmpty) const _TodayDivider(),
        if (nearest != null)
          EventCard(
            forecast: nearest,
            isPinned: true,
            onTap: () => _openDetail(context, nearest),
          ),
        ...restUpcoming.map((f) => EventCard(
              forecast: f,
              isPinned: false,
              onTap: () => _openDetail(context, f),
            )),
        if (upcoming.isEmpty)
          Padding(
            padding: const EdgeInsets.all(40),
            child: Center(
              child: Text(
                'No upcoming forecasts',
                style: TextStyle(color: context.appColors.hintText),
              ),
            ),
          ),
        const SizedBox(height: 40),
      ],
    );
  }

  void _openDetail(BuildContext context, Forecast forecast) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => EventDetailScreen(forecast: forecast),
      ),
    );
  }
}

class _EarlierToggleButton extends StatelessWidget {
  final int count;
  final bool expanded;
  final VoidCallback onTap;

  const _EarlierToggleButton({
    required this.count,
    required this.expanded,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final label = expanded
        ? 'Hide earlier forecasts'
        : 'Show $count earlier forecast${count == 1 ? '' : 's'}';
    return SizedBox(
      width: double.infinity,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: OutlinedButton.icon(
          onPressed: onTap,
          icon: Icon(
            expanded ? Icons.expand_more : Icons.expand_less,
            size: 18,
          ),
          label: Text(label),
          style: OutlinedButton.styleFrom(
            minimumSize: const Size.fromHeight(40),
            foregroundColor: colors.sectionLabel,
            side: BorderSide(color: colors.buttonInactiveBorder, width: 0.5),
          ),
        ),
      ),
    );
  }
}

class _TodayDivider extends StatelessWidget {
  const _TodayDivider();

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final today = DateFormat('d MMM').format(DateTime.now()).toUpperCase();
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 4),
      child: Row(
        children: [
          Expanded(child: Container(height: 0.5, color: colors.dividerSoft)),
          const SizedBox(width: 8),
          Text(
            'TODAY \u2022 $today',
            style: TextStyle(
              fontSize: 10,
              letterSpacing: 0.5,
              color: colors.sectionLabel,
            ),
          ),
          const SizedBox(width: 8),
          Expanded(child: Container(height: 0.5, color: colors.dividerSoft)),
        ],
      ),
    );
  }
}

class _LoadingScroll extends StatelessWidget {
  const _LoadingScroll();

  @override
  Widget build(BuildContext context) {
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      children: const [
        SizedBox(height: 100),
        Center(
          child: Column(
            children: [
              CircularProgressIndicator(),
              SizedBox(height: 16),
              Text('Fetching forecasts...'),
            ],
          ),
        ),
      ],
    );
  }
}

class _ErrorScroll extends StatelessWidget {
  final Object error;
  const _ErrorScroll({required this.error});

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(24),
      children: [
        const SizedBox(height: 60),
        const Icon(Icons.error_outline, size: 48, color: Colors.redAccent),
        const SizedBox(height: 16),
        const Text(
          'Feed fetch failed',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 18, fontWeight: FontWeight.w500),
        ),
        const SizedBox(height: 8),
        Text(
          error.toString(),
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 12),
        ),
        const SizedBox(height: 20),
        Center(
          child: Text(
            'Pull to retry',
            style: TextStyle(fontSize: 12, color: colors.hintText),
          ),
        ),
      ],
    );
  }
}
