import 'package:material_ui/material_ui.dart';

import '../data/catalogue_models.dart';
import '../data/catalogue_repository.dart';
import '../data/product_formatters.dart';
import '../data/product_selection_store.dart';
import '../theme/app_theme.dart';
import '../widgets/app_components.dart';
import 'solution_finder_screen.dart';

class ProductCompareScreen extends StatefulWidget {
  const ProductCompareScreen({
    super.key,
    required this.repository,
    required this.selection,
  });

  final CatalogueRepository repository;
  final ProductSelectionStore selection;

  @override
  State<ProductCompareScreen> createState() => _ProductCompareScreenState();
}

class _ProductCompareScreenState extends State<ProductCompareScreen> {
  late List<ProductSummary> _selected;
  late Future<List<ProductDetails>> _details;

  @override
  void initState() {
    super.initState();
    _selected = widget.selection.products.value;
    _details = _loadDetails(_selected);
    widget.selection.products.addListener(_selectionChanged);
  }

  @override
  void dispose() {
    widget.selection.products.removeListener(_selectionChanged);
    super.dispose();
  }

  void _selectionChanged() {
    final selected = widget.selection.products.value;
    setState(() {
      _selected = selected;
      _details = _loadDetails(selected);
    });
  }

  Future<List<ProductDetails>> _loadDetails(List<ProductSummary> products) =>
      Future.wait(
        products.map((product) => widget.repository.getProduct(product.slug)),
      );

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Compare products')),
    body: _selected.isEmpty
        ? const Center(
            child: Padding(
              padding: EdgeInsets.all(24),
              child: EmptyState(
                icon: Icons.compare_arrows_rounded,
                title: 'Your comparison is empty',
                message: 'Add products from the catalogue to compare their published details.',
              ),
            ),
          )
        : FutureBuilder<List<ProductDetails>>(
            future: _details,
            builder: (context, snapshot) {
              if (snapshot.hasError) {
                return Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: EmptyState(
                      icon: Icons.wifi_off_rounded,
                      title: 'Product details unavailable',
                      message: 'Reconnect and retry to compare the latest published specifications.',
                      actionLabel: 'Retry',
                      onAction: () =>
                          setState(() => _details = _loadDetails(_selected)),
                    ),
                  ),
                );
              }
              if (!snapshot.hasData) {
                return const Center(child: CircularProgressIndicator());
              }
              return _comparison(snapshot.data!);
            },
          ),
  );

  Widget _comparison(List<ProductDetails> details) {
    final comparisonRows = <_ComparisonRow>[
      _ComparisonRow(
        'Model',
        details.map((product) => product.modelCode ?? 'Not provided').toList(),
      ),
      _ComparisonRow('Price', details.map(_price).toList()),
      _ComparisonRow(
        'Availability',
        details.map((product) => _stock(product.stockStatus)).toList(),
      ),
      _ComparisonRow(
        'Summary',
        details
            .map(
              (product) => product.summary?.trim().isNotEmpty == true
                  ? product.summary!
                  : 'Not provided',
            )
            .toList(),
      ),
      _ComparisonRow(
        'Applications',
        details
            .map(
              (product) => product.applications.isEmpty
                  ? 'Not provided'
                  : product.applications.join(', '),
            )
            .toList(),
      ),
      _ComparisonRow(
        'Key features',
        details
            .map(
              (product) => product.features.isEmpty
                  ? 'Not provided'
                  : product.features.join('\n'),
            )
            .toList(),
      ),
    ];
    final specKeys = <String>{};
    for (final product in details) {
      specKeys.addAll(product.specifications.keys);
    }
    for (final key in specKeys.toList()..sort()) {
      comparisonRows.add(
        _ComparisonRow(
          key,
          details
              .map((product) => _display(product.specifications[key]))
              .toList(),
        ),
      );
    }

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(18, 12, 18, 8),
          child: Row(
            children: [
              const Expanded(
                child: Text(
                  'Swipe sideways to compare all products.',
                  style: TextStyle(color: AppColors.muted, fontSize: 12),
                ),
              ),
              Text(
                '${details.length}/${ProductSelectionStore.maxProducts}',
                style: const TextStyle(
                  color: AppColors.muted,
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
        ),
        Expanded(
          child: SingleChildScrollView(
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: SizedBox(
                width: 150 + details.length * 190,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _row(
                      children: [
                        const SizedBox(
                          width: 150,
                          child: Padding(
                            padding: EdgeInsets.all(10),
                            child: Text(
                              'Product',
                              style: TextStyle(fontWeight: FontWeight.w700),
                            ),
                          ),
                        ),
                        ...details.map(
                          (product) => SizedBox(
                            width: 190,
                            child: Padding(
                              padding: const EdgeInsets.all(8),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    product.name,
                                    maxLines: 3,
                                    overflow: TextOverflow.ellipsis,
                                    style: const TextStyle(
                                      color: AppColors.ink,
                                      fontSize: 13,
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                  TextButton.icon(
                                    onPressed: () =>
                                        widget.selection.remove(product.id),
                                    icon: const Icon(
                                      Icons.remove_circle_outline_rounded,
                                      size: 17,
                                    ),
                                    label: const Text('Remove'),
                                    style: TextButton.styleFrom(
                                      minimumSize: const Size(44, 44),
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 4,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                      ],
                      header: true,
                    ),
                    ...comparisonRows.map(
                      (row) => _row(
                        children: [
                          SizedBox(
                            width: 150,
                            child: Padding(
                              padding: const EdgeInsets.all(10),
                              child: Text(
                                row.label,
                                style: const TextStyle(
                                  color: AppColors.muted,
                                  fontSize: 12,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ),
                          ),
                          ...row.values.map(
                            (value) => SizedBox(
                              width: 190,
                              child: Padding(
                                padding: const EdgeInsets.all(10),
                                child: Text(
                                  value,
                                  style: const TextStyle(
                                    color: AppColors.ink,
                                    fontSize: 12,
                                    height: 1.4,
                                  ),
                                ),
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
        SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(18, 8, 18, 14),
            child: SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => SolutionFinderScreen(
                      initialProducts: _selected
                          .map((product) => product.name)
                          .join(', '),
                    ),
                  ),
                ),
                icon: const Icon(Icons.request_quote_outlined),
                label: const Text('Request a quote for selected products'),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _row({required List<Widget> children, bool header = false}) =>
      Container(
        decoration: BoxDecoration(
          color: header ? const Color(0xFFEAF3FA) : Colors.white,
          border: const Border(bottom: BorderSide(color: AppColors.border)),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: children,
        ),
      );

  String _price(ProductSummary product) {
    if (product.priceMinor == null) return 'Contact for pricing';
    return formatProductPrice(
      priceMinor: product.priceMinor!,
      currencyMinorUnit: product.currencyMinorUnit,
      currencyCode: product.currencyCode,
    );
  }

  String _stock(String status) => switch (status) {
    'instock' => 'In stock',
    'outofstock' => 'Currently unavailable',
    'onbackorder' => 'Available on backorder',
    _ => 'Availability not provided',
  };

  String _display(Object? value) =>
      value == null || value.toString().trim().isEmpty
      ? 'Not provided'
      : value is List
      ? value.join(', ')
      : value.toString();
}

class _ComparisonRow {
  const _ComparisonRow(this.label, this.values);
  final String label;
  final List<String> values;
}
