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
      'Product Overview Useful power. Key Features No-break switching. Specifications Capacity 12.5 kVA.',
    );
    expect(formatted, contains('Product Overview\n'));
    expect(formatted, contains('\n\nKey Features\n'));
    expect(formatted, contains('\n\nSpecifications\n'));
  });
}

