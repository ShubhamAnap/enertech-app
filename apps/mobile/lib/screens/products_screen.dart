import 'dart:async';

import 'package:material_ui/material_ui.dart';

import '../data/catalogue_models.dart';
import '../data/catalogue_repository.dart';
import '../data/product_formatters.dart';
import '../data/product_selection_store.dart';
import '../theme/app_theme.dart';
import '../widgets/app_components.dart';
import 'product_detail_screen.dart';
import 'product_compare_screen.dart';

class ProductsScreen extends StatefulWidget {
  const ProductsScreen({
    super.key,
    required this.repository,
    required this.selection,
    this.selectedCategorySlug,
    this.refreshVersion = 0,
  });
  final CatalogueRepository repository;
  final ProductSelectionStore selection;
  final String? selectedCategorySlug;
  final int refreshVersion;

  @override
  State<ProductsScreen> createState() => _ProductsScreenState();
}

class _ProductsScreenState extends State<ProductsScreen> {
  static const _pageSize = 24;
  final _searchController = TextEditingController();
  Timer? _debounce;
  List<ProductCategory> _categories = const [];
  List<ProductSummary> _products = const [];
  String? _selectedCategory;
  String? _error;
  int _total = 0;
  int _offset = 0;
  int _requestGeneration = 0;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _selectedCategory = widget.selectedCategorySlug;
    _load();
  }

  @override
  void didUpdateWidget(covariant ProductsScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.selectedCategorySlug != widget.selectedCategorySlug ||
        oldWidget.refreshVersion != widget.refreshVersion) {
      _selectedCategory = widget.selectedCategorySlug;
      _offset = 0;
      _load();
    }
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _searchController.dispose();
    super.dispose();
  }

  void _searchChanged(String _) {
    _debounce?.cancel();
    _offset = 0;
    _debounce = Timer(const Duration(milliseconds: 300), _load);
  }

  Future<void> _load() async {
    final generation = ++_requestGeneration;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final results = await Future.wait([
        widget.repository.getCategories(),
        widget.repository.getProducts(
          query: _searchController.text,
          category: _selectedCategory,
          limit: _pageSize,
          offset: _offset,
        ),
      ]);
      if (!mounted || generation != _requestGeneration) return;
      setState(() {
        _categories = results[0] as List<ProductCategory>;
        final page = results[1] as ProductPageData;
        _products = page.items;
        _total = page.total;
        _loading = false;
      });
    } on CatalogueException catch (error) {
      if (!mounted || generation != _requestGeneration) return;
      setState(() {
        _error = error.message;
        _loading = false;
      });
    } catch (_) {
      if (!mounted || generation != _requestGeneration) return;
      setState(() {
        _error = 'Catalogue could not load. Please retry.';
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) => RefreshIndicator(
    onRefresh: _load,
    child: CustomScrollView(
      physics: const AlwaysScrollableScrollPhysics(),
      slivers: [
      SliverPadding(
        padding: const EdgeInsets.fromLTRB(20, 20, 20, 0),
        sliver: SliverList.list(
          children: [
            const Text(
              'Products',
              style: TextStyle(
                color: AppColors.ink,
                fontSize: 24,
                fontWeight: FontWeight.w800,
                letterSpacing: -.4,
              ),
            ),
            const SizedBox(height: 5),
            const Text(
              'Explore the published EnerTech catalogue.',
              style: TextStyle(color: AppColors.muted, fontSize: 13),
            ),
            const SizedBox(height: 17),
            ValueListenableBuilder<List<ProductSummary>>(
              valueListenable: widget.selection.products,
              builder: (context, selected, _) => Align(
                alignment: Alignment.centerRight,
                child: OutlinedButton.icon(
                  onPressed: selected.isEmpty
                      ? null
                      : () => Navigator.of(context).push(
                          MaterialPageRoute<void>(
                            builder: (_) => ProductCompareScreen(
                              repository: widget.repository,
                              selection: widget.selection,
                            ),
                          ),
                        ),
                  icon: const Icon(Icons.compare_arrows_rounded),
                  label: Text('Compare / quote list (${selected.length})'),
                ),
              ),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: _searchController,
              onChanged: _searchChanged,
              textInputAction: TextInputAction.search,
              onSubmitted: (_) => _load(),
              decoration: const InputDecoration(
                prefixIcon: Icon(Icons.search_rounded),
                hintText: 'Search products or model',
              ),
            ),
            if (_categories.isNotEmpty) ...[
              const SizedBox(height: 12),
              SizedBox(
                height: 42,
                child: ListView(
                  scrollDirection: Axis.horizontal,
                  children: [
                    Padding(
                      padding: const EdgeInsets.only(right: 7),
                      child: ChoiceChip(
                        label: const Text('All'),
                        selected: _selectedCategory == null,
                        onSelected: (_) {
                          setState(() {
                            _selectedCategory = null;
                            _offset = 0;
                          });
                          _load();
                        },
                      ),
                    ),
                    ..._categories.map(
                      (category) => Padding(
                        padding: const EdgeInsets.only(right: 7),
                        child: ChoiceChip(
                          label: Text(category.name),
                          selected: _selectedCategory == category.slug,
                          onSelected: (_) {
                            setState(() {
                              _selectedCategory = category.slug;
                              _offset = 0;
                            });
                            _load();
                          },
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
            const SizedBox(height: 17),
            if (!_loading && _error == null)
              Text(
                '$_total ${_total == 1 ? 'product' : 'products'}',
                style: const TextStyle(
                  color: AppColors.muted,
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                ),
              ),
            const SizedBox(height: 10),
          ],
        ),
      ),
      if (_loading)
        const SliverFillRemaining(
          hasScrollBody: false,
          child: Center(child: CircularProgressIndicator()),
        )
      else if (_error != null)
        SliverFillRemaining(
          hasScrollBody: false,
          child: Center(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: EmptyState(
                icon: Icons.wifi_off_rounded,
                title: 'Catalogue unavailable',
                message: _error!,
                actionLabel: 'Try again',
                onAction: _load,
              ),
            ),
          ),
        )
      else if (_products.isEmpty)
        SliverFillRemaining(
          hasScrollBody: false,
          child: Center(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: EmptyState(
                icon: Icons.inventory_2_outlined,
                title: _searchController.text.isEmpty
                    ? 'No products published yet'
                    : 'No matching products',
                message: _searchController.text.isEmpty
                    ? 'EnerTech’s verified product catalogue will appear here when published.'
                    : 'Try a different model or describe what you need to the technical team.',
              ),
            ),
          ),
        )
      else
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
          sliver: SliverList.separated(
            itemCount: _products.length,
            separatorBuilder: (_, _) => const SizedBox(height: 10),
            itemBuilder: (context, index) =>
                ValueListenableBuilder<List<ProductSummary>>(
                  valueListenable: widget.selection.products,
                  builder: (context, selected, _) => _ProductCard(
                    product: _products[index],
                    category:
                        _categories
                            .where(
                              (item) => item.id == _products[index].categoryId,
                            )
                            .firstOrNull
                            ?.name ??
                        'Product',
                    selected: widget.selection.contains(_products[index].id),
                    onToggle: () {
                      final product = _products[index];
                      if (widget.selection.contains(product.id)) {
                        widget.selection.remove(product.id);
                      } else if (!widget.selection.add(product)) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text(
                              'Compare up to four products at a time.',
                            ),
                          ),
                        );
                      }
                    },
                    onTap: () {
                      Navigator.of(context).push(
                        MaterialPageRoute<void>(
                          builder: (_) => ProductDetailScreen(
                            categorySlug: _selectedCategory,
                            repository: widget.repository,
                            selection: widget.selection,
                            product: _products[index],
                            category:
                                _categories
                                    .where(
                                      (item) =>
                                          item.id ==
                                          _products[index].categoryId,
                                    )
                                    .firstOrNull
                                    ?.name ??
                                'Product',
                          ),
                        ),
                      );
                    },
                  ),
                ),
          ),
        ),
      if (!_loading && _error == null && _total > _pageSize)
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 2, 20, 24),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Showing ${_offset + 1}–${_offset + _products.length} of $_total',
                  style: const TextStyle(color: AppColors.muted, fontSize: 11),
                ),
                Row(
                  children: [
                    IconButton(
                      tooltip: 'Previous page',
                      onPressed: _offset == 0
                          ? null
                          : () {
                              setState(
                                () => _offset = (_offset - _pageSize).clamp(
                                  0,
                                  _total,
                                ),
                              );
                              _load();
                            },
                      icon: const Icon(Icons.chevron_left_rounded),
                    ),
                    IconButton(
                      tooltip: 'Next page',
                      onPressed: _offset + _pageSize >= _total
                          ? null
                          : () {
                              setState(() => _offset += _pageSize);
                              _load();
                            },
                      icon: const Icon(Icons.chevron_right_rounded),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ],
    ),
  );
}

class _ProductCard extends StatelessWidget {
  const _ProductCard({
    required this.product,
    required this.category,
    required this.onTap,
    required this.selected,
    required this.onToggle,
  });
  final ProductSummary product;
  final String category;
  final VoidCallback onTap;
  final bool selected;
  final VoidCallback onToggle;

  @override
  Widget build(BuildContext context) => Card(
    child: InkWell(
      borderRadius: BorderRadius.circular(16),
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.all(13),
        child: Row(
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: Container(
                width: 70,
                height: 76,
                color: const Color(0xFFF2F6FA),
                child: product.imageUrl == null
                    ? const Icon(
                        Icons.bolt_rounded,
                        color: AppColors.blue,
                        size: 31,
                      )
                    : Image.network(
                        product.imageUrl!,
                        fit: BoxFit.contain,
                        errorBuilder: (_, _, _) => const Icon(
                          Icons.bolt_rounded,
                          color: AppColors.blue,
                          size: 31,
                        ),
                      ),
              ),
            ),
            const SizedBox(width: 13),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    category.toUpperCase(),
                    style: const TextStyle(
                      color: AppColors.muted,
                      fontSize: 9,
                      letterSpacing: .6,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    product.name,
                    maxLines: 3,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: AppColors.ink,
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  if (product.modelCode != null) ...[
                    const SizedBox(height: 3),
                    Text(
                      product.modelCode!,
                      style: const TextStyle(
                        color: AppColors.muted,
                        fontSize: 11,
                      ),
                    ),
                  ],
                  if (product.priceMinor != null) ...[
                    const SizedBox(height: 5),
                    Text(
                      _productPrice(product),
                      style: const TextStyle(
                        color: AppColors.ink,
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                  if (product.stockStatus != 'unknown') ...[
                    const SizedBox(height: 3),
                    Text(
                      _stockLabel(product.stockStatus),
                      style: TextStyle(
                        color: product.stockStatus == 'instock'
                            ? const Color(0xFF2D754A)
                            : AppColors.muted,
                        fontSize: 10,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                  const SizedBox(height: 5),
                  Wrap(
                    spacing: 8,
                    runSpacing: 4,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      const Text(
                        'View product details',
                        style: TextStyle(
                          color: AppColors.blue,
                          fontSize: 11,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      if (product.documents.isNotEmpty ||
                          (product.catalogPdfUrl?.startsWith('https://') ??
                              false))
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 7,
                            vertical: 2,
                          ),
                          decoration: BoxDecoration(
                            color: const Color(0xFFEEF5FC),
                            borderRadius: BorderRadius.circular(999),
                            border: Border.all(
                              color: AppColors.blue.withValues(alpha: .28),
                            ),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const Icon(
                                Icons.picture_as_pdf_rounded,
                                size: 11,
                                color: AppColors.blue,
                              ),
                              const SizedBox(width: 4),
                              Text(
                                product.documents.length > 1
                                    ? '${product.documents.length} PDFs'
                                    : 'Brochure PDF',
                                style: const TextStyle(
                                  color: AppColors.blue,
                                  fontSize: 10,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ],
                          ),
                        ),
                    ],
                  ),
                ],
              ),
            ),
            Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                IconButton(
                  tooltip: selected
                      ? 'Remove from comparison'
                      : 'Add to comparison',
                  onPressed: onToggle,
                  icon: Icon(
                    selected
                        ? Icons.check_circle_rounded
                        : Icons.add_circle_outline_rounded,
                    color: selected ? AppColors.blue : AppColors.muted,
                  ),
                ),
                const Icon(Icons.chevron_right_rounded, color: AppColors.muted),
              ],
            ),
          ],
        ),
      ),
    ),
  );
}

String _productPrice(ProductSummary product) {
  return formatProductPrice(
    priceMinor: product.priceMinor!,
    currencyMinorUnit: product.currencyMinorUnit,
    currencyCode: product.currencyCode,
  );
}

String _stockLabel(String status) => switch (status) {
  'instock' => 'In stock',
  'outofstock' => 'Currently unavailable',
  'onbackorder' => 'Available on backorder',
  _ => '',
};
