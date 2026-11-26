import 'dart:convert';

import 'package:enertech_customer/data/catalogue_models.dart';
import 'package:enertech_customer/data/catalogue_repository.dart';
import 'package:enertech_customer/data/product_selection_store.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  ProductSummary product(String id) => ProductSummary(
    id: id,
    slug: 'product-$id',
    name: 'Product $id',
    categoryId: 'category-1',
  );

  test('selection is unique and capped at four products', () {
    final selection = ProductSelectionStore();
    expect(selection.add(product('1')), isTrue);
    expect(selection.add(product('1')), isTrue);
    expect(selection.add(product('2')), isTrue);
    expect(selection.add(product('3')), isTrue);
    expect(selection.add(product('4')), isTrue);
    expect(selection.add(product('5')), isFalse);
    expect(selection.products.value.map((item) => item.id), [
      '1',
      '2',
      '3',
      '4',
    ]);

    selection.remove('2');
    expect(selection.add(product('5')), isTrue);
    expect(selection.products.value.map((item) => item.id), [
      '1',
      '3',
      '4',
      '5',
    ]);
  });

  test('clear empties selection', () {
    final selection = ProductSelectionStore()..add(product('1'));
    selection.clear();
    expect(selection.products.value, isEmpty);
  });

  test(
    'offline category filter maps the selected slug to cached category id',
    () async {
      SharedPreferences.setMockInitialValues({
        'enertech_cached_categories_v2': jsonEncode([
          {'id': 'category-1', 'slug': 'inverters', 'name': 'Inverters'},
          {'id': 'category-2', 'slug': 'batteries', 'name': 'Batteries'},
        ]),
        'enertech_cached_products_v2': jsonEncode({
          'total': 2,
          'items': [
            {
              'id': '1',
              'slug': 'solar-inverter',
              'name': 'Solar inverter',
              'category_id': 'category-1',
            },
            {
              'id': '2',
              'slug': 'backup-battery',
              'name': 'Backup battery',
              'category_id': 'category-2',
            },
          ],
        }),
      });

      final page = await CatalogueRepository(baseUrl: '')
          .getProducts(category: 'inverters');
      expect(page.total, 1);
      expect(page.items.single.slug, 'solar-inverter');
    },
  );
}
