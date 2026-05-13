// lib/widgets/countdown_text.dart
//
// Small reusable widget showing days remaining or days ago for a forecast.
// Three size variants for different card sizes.

import 'package:flutter/material.dart';

enum CountdownSize { compact, normal, large }

class CountdownText extends StatelessWidget {
  final int daysUntil;
  final CountdownSize size;
  final Color numberColor;
  final Color labelColor;

  const CountdownText({
    super.key,
    required this.daysUntil,
    this.size = CountdownSize.normal,
    required this.numberColor,
    required this.labelColor,
  });

  @override
  Widget build(BuildContext context) {
    final double numberSize;
    final double labelSize;
    switch (size) {
      case CountdownSize.compact:
        numberSize = 16;
        labelSize = 10;
      case CountdownSize.normal:
        numberSize = 20;
        labelSize = 11;
      case CountdownSize.large:
        numberSize = 26;
        labelSize = 12;
    }

    if (daysUntil == 0) {
      return Text(
        'Today',
        style: TextStyle(
          fontSize: numberSize * 0.7,
          fontWeight: FontWeight.w500,
          color: numberColor,
        ),
      );
    }

    if (daysUntil < 0) {
      final ago = -daysUntil;
      return Text(
        '$ago day${ago == 1 ? '' : 's'} ago',
        style: TextStyle(
          fontSize: labelSize,
          color: labelColor,
        ),
      );
    }

    return Row(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.baseline,
      textBaseline: TextBaseline.alphabetic,
      children: [
        Text(
          '$daysUntil',
          style: TextStyle(
            fontSize: numberSize,
            fontWeight: FontWeight.w500,
            color: numberColor,
            height: 1.0,
          ),
        ),
        const SizedBox(width: 4),
        Text(
          daysUntil == 1 ? 'day' : 'days',
          style: TextStyle(
            fontSize: labelSize,
            color: labelColor,
          ),
        ),
      ],
    );
  }
}
