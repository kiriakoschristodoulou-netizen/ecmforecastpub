// lib/screens/archive_screen.dart
//
// Past forecasts older than 60 days. Same EventCard widget as the home
// screen; never pinned. Sorted newest-first.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/forecast.dart';
import '../providers/events_provider.dart';
import '../theme/app_theme.dart';
import '../widgets/event_card.dart';
import 'event_detail_screen.dart';

class ArchiveScreen extends ConsumerWidget {
  const ArchiveScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final feedAsync = ref.watch(eventsFeedProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Archive')),
      body: feedAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (err, _) => Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Text(
              'Failed to load: $err',
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 12),
            ),
          ),
        ),
        data: (feed) => _ArchiveBody(forecasts: feed.sortedByDate),
      ),
    );
  }
}

class _ArchiveBody extends StatelessWidget {
  final List<Forecast> forecasts;

  const _ArchiveBody({required this.forecasts});

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final archived = forecasts
        .where((f) => f.isPast() && f.daysUntil() < -60)
        .toList();
    archived.sort((a, b) => b.date.compareTo(a.date));

    if (archived.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(40),
          child: Text(
            'No archived forecasts yet.\n'
            'Forecasts older than 60 days move here automatically.',
            textAlign: TextAlign.center,
            style: TextStyle(color: colors.hintText, height: 1.4),
          ),
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      itemCount: archived.length,
      itemBuilder: (context, i) {
        final f = archived[i];
        return EventCard(
          forecast: f,
          isPinned: false,
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => EventDetailScreen(forecast: f),
            ),
          ),
        );
      },
    );
  }
}
