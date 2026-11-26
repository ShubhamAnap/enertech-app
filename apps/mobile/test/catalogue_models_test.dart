import 'package:enertech_customer/data/catalogue_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('product summaries retain every catalogue category', () {
    final product = ProductSummary.fromJson({
      'id': 'product-id',
      'slug': 'multi-category-product',
      'name': 'Multi category product',
      'category_id': 'primary-id',
      'category_ids': ['primary-id', 'secondary-id'],
    });

    expect(product.categoryId, 'primary-id');
    expect(product.categoryIds, ['primary-id', 'secondary-id']);
  });

  test('older cached product data falls back to the primary category', () {
    final product = ProductSummary.fromJson({
      'id': 'product-id',
      'slug': 'legacy-product',
      'name': 'Legacy product',
      'category_id': 'primary-id',
    });

    expect(product.categoryIds, ['primary-id']);
  });

  test('products inherit catalog_pdf_url when documents list is omitted or empty', () {
    final summary = ProductSummary.fromJson({
      'id': 'p1',
      'slug': 'batteryless-gridless-solar-hybrid-inverter',
      'name': 'Batteryless Gridless Solar Hybrid Inverter',
      'category_id': 'c1',
      'documents': const <Map<String, dynamic>>[],
      'catalog_pdf_url': 'https://enertechups.com/wp-content/uploads/batteryless-family.pdf',
    });

    expect(summary.catalogPdfUrl, 'https://enertechups.com/wp-content/uploads/batteryless-family.pdf');
    expect(summary.documents.single.url, 'https://enertechups.com/wp-content/uploads/batteryless-family.pdf');
  });
}
