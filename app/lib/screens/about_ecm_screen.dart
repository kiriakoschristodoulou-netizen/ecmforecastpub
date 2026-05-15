// lib/screens/about_ecm_screen.dart
//
// Educational screen explaining the Economic Confidence Model framework
// the app is built around. Written carefully to:
//   - Describe the mathematical structure of the model (Pi cycle,
//     8.6yr wave, 309.6yr supercycle) without attributing analysis
//     to any specific person
//   - Frame forecasts as model output, not predictions of truth
//   - Note the interpretive nature of the "why this matters"
//     synthesis text
//
// Reached via the help icon in the home screen AppBar.

import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

class AboutEcmScreen extends StatelessWidget {
  const AboutEcmScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('About the ECM')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: const [
            _SectionTitle('The Economic Confidence Model'),
            SizedBox(height: 8),
            _Paragraph(
              'The Economic Confidence Model (ECM) is a long-running '
              'cyclical framework for tracking shifts in business, political, '
              'and financial confidence. It treats history as a repeating '
              'pattern of waves whose turning points can be projected '
              'forward using fixed cycle lengths.',
            ),
            SizedBox(height: 16),
            _Paragraph(
              'This app shows the dates the model points to, plus a brief '
              'note on why each date may matter. The dates themselves are '
              'mathematical projections of the cycle; the explanations are '
              'interpretive context, not predictions of specific events.',
            ),
            SizedBox(height: 24),

            _SectionTitle('The cycle math'),
            SizedBox(height: 8),
            _Paragraph(
              'The model uses three nested cycle lengths:',
            ),
            SizedBox(height: 8),
            _BulletPoint(
              'Pi cycle: 31.4 years. A full long-form rotation through '
              'expansion and contraction.',
            ),
            _BulletPoint(
              'ECM wave: 8.6 years. One quarter of the Pi cycle. Most '
              'short-term turning points fall on wave boundaries.',
            ),
            _BulletPoint(
              '309.6-year supercycle: 36 Pi cycles, or 6 great waves. Sets '
              'the multi-generational backdrop.',
            ),
            SizedBox(height: 16),
            _Paragraph(
              'Dates are sometimes published in decimal-year form (for '
              'example, 2026.496). The fractional part is the day of the '
              'year as a fraction: 0.5 is roughly July 1.',
            ),
            SizedBox(height: 24),

            _SectionTitle('How to read the forecasts'),
            SizedBox(height: 8),
            _Paragraph(
              'Each card shows a date the model has marked. The category '
              'badge tells you what kind of turning point it is — an ECM '
              'wave change, an asset panic cycle, a long-cycle inflection, '
              'and so on.',
            ),
            SizedBox(height: 12),
            _Paragraph(
              'The CONVERGENCE badge appears when multiple distinct forces '
              'cluster around the same date — for example, a central bank '
              'meeting, an election, and a model-projected turning point '
              'all within a narrow window. Dense clusters tend to be the '
              'periods worth watching most carefully.',
            ),
            SizedBox(height: 12),
            _Paragraph(
              'HIT and MISS buttons on past cards let you score the '
              'model in retrospect. Your hit rate accumulates locally on '
              'your device and shows in Settings.',
            ),
            SizedBox(height: 24),

            _SectionTitle('What this is not'),
            SizedBox(height: 8),
            _Paragraph(
              'This is not investment advice. The cycle dates are not '
              'guarantees that anything will happen on or near them. The '
              '"why this matters" notes are produced by an AI language '
              'model synthesizing publicly available context; they are '
              'interpretive commentary, not the published views of any '
              'specific analyst.',
            ),
            SizedBox(height: 12),
            _Paragraph(
              'Use the forecasts as a lens for paying attention, not as a '
              'directive for action.',
            ),
          ],
        ),
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  final String text;
  const _SectionTitle(this.text);

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: const TextStyle(
        fontSize: 16,
        fontWeight: FontWeight.w600,
      ),
    );
  }
}

class _Paragraph extends StatelessWidget {
  final String text;
  const _Paragraph(this.text);

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: const TextStyle(fontSize: 13, height: 1.55),
    );
  }
}

class _BulletPoint extends StatelessWidget {
  final String text;
  const _BulletPoint(this.text);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(left: 12, top: 4, bottom: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Padding(
            padding: EdgeInsets.only(top: 6, right: 8),
            child: Text('\u2022', style: TextStyle(fontSize: 10)),
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
