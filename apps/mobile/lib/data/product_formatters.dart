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
  final text = description.trim();
  if (text.isEmpty) return text;
  final sectionHeadings = RegExp(
    r'Product Overview|Key Features|Technical Specifications|Specifications|Applications',
    caseSensitive: false,
  );
  return text.replaceAllMapped(sectionHeadings, (match) {
    final prefix = text.substring(0, match.start);
    final separator = prefix.trim().isEmpty ? '' : '\n\n';
    return '$separator${match.group(0)}\n';
  });
}

