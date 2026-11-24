import 'package:enertech_customer/data/catalogue_models.dart';
import 'package:enertech_customer/data/catalogue_repository.dart';
import 'package:enertech_customer/data/product_selection_store.dart';
import 'package:enertech_customer/screens/product_compare_screen.dart';
import 'package:enertech_customer/theme/app_theme.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

class _CatalogueRepository extends CatalogueRepository {
  @override
  Future<ProductDetails> getProduct(String slug) async => ProductDetails(
    id: 'product-1',
    slug: slug,
    name: 'Industrial UPS',
    categoryId: 'category-1',
    modelCode: 'ET-1000',
    specifications: const {'Capacity': '10 kVA'},
  );
}

void main() {
  testWidgets('comparison renders published specifications and removal state', (
    tester,
  ) async {
    final selection = ProductSelectionStore()
      ..add(
        const ProductSummary(
          id: 'product-1',
          slug: 'industrial-ups',
          name: 'Industrial UPS',
          categoryId: 'category-1',
        ),
      );

    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.light,
        home: ProductCompareScreen(
          repository: _CatalogueRepository(),
          selection: selection,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Industrial UPS'), findsOneWidget);
    expect(find.text('ET-1000'), findsOneWidget);
    expect(find.text('10 kVA'), findsOneWidget);
    expect(find.text('Request a quote for selected products'), findsOneWidget);

    await tester.tap(find.text('Remove'));
    await tester.pumpAndSettle();
    expect(find.text('Your comparison is empty'), findsOneWidget);
  });
}
