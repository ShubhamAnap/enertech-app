import 'package:enertech_customer/data/product_formatters.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('whole currency amounts do not show unnecessary decimal zeros', () {
    expect(
      formatProductPrice(
        priceMinor: 21437700,
        currencyMinorUnit: 2,
        currencyCode: 'INR',
      ),
      '₹2,14,377',
    );
  });

  test('fractional currency amounts retain their configured precision', () {
    expect(
      formatProductPrice(
        priceMinor: 5672550,
        currencyMinorUnit: 2,
        currencyCode: 'INR',
      ),
      '₹56,725.50',
    );
  });

  test('flattened WooCommerce section labels get separate lines', () {
    final formatted = formatProductDescription(
      'Product Overview Useful power. Key Features No-break switching; Low internal resistance. Specifications Capacity 12.5 kVA Nominal Battery Voltage 120 V DC Phase Single Phase.',
    );
    expect(formatted, contains('Product Overview\n'));
    expect(formatted, contains('\n\nKey Features\n'));
    expect(formatted, contains('\n\nSpecifications\n'));
    expect(formatted, contains('• No-break switching'));
    expect(formatted, contains('• Low internal resistance.'));
    expect(formatted, contains('Capacity: 12.5 kVA'));
    expect(formatted, contains('Nominal Battery Voltage: 120 V'));
    expect(formatted, contains('DC Phase: Single Phase.'));
  });

  test('HTML catalogue copy becomes readable headings and bullets', () {
    final formatted = formatProductDescription(
      '<h3>Product Overview</h3><p>Reliable power.</p><h3>Key Features</h3><ul><li>No-break output</li><li>High efficiency</li></ul>',
    );
    expect(formatted, contains('Product Overview\nReliable power.'));
    expect(formatted, contains('• No-break output'));
    expect(formatted, contains('• High efficiency'));
  });
}
