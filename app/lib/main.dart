// lib/main.dart
//
// App entry point. Initializes:
//   - Flutter binding (required before SharedPreferences)
//   - SharedPreferences (for retrospectives + settings)
//   - NotificationService (for 3-day-before reminders)
//
// Theme: light + dark palettes from app_theme.dart, mode selected by
// themeModeProvider (defaults to ThemeMode.system).

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'providers/preferences_provider.dart';
import 'providers/theme_mode_provider.dart';
import 'screens/home_screen.dart';
import 'services/notification_service.dart';
import 'theme/app_theme.dart';
import 'widgets/app_lifecycle.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  final prefs = await SharedPreferences.getInstance();
  await NotificationService.init();

  runApp(
    ProviderScope(
      overrides: [
        sharedPreferencesProvider.overrideWithValue(prefs),
      ],
      child: const EcmForecastApp(),
    ),
  );
}

class EcmForecastApp extends ConsumerWidget {
  const EcmForecastApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final themeMode = ref.watch(themeModeProvider);

    return MaterialApp(
      title: 'ECM Forecasting Alerts',
      debugShowCheckedModeBanner: false,
      theme: buildLightTheme(),
      darkTheme: buildDarkTheme(),
      themeMode: themeMode,
      home: const AppLifecycle(child: HomeScreen()),
    );
  }
}
