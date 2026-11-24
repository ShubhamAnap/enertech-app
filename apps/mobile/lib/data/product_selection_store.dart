import 'package:flutter/foundation.dart';

import 'catalogue_models.dart';

/// Keeps a short-lived product comparison/quote list for the current app run.
/// Only public catalogue summaries are held; no customer data is persisted.
class ProductSelectionStore {
  static const int maxProducts = 4;

  final ValueNotifier<List<ProductSummary>> products =
      ValueNotifier<List<ProductSummary>>(const []);

  bool contains(String productId) =>
      products.value.any((product) => product.id == productId);

  /// Returns false when adding would exceed the comparison limit.
  bool add(ProductSummary product) {
    if (contains(product.id)) return true;
    if (products.value.length >= maxProducts) return false;
    products.value = List.unmodifiable([...products.value, product]);
    return true;
  }

  void remove(String productId) {
    products.value = List.unmodifiable(
      products.value.where((product) => product.id != productId),
    );
  }

  void clear() => products.value = const [];
}
