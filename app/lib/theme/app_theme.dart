// lib/theme/app_theme.dart
//
// Centralized theme system. Every color used by the app's widgets comes
// through AppColors via Theme.of(context).extension<AppColors>().
//
// Two palettes (light + dark) are defined as constant AppColors instances.
// The MaterialApp's themeMode determines which gets used at runtime.
//
// Semantic naming, not literal naming. We say "upcomingBg" not "green200"
// so that the same token can resolve to very different colors in dark
// mode without renaming anything in the widgets.

import 'package:flutter/material.dart';

/// Theme extension holding all the app's domain-specific colors.
/// Access via: Theme.of(context).extension<AppColors>()!
@immutable
class AppColors extends ThemeExtension<AppColors> {
  // --- Cards: nearest upcoming (the bright "UP NEXT" pinned card) ---
  final Color nearestBg;
  final Color nearestBorder;
  final Color nearestTitle;
  final Color nearestSubtitle;

  // --- Cards: upcoming (normal upcoming forecasts) ---
  final Color upcomingBg;
  final Color upcomingBorder;
  final Color upcomingTitle;
  final Color upcomingSubtitle;

  // --- Cards: past unflagged ---
  final Color pastBg;
  final Color pastBorder;
  final Color pastTitle;
  final Color pastSubtitle;

  // --- Cards: past + HIT (green-tinted) ---
  final Color pastHitBg;
  final Color pastHitBorder;

  // --- Cards: past + MISS (red-tinted) ---
  final Color pastMissBg;
  final Color pastMissBorder;

  // --- CONVERGENCE! badge ---
  final Color convergenceBg;
  final Color convergenceText;

  // --- HIT/MISS pills on past cards (small in-card labels) ---
  final Color hitPillBg;
  final Color hitPillText;
  final Color missPillBg;
  final Color missPillText;

  // --- Detail screen: importance justification callout (amber) ---
  final Color justificationBg;
  final Color justificationAccent;
  final Color justificationLabel;
  final Color justificationText;

  // --- Detail screen: section labels + body text + list rows ---
  final Color sectionLabel;
  final Color bodyText;
  final Color listDivider;
  final Color listIcon;
  final Color listText;
  final Color listSubtle;

  // --- HIT / MISS score buttons in the detail score panel ---
  final Color scorePanelBg;
  final Color hitButtonActive;
  final Color hitButtonText;
  final Color missButtonActive;
  final Color missButtonText;
  final Color buttonInactiveBorder;
  final Color buttonInactiveText;

  // --- Update banner (info-style, blue) ---
  final Color updateBannerBg;
  final Color updateBannerAccent;
  final Color updateBannerText;
  final Color updateBannerTextStrong;

  // --- Misc utility tokens ---
  final Color dividerSoft;
  final Color hintText;

  // --- Category badges (one bg + one text per ForecastCategory) ---
  // ECM panic / wave inflections - red family
  final Color catEcmPanicBg;
  final Color catEcmPanicText;
  // Pi cycle target - purple family
  final Color catPiTargetBg;
  final Color catPiTargetText;
  // Geopolitical cycle - blue family
  final Color catGeopoliticalBg;
  final Color catGeopoliticalText;
  // Long cycle (war, religion) - bronze/brown family
  final Color catLongCycleBg;
  final Color catLongCycleText;
  // Asset panic cycle - orange family
  final Color catAssetPanicBg;
  final Color catAssetPanicText;
  // Natural disasters - teal family
  final Color catNaturalBg;
  final Color catNaturalText;
  // Other / unknown - neutral grey
  final Color catOtherBg;
  final Color catOtherText;

  const AppColors({
    required this.nearestBg,
    required this.nearestBorder,
    required this.nearestTitle,
    required this.nearestSubtitle,
    required this.upcomingBg,
    required this.upcomingBorder,
    required this.upcomingTitle,
    required this.upcomingSubtitle,
    required this.pastBg,
    required this.pastBorder,
    required this.pastTitle,
    required this.pastSubtitle,
    required this.pastHitBg,
    required this.pastHitBorder,
    required this.pastMissBg,
    required this.pastMissBorder,
    required this.convergenceBg,
    required this.convergenceText,
    required this.hitPillBg,
    required this.hitPillText,
    required this.missPillBg,
    required this.missPillText,
    required this.justificationBg,
    required this.justificationAccent,
    required this.justificationLabel,
    required this.justificationText,
    required this.sectionLabel,
    required this.bodyText,
    required this.listDivider,
    required this.listIcon,
    required this.listText,
    required this.listSubtle,
    required this.scorePanelBg,
    required this.hitButtonActive,
    required this.hitButtonText,
    required this.missButtonActive,
    required this.missButtonText,
    required this.buttonInactiveBorder,
    required this.buttonInactiveText,
    required this.updateBannerBg,
    required this.updateBannerAccent,
    required this.updateBannerText,
    required this.updateBannerTextStrong,
    required this.dividerSoft,
    required this.hintText,
    required this.catEcmPanicBg,
    required this.catEcmPanicText,
    required this.catPiTargetBg,
    required this.catPiTargetText,
    required this.catGeopoliticalBg,
    required this.catGeopoliticalText,
    required this.catLongCycleBg,
    required this.catLongCycleText,
    required this.catAssetPanicBg,
    required this.catAssetPanicText,
    required this.catNaturalBg,
    required this.catNaturalText,
    required this.catOtherBg,
    required this.catOtherText,
  });

  @override
  AppColors copyWith({
    Color? nearestBg,
    Color? nearestBorder,
    Color? nearestTitle,
    Color? nearestSubtitle,
    Color? upcomingBg,
    Color? upcomingBorder,
    Color? upcomingTitle,
    Color? upcomingSubtitle,
    Color? pastBg,
    Color? pastBorder,
    Color? pastTitle,
    Color? pastSubtitle,
    Color? pastHitBg,
    Color? pastHitBorder,
    Color? pastMissBg,
    Color? pastMissBorder,
    Color? convergenceBg,
    Color? convergenceText,
    Color? hitPillBg,
    Color? hitPillText,
    Color? missPillBg,
    Color? missPillText,
    Color? justificationBg,
    Color? justificationAccent,
    Color? justificationLabel,
    Color? justificationText,
    Color? sectionLabel,
    Color? bodyText,
    Color? listDivider,
    Color? listIcon,
    Color? listText,
    Color? listSubtle,
    Color? scorePanelBg,
    Color? hitButtonActive,
    Color? hitButtonText,
    Color? missButtonActive,
    Color? missButtonText,
    Color? buttonInactiveBorder,
    Color? buttonInactiveText,
    Color? updateBannerBg,
    Color? updateBannerAccent,
    Color? updateBannerText,
    Color? updateBannerTextStrong,
    Color? dividerSoft,
    Color? hintText,
    Color? catEcmPanicBg,
    Color? catEcmPanicText,
    Color? catPiTargetBg,
    Color? catPiTargetText,
    Color? catGeopoliticalBg,
    Color? catGeopoliticalText,
    Color? catLongCycleBg,
    Color? catLongCycleText,
    Color? catAssetPanicBg,
    Color? catAssetPanicText,
    Color? catNaturalBg,
    Color? catNaturalText,
    Color? catOtherBg,
    Color? catOtherText,
  }) {
    return AppColors(
      nearestBg: nearestBg ?? this.nearestBg,
      nearestBorder: nearestBorder ?? this.nearestBorder,
      nearestTitle: nearestTitle ?? this.nearestTitle,
      nearestSubtitle: nearestSubtitle ?? this.nearestSubtitle,
      upcomingBg: upcomingBg ?? this.upcomingBg,
      upcomingBorder: upcomingBorder ?? this.upcomingBorder,
      upcomingTitle: upcomingTitle ?? this.upcomingTitle,
      upcomingSubtitle: upcomingSubtitle ?? this.upcomingSubtitle,
      pastBg: pastBg ?? this.pastBg,
      pastBorder: pastBorder ?? this.pastBorder,
      pastTitle: pastTitle ?? this.pastTitle,
      pastSubtitle: pastSubtitle ?? this.pastSubtitle,
      pastHitBg: pastHitBg ?? this.pastHitBg,
      pastHitBorder: pastHitBorder ?? this.pastHitBorder,
      pastMissBg: pastMissBg ?? this.pastMissBg,
      pastMissBorder: pastMissBorder ?? this.pastMissBorder,
      convergenceBg: convergenceBg ?? this.convergenceBg,
      convergenceText: convergenceText ?? this.convergenceText,
      hitPillBg: hitPillBg ?? this.hitPillBg,
      hitPillText: hitPillText ?? this.hitPillText,
      missPillBg: missPillBg ?? this.missPillBg,
      missPillText: missPillText ?? this.missPillText,
      justificationBg: justificationBg ?? this.justificationBg,
      justificationAccent: justificationAccent ?? this.justificationAccent,
      justificationLabel: justificationLabel ?? this.justificationLabel,
      justificationText: justificationText ?? this.justificationText,
      sectionLabel: sectionLabel ?? this.sectionLabel,
      bodyText: bodyText ?? this.bodyText,
      listDivider: listDivider ?? this.listDivider,
      listIcon: listIcon ?? this.listIcon,
      listText: listText ?? this.listText,
      listSubtle: listSubtle ?? this.listSubtle,
      scorePanelBg: scorePanelBg ?? this.scorePanelBg,
      hitButtonActive: hitButtonActive ?? this.hitButtonActive,
      hitButtonText: hitButtonText ?? this.hitButtonText,
      missButtonActive: missButtonActive ?? this.missButtonActive,
      missButtonText: missButtonText ?? this.missButtonText,
      buttonInactiveBorder:
          buttonInactiveBorder ?? this.buttonInactiveBorder,
      buttonInactiveText: buttonInactiveText ?? this.buttonInactiveText,
      updateBannerBg: updateBannerBg ?? this.updateBannerBg,
      updateBannerAccent: updateBannerAccent ?? this.updateBannerAccent,
      updateBannerText: updateBannerText ?? this.updateBannerText,
      updateBannerTextStrong:
          updateBannerTextStrong ?? this.updateBannerTextStrong,
      dividerSoft: dividerSoft ?? this.dividerSoft,
      hintText: hintText ?? this.hintText,
      catEcmPanicBg: catEcmPanicBg ?? this.catEcmPanicBg,
      catEcmPanicText: catEcmPanicText ?? this.catEcmPanicText,
      catPiTargetBg: catPiTargetBg ?? this.catPiTargetBg,
      catPiTargetText: catPiTargetText ?? this.catPiTargetText,
      catGeopoliticalBg: catGeopoliticalBg ?? this.catGeopoliticalBg,
      catGeopoliticalText: catGeopoliticalText ?? this.catGeopoliticalText,
      catLongCycleBg: catLongCycleBg ?? this.catLongCycleBg,
      catLongCycleText: catLongCycleText ?? this.catLongCycleText,
      catAssetPanicBg: catAssetPanicBg ?? this.catAssetPanicBg,
      catAssetPanicText: catAssetPanicText ?? this.catAssetPanicText,
      catNaturalBg: catNaturalBg ?? this.catNaturalBg,
      catNaturalText: catNaturalText ?? this.catNaturalText,
      catOtherBg: catOtherBg ?? this.catOtherBg,
      catOtherText: catOtherText ?? this.catOtherText,
    );
  }

  @override
  AppColors lerp(ThemeExtension<AppColors>? other, double t) {
    if (other is! AppColors) return this;
    return AppColors(
      nearestBg: Color.lerp(nearestBg, other.nearestBg, t)!,
      nearestBorder: Color.lerp(nearestBorder, other.nearestBorder, t)!,
      nearestTitle: Color.lerp(nearestTitle, other.nearestTitle, t)!,
      nearestSubtitle: Color.lerp(nearestSubtitle, other.nearestSubtitle, t)!,
      upcomingBg: Color.lerp(upcomingBg, other.upcomingBg, t)!,
      upcomingBorder: Color.lerp(upcomingBorder, other.upcomingBorder, t)!,
      upcomingTitle: Color.lerp(upcomingTitle, other.upcomingTitle, t)!,
      upcomingSubtitle:
          Color.lerp(upcomingSubtitle, other.upcomingSubtitle, t)!,
      pastBg: Color.lerp(pastBg, other.pastBg, t)!,
      pastBorder: Color.lerp(pastBorder, other.pastBorder, t)!,
      pastTitle: Color.lerp(pastTitle, other.pastTitle, t)!,
      pastSubtitle: Color.lerp(pastSubtitle, other.pastSubtitle, t)!,
      pastHitBg: Color.lerp(pastHitBg, other.pastHitBg, t)!,
      pastHitBorder: Color.lerp(pastHitBorder, other.pastHitBorder, t)!,
      pastMissBg: Color.lerp(pastMissBg, other.pastMissBg, t)!,
      pastMissBorder: Color.lerp(pastMissBorder, other.pastMissBorder, t)!,
      convergenceBg: Color.lerp(convergenceBg, other.convergenceBg, t)!,
      convergenceText: Color.lerp(convergenceText, other.convergenceText, t)!,
      hitPillBg: Color.lerp(hitPillBg, other.hitPillBg, t)!,
      hitPillText: Color.lerp(hitPillText, other.hitPillText, t)!,
      missPillBg: Color.lerp(missPillBg, other.missPillBg, t)!,
      missPillText: Color.lerp(missPillText, other.missPillText, t)!,
      justificationBg: Color.lerp(justificationBg, other.justificationBg, t)!,
      justificationAccent:
          Color.lerp(justificationAccent, other.justificationAccent, t)!,
      justificationLabel:
          Color.lerp(justificationLabel, other.justificationLabel, t)!,
      justificationText:
          Color.lerp(justificationText, other.justificationText, t)!,
      sectionLabel: Color.lerp(sectionLabel, other.sectionLabel, t)!,
      bodyText: Color.lerp(bodyText, other.bodyText, t)!,
      listDivider: Color.lerp(listDivider, other.listDivider, t)!,
      listIcon: Color.lerp(listIcon, other.listIcon, t)!,
      listText: Color.lerp(listText, other.listText, t)!,
      listSubtle: Color.lerp(listSubtle, other.listSubtle, t)!,
      scorePanelBg: Color.lerp(scorePanelBg, other.scorePanelBg, t)!,
      hitButtonActive: Color.lerp(hitButtonActive, other.hitButtonActive, t)!,
      hitButtonText: Color.lerp(hitButtonText, other.hitButtonText, t)!,
      missButtonActive:
          Color.lerp(missButtonActive, other.missButtonActive, t)!,
      missButtonText: Color.lerp(missButtonText, other.missButtonText, t)!,
      buttonInactiveBorder:
          Color.lerp(buttonInactiveBorder, other.buttonInactiveBorder, t)!,
      buttonInactiveText:
          Color.lerp(buttonInactiveText, other.buttonInactiveText, t)!,
      updateBannerBg: Color.lerp(updateBannerBg, other.updateBannerBg, t)!,
      updateBannerAccent:
          Color.lerp(updateBannerAccent, other.updateBannerAccent, t)!,
      updateBannerText:
          Color.lerp(updateBannerText, other.updateBannerText, t)!,
      updateBannerTextStrong:
          Color.lerp(updateBannerTextStrong, other.updateBannerTextStrong, t)!,
      dividerSoft: Color.lerp(dividerSoft, other.dividerSoft, t)!,
      hintText: Color.lerp(hintText, other.hintText, t)!,
      catEcmPanicBg: Color.lerp(catEcmPanicBg, other.catEcmPanicBg, t)!,
      catEcmPanicText: Color.lerp(catEcmPanicText, other.catEcmPanicText, t)!,
      catPiTargetBg: Color.lerp(catPiTargetBg, other.catPiTargetBg, t)!,
      catPiTargetText: Color.lerp(catPiTargetText, other.catPiTargetText, t)!,
      catGeopoliticalBg:
          Color.lerp(catGeopoliticalBg, other.catGeopoliticalBg, t)!,
      catGeopoliticalText:
          Color.lerp(catGeopoliticalText, other.catGeopoliticalText, t)!,
      catLongCycleBg: Color.lerp(catLongCycleBg, other.catLongCycleBg, t)!,
      catLongCycleText:
          Color.lerp(catLongCycleText, other.catLongCycleText, t)!,
      catAssetPanicBg:
          Color.lerp(catAssetPanicBg, other.catAssetPanicBg, t)!,
      catAssetPanicText:
          Color.lerp(catAssetPanicText, other.catAssetPanicText, t)!,
      catNaturalBg: Color.lerp(catNaturalBg, other.catNaturalBg, t)!,
      catNaturalText: Color.lerp(catNaturalText, other.catNaturalText, t)!,
      catOtherBg: Color.lerp(catOtherBg, other.catOtherBg, t)!,
      catOtherText: Color.lerp(catOtherText, other.catOtherText, t)!,
    );
  }
}

/// Light palette - matches the original session-4 mockup.
const AppColors appColorsLight = AppColors(
  nearestBg: Color(0xFF97C459),
  nearestBorder: Color(0xFF3B6D11),
  nearestTitle: Color(0xFF173404),
  nearestSubtitle: Color(0xFF27500A),

  upcomingBg: Color(0xFFEAF3DE),
  upcomingBorder: Color(0xFF639922),
  upcomingTitle: Color(0xFF173404),
  upcomingSubtitle: Color(0xFF3B6D11),

  pastBg: Color(0xFFE8E6DD),
  pastBorder: Color(0xFFB4B2A9),
  pastTitle: Color(0xFF444441),
  pastSubtitle: Color(0xFF5F5E5A),

  pastHitBg: Color(0xFFDDE5D3),
  pastHitBorder: Color(0xFF7A9560),

  pastMissBg: Color(0xFFE5D6D3),
  pastMissBorder: Color(0xFF956060),

  convergenceBg: Color(0xFF185FA5),
  convergenceText: Color(0xFFE6F1FB),

  hitPillBg: Color(0xFFEAF3DE),
  hitPillText: Color(0xFF27500A),
  missPillBg: Color(0xFFFCEBEB),
  missPillText: Color(0xFF791F1F),

  justificationBg: Color(0xFFFAEEDA),
  justificationAccent: Color(0xFFBA7517),
  justificationLabel: Color(0xFF633806),
  justificationText: Color(0xFF412402),

  sectionLabel: Color(0xFF5F5E5A),
  bodyText: Color(0xFF2C2C2A),
  listDivider: Color(0xFFE8E6DD),
  listIcon: Color(0xFF888780),
  listText: Color(0xFF2C2C2A),
  listSubtle: Color(0xFF5F5E5A),

  scorePanelBg: Color(0xFFF1EFE8),
  hitButtonActive: Color(0xFFC0DD97),
  hitButtonText: Color(0xFF173404),
  missButtonActive: Color(0xFFF7C1C1),
  missButtonText: Color(0xFF501313),
  buttonInactiveBorder: Color(0xFFB4B2A9),
  buttonInactiveText: Color(0xFF5F5E5A),

  updateBannerBg: Color(0xFFE6F1FB),
  updateBannerAccent: Color(0xFF185FA5),
  updateBannerText: Color(0xFF0F3F70),
  updateBannerTextStrong: Color(0xFF0F3F70),

  dividerSoft: Color(0xFFD3D1C7),
  hintText: Color(0xFF888780),

  // Category badges - light palette. Soft pastel bgs with deep text.
  catEcmPanicBg: Color(0xFFFBE1DC),
  catEcmPanicText: Color(0xFF8E2A1B),
  catPiTargetBg: Color(0xFFEDE2F4),
  catPiTargetText: Color(0xFF5A2A82),
  catGeopoliticalBg: Color(0xFFDDEAF5),
  catGeopoliticalText: Color(0xFF1F4F80),
  catLongCycleBg: Color(0xFFE9DFCD),
  catLongCycleText: Color(0xFF5C4220),
  catAssetPanicBg: Color(0xFFFCE3CB),
  catAssetPanicText: Color(0xFF8A4A0E),
  catNaturalBg: Color(0xFFD5ECEA),
  catNaturalText: Color(0xFF1E5A55),
  catOtherBg: Color(0xFFE0DED5),
  catOtherText: Color(0xFF55544F),
);

/// Dark palette - same semantic structure, tuned for a near-black bg.
/// Background colors deliberately stay vivid (not desaturated grey) so
/// the importance/state hierarchy survives the mode switch. The "green"
/// reads as a deep forest tone in dark mode rather than a pastel.
const AppColors appColorsDark = AppColors(
  // Nearest upcoming: deep saturated green still feels like the focal
  // point against a near-black background.
  nearestBg: Color(0xFF3F6A1A),
  nearestBorder: Color(0xFF8FC04A),
  nearestTitle: Color(0xFFE9F4D6),
  nearestSubtitle: Color(0xFFBAD693),

  // Upcoming: muted forest green.
  upcomingBg: Color(0xFF2A3D1A),
  upcomingBorder: Color(0xFF4F7B1F),
  upcomingTitle: Color(0xFFD9E8C2),
  upcomingSubtitle: Color(0xFFA8C57A),

  // Past unflagged: warm dark grey.
  pastBg: Color(0xFF2D2C29),
  pastBorder: Color(0xFF4F4E48),
  pastTitle: Color(0xFFC9C7BE),
  pastSubtitle: Color(0xFF8E8C82),

  // Past + HIT: dark green-tinted.
  pastHitBg: Color(0xFF2E3A25),
  pastHitBorder: Color(0xFF6F9252),

  // Past + MISS: dark red-tinted.
  pastMissBg: Color(0xFF3D2A28),
  pastMissBorder: Color(0xFF8E5757),

  // CONVERGENCE! badge: brightened blue for dark-bg contrast.
  convergenceBg: Color(0xFF4192E0),
  convergenceText: Color(0xFF0A1E33),

  // HIT/MISS pills: dark tints.
  hitPillBg: Color(0xFF2E4017),
  hitPillText: Color(0xFFB8D784),
  missPillBg: Color(0xFF3F1B1B),
  missPillText: Color(0xFFE8A3A3),

  // Importance justification (amber): deep amber.
  justificationBg: Color(0xFF3A2B12),
  justificationAccent: Color(0xFFE0A050),
  justificationLabel: Color(0xFFE5B36C),
  justificationText: Color(0xFFE8D7B3),

  // Body / list / labels.
  sectionLabel: Color(0xFF9C9A91),
  bodyText: Color(0xFFD7D5CC),
  listDivider: Color(0xFF3A3936),
  listIcon: Color(0xFF8E8C82),
  listText: Color(0xFFD7D5CC),
  listSubtle: Color(0xFF9C9A91),

  // Score panel + buttons.
  scorePanelBg: Color(0xFF252523),
  hitButtonActive: Color(0xFF4D6F23),
  hitButtonText: Color(0xFFE9F4D6),
  missButtonActive: Color(0xFF783131),
  missButtonText: Color(0xFFF7DCDC),
  buttonInactiveBorder: Color(0xFF4F4E48),
  buttonInactiveText: Color(0xFF9C9A91),

  // Update banner (blue, dark variant).
  updateBannerBg: Color(0xFF142A45),
  updateBannerAccent: Color(0xFF4192E0),
  updateBannerText: Color(0xFFB8D5F0),
  updateBannerTextStrong: Color(0xFFE6F1FB),

  // Misc.
  dividerSoft: Color(0xFF3A3936),
  hintText: Color(0xFF8E8C82),

  // Category badges - dark palette. Deep saturated bgs with bright text.
  catEcmPanicBg: Color(0xFF4A1F18),
  catEcmPanicText: Color(0xFFF2BFB7),
  catPiTargetBg: Color(0xFF2E1B47),
  catPiTargetText: Color(0xFFD7BFEC),
  catGeopoliticalBg: Color(0xFF15304E),
  catGeopoliticalText: Color(0xFFB8D5F0),
  catLongCycleBg: Color(0xFF3A2D17),
  catLongCycleText: Color(0xFFE0C99A),
  catAssetPanicBg: Color(0xFF4A2D10),
  catAssetPanicText: Color(0xFFF2C28E),
  catNaturalBg: Color(0xFF153833),
  catNaturalText: Color(0xFFA7D8D3),
  catOtherBg: Color(0xFF35342F),
  catOtherText: Color(0xFFB8B6AD),
);

/// Convenience accessor. Use in widgets like:
///   final colors = context.appColors;
extension AppThemeContext on BuildContext {
  AppColors get appColors =>
      Theme.of(this).extension<AppColors>() ?? appColorsLight;
}

/// Build the Material light theme with our AppColors extension attached.
ThemeData buildLightTheme() {
  return ThemeData(
    brightness: Brightness.light,
    colorScheme: ColorScheme.fromSeed(
      seedColor: const Color(0xFF3B6D11),
      brightness: Brightness.light,
    ),
    useMaterial3: true,
    fontFamily: 'Roboto',
    extensions: const [appColorsLight],
  );
}

/// Build the Material dark theme with our AppColors extension attached.
ThemeData buildDarkTheme() {
  return ThemeData(
    brightness: Brightness.dark,
    colorScheme: ColorScheme.fromSeed(
      seedColor: const Color(0xFF8FC04A),
      brightness: Brightness.dark,
    ),
    useMaterial3: true,
    fontFamily: 'Roboto',
    extensions: const [appColorsDark],
  );
}
