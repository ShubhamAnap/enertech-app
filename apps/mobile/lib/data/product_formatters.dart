import 'package:intl/intl.dart';

String formatProductPrice({
  required int priceMinor,
  required int currencyMinorUnit,
  required String currencyCode,
}) {
  final minorDigits = currencyMinorUnit.clamp(0, 4);
  final divisor = int.parse('1${'0' * minorDigits}');
  final amount = priceMinor / divisor;
  final symbol = currencyCode == 'INR' ? '₹' : '$currencyCode ';
  final displayDigits = amount == amount.roundToDouble() ? 0 : minorDigits;
  return NumberFormat.currency(
    locale: 'en_IN',
    name: currencyCode,
    symbol: symbol,
    decimalDigits: displayDigits,
  ).format(amount);
}

String formatProductDescription(String description) {
  final text = _plainText(description).trim();
  if (text.isEmpty) return text;
  const headings = <String>[
    'Product Overview',
    'Key Features',
    'Technical Specifications',
    'Specifications',
    'Applications',
  ];
  final headingPattern = RegExp(
    '\\b(?:${headings.map(RegExp.escape).join('|')})\\b',
    caseSensitive: false,
  );
  final matches = headingPattern.allMatches(text).toList(growable: false);
  if (matches.isEmpty) return _normalizeParagraph(text);

  final sections = <String>[];
  final prefix = text.substring(0, matches.first.start).trim();
  if (prefix.isNotEmpty) sections.add(_normalizeParagraph(prefix));

  for (var index = 0; index < matches.length; index++) {
    final match = matches[index];
    final end = index + 1 < matches.length
        ? matches[index + 1].start
        : text.length;
    final heading = headings.firstWhere(
      (candidate) => candidate.toLowerCase() == match.group(0)!.toLowerCase(),
    );
    final body = text.substring(match.end, end).trim();
    sections.add('$heading\n${_formatSectionBody(heading, body)}'.trimRight());
  }
  return sections.where((section) => section.trim().isNotEmpty).join('\n\n');
}

String _plainText(String value) => value
    .replaceAll(RegExp(r'<\s*br\s*/?\s*>', caseSensitive: false), '\n')
    .replaceAll(RegExp(r'<\s*li\b[^>]*>', caseSensitive: false), '\n• ')
    .replaceAll(
      RegExp(r'</\s*(?:p|div|li|h[1-6]|tr)\s*>', caseSensitive: false),
      '\n',
    )
    .replaceAll(RegExp(r'<\s*td\b[^>]*>', caseSensitive: false), '  ')
    .replaceAll(RegExp(r'<[^>]+>'), '')
    .replaceAll('&nbsp;', ' ')
    .replaceAll('&#8211;', '–')
    .replaceAll('&#8217;', '’')
    .replaceAll('&amp;', '&')
    .replaceAll('&lt;', '<')
    .replaceAll('&gt;', '>');

String _formatSectionBody(String heading, String value) {
  var body = value
      .replaceAll(RegExp(r'[\t\r]+'), ' ')
      .replaceAll(RegExp(r'\s*;\s*'), '\n')
      .replaceAll(RegExp(r'\s*[•·]\s*'), '\n• ')
      .replaceAll(RegExp(r'\n{2,}'), '\n');

  if (heading == 'Specifications' || heading == 'Technical Specifications') {
    const labels = <String>[
      'Rated Capacity',
      'Nominal Battery Voltage',
      'Nominal Cell Voltage',
      'Battery Voltage',
      'Float Voltage',
      'Charge Voltage',
      'Chemistry',
      'Capacity',
      'DC Phase',
      'Phase',
      'Model',
      'DG Compatibility',
      'Double Rating Of Inverter Capacity',
      'Switching Time',
      'Change Over Time',
      'Design',
      'Monitoring',
      'Battery Compatibility',
      'Reverse Polarity For Panel and Battery',
      'Reverse Polarity',
      'Anti-Islanding Prevention of Grid Isolation',
      'Anti-Islanding',
      'Power Factor',
      'Mode',
      'Applications',
    ];
    final orderedLabels = labels.toList()
      ..remove('Phase')
      ..sort((left, right) => right.length.compareTo(left.length));
    body = _separateSpecificationLabels(body, orderedLabels);
  } else if (heading == 'Key Features') {
    const featureStarts = <String>[
      'No-break changeover',
      'No-break switching',
      'Contactor- and relay-less design',
      'Contactor and relay-less design',
      'DG compatible',
      'Saving, backup, export',
      'Lead acid / VRLA',
      'Lead-acid design',
      'Maintenance-free',
      'Spill-proof',
      'Low self-discharge',
      'Design life',
      'Low internal resistance',
    ];
    final featureAlternation = featureStarts.map(RegExp.escape).join('|');
    body = body.replaceAll(
      RegExp('\\s+(?=(?:$featureAlternation)\\b)', caseSensitive: false),
      '\n',
    );
    body = body
        .replaceAll(RegExp(r'(?<=[.!?])\s+(?=[A-Z0-9])'), '\n')
        .split('\n')
        .map((line) {
          final clean = line.trim().replaceFirst(RegExp(r'^[•·-]\s*'), '');
          return clean.isEmpty ? '' : '• $clean';
        })
        .where((line) => line.isNotEmpty)
        .join('\n');
  } else {
    body = _normalizeParagraph(body);
  }
  return body;
}

String _normalizeParagraph(String value) => value
    .split('\n')
    .map((line) => line.trim().replaceAll(RegExp(r'\s{2,}'), ' '))
    .where((line) => line.isNotEmpty)
    .join('\n');

String _separateSpecificationLabels(String value, List<String> labels) {
  final source = value.trim();
  final output = StringBuffer();
  var index = 0;
  while (index < source.length) {
    final atWhitespace = index == 0 || RegExp(r'\s').hasMatch(source[index]);
    if (atWhitespace) {
      var labelStart = index;
      while (labelStart < source.length &&
          RegExp(r'\s').hasMatch(source[labelStart])) {
        labelStart++;
      }
      final label = labels.cast<String?>().firstWhere(
        (candidate) =>
            candidate != null &&
            source.toLowerCase().startsWith(
              candidate.toLowerCase(),
              labelStart,
            ) &&
            (labelStart + candidate.length == source.length ||
                RegExp(r'[\s:]')
                    .hasMatch(source[labelStart + candidate.length])),
        orElse: () => null,
      );
      if (label != null) {
        if (output.isNotEmpty) output.write('\n');
        output.write('$label: ');
        index = labelStart + label.length;
        while (index < source.length && RegExp(r'\s').hasMatch(source[index])) {
          index++;
        }
        continue;
      }
      if (index > 0 && output.isNotEmpty && !output.toString().endsWith(' ')) {
        output.write(' ');
      }
      index = labelStart;
      continue;
    }
    output.write(source[index]);
    index++;
  }
  return output.toString().trim();
}
