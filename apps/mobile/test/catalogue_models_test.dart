import 'package:enertech_customer/data/catalogue_models.dart';
import 'package:enertech_customer/data/catalogue_repository.dart';
import 'package:enertech_customer/data/product_selection_store.dart';
import 'package:enertech_customer/screens/products_screen.dart';
import 'package:enertech_customer/theme/app_theme.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

class _FakeProductsRepository extends CatalogueRepository {
  _FakeProductsRepository() : super(baseUrl: '');

  @override
  Future<List<ProductCategory>> getCategories({int limit = 200, int offset = 0}) async =>
      const [ProductCategory(id: 'c1', slug: 'ups', name: 'Industrial UPS')];

  @override
  Future<ProductPageData> getProducts({
    String query = '',
    String? category,
    int limit = 24,
    int offset = 0,
  }) async =>
      const ProductPageData(
        items: [
          ProductSummary(
            id: 'p-with-pdf',
            slug: '100-kva-industrial-ups',
            name: '100 KVA Industrial UPS',
            categoryId: 'c1',
            catalogPdfUrl: 'https://enertechups.com/wp-content/uploads/100kva.pdf',
          ),
          ProductSummary(
            id: 'p-no-pdf',
            slug: '10kva-stabilizer',
            name: '10KVA Stabilizer',
            categoryId: 'c1',
          ),
        ],
        total: 2,
      );
}

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

  testWidgets('ProductsScreen displays Brochure PDF badge only for products with PDF', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.light,
        home: Scaffold(
          body: ProductsScreen(
            repository: _FakeProductsRepository(),
            selection: ProductSelectionStore(),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('100 KVA Industrial UPS'), findsOneWidget);
    expect(find.text('10KVA Stabilizer'), findsOneWidget);
    expect(find.text('Brochure PDF'), findsOneWidget);
  });
}
