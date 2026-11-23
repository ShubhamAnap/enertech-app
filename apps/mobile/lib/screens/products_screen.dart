import 'dart:async';

import 'package:intl/intl.dart';
import 'package:material_ui/material_ui.dart';

import '../data/catalogue_models.dart';
import '../data/catalogue_repository.dart';
import '../theme/app_theme.dart';
import '../widgets/app_components.dart';
import 'product_detail_screen.dart';

class ProductsScreen extends StatefulWidget {
  const ProductsScreen({super.key, required this.repository});
  final CatalogueRepository repository;

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
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
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
    setState(() { _loading = true; _error = null; });
    try {
      final results = await Future.wait([
        widget.repository.getCategories(),
        widget.repository.getProducts(query: _searchController.text, category: _selectedCategory, limit: _pageSize, offset: _offset),
      ]);
      if (!mounted) return;
      setState(() {
        _categories = results[0] as List<ProductCategory>;
        final page = results[1] as ProductPageData;
        _products = page.items;
        _total = page.total;
        _loading = false;
      });
    } on CatalogueException catch (error) {
      if (!mounted) return;
      setState(() { _error = error.message; _loading = false; });
    } catch (_) {
      if (!mounted) return;
      setState(() { _error = 'Catalogue could not load. Please retry.'; _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) => CustomScrollView(slivers: [
    SliverPadding(padding: const EdgeInsets.fromLTRB(20, 20, 20, 0), sliver: SliverList.list(children: [
      const Text('Products', style: TextStyle(color: AppColors.ink, fontSize: 24, fontWeight: FontWeight.w800, letterSpacing: -.4)),
      const SizedBox(height: 5),
      const Text('Explore the published EnerTech catalogue.', style: TextStyle(color: AppColors.muted, fontSize: 13)),
      const SizedBox(height: 17),
      TextField(controller: _searchController, onChanged: _searchChanged, textInputAction: TextInputAction.search, onSubmitted: (_) => _load(), decoration: const InputDecoration(prefixIcon: Icon(Icons.search_rounded), hintText: 'Search products or model')),
      if (_categories.isNotEmpty) ...[
        const SizedBox(height: 12),
        SizedBox(height: 42, child: ListView(scrollDirection: Axis.horizontal, children: [
          Padding(padding: const EdgeInsets.only(right: 7), child: ChoiceChip(label: const Text('All'), selected: _selectedCategory == null, onSelected: (_) { setState(() { _selectedCategory = null; _offset = 0; }); _load(); })),
          ..._categories.map((category) => Padding(padding: const EdgeInsets.only(right: 7), child: ChoiceChip(label: Text(category.name), selected: _selectedCategory == category.slug, onSelected: (_) { setState(() { _selectedCategory = category.slug; _offset = 0; }); _load(); }))),
        ])),
      ],
      const SizedBox(height: 17),
      if (!_loading && _error == null) Text('$_total ${_total == 1 ? 'product' : 'products'}', style: const TextStyle(color: AppColors.muted, fontSize: 12, fontWeight: FontWeight.w600)),
      const SizedBox(height: 10),
    ])),
    if (_loading)
      const SliverFillRemaining(hasScrollBody: false, child: Center(child: CircularProgressIndicator()))
    else if (_error != null)
      SliverFillRemaining(hasScrollBody: false, child: Center(child: Padding(padding: const EdgeInsets.all(20), child: EmptyState(icon: Icons.wifi_off_rounded, title: 'Catalogue unavailable', message: _error!, actionLabel: 'Try again', onAction: _load))))
    else if (_products.isEmpty)
      SliverFillRemaining(hasScrollBody: false, child: Center(child: Padding(padding: const EdgeInsets.all(20), child: EmptyState(icon: Icons.inventory_2_outlined, title: _searchController.text.isEmpty ? 'No products published yet' : 'No matching products', message: _searchController.text.isEmpty ? 'EnerTech’s verified product catalogue will appear here when published.' : 'Try a different model or describe what you need to the technical team.'))))
    else
      SliverPadding(padding: const EdgeInsets.fromLTRB(20, 0, 20, 24), sliver: SliverList.separated(
        itemCount: _products.length,
        separatorBuilder: (_, _) => const SizedBox(height: 10),
        itemBuilder: (context, index) => _ProductCard(product: _products[index], category: _categories.where((item) => item.id == _products[index].categoryId).firstOrNull?.name ?? 'Product', onTap: () {
          Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => ProductDetailScreen(repository: widget.repository, product: _products[index], category: _categories.where((item) => item.id == _products[index].categoryId).firstOrNull?.name ?? 'Product')));
        }),
      )),
    if (!_loading && _error == null && _total > _pageSize)
      SliverToBoxAdapter(child: Padding(padding: const EdgeInsets.fromLTRB(20, 2, 20, 24), child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        Text('Showing ${_offset + 1}–${_offset + _products.length} of $_total', style: const TextStyle(color: AppColors.muted, fontSize: 11)),
        Row(children: [
          IconButton(tooltip: 'Previous page', onPressed: _offset == 0 ? null : () { setState(() => _offset = (_offset - _pageSize).clamp(0, _total)); _load(); }, icon: const Icon(Icons.chevron_left_rounded)),
          IconButton(tooltip: 'Next page', onPressed: _offset + _pageSize >= _total ? null : () { setState(() => _offset += _pageSize); _load(); }, icon: const Icon(Icons.chevron_right_rounded)),
        ]),
      ]))),
  ]);
}

class _ProductCard extends StatelessWidget {
  const _ProductCard({required this.product, required this.category, required this.onTap});
  final ProductSummary product;
  final String category;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Card(child: InkWell(
    borderRadius: BorderRadius.circular(16), onTap: onTap,
    child: Padding(padding: const EdgeInsets.all(13), child: Row(children: [
      ClipRRect(borderRadius: BorderRadius.circular(12), child: Container(width: 70, height: 76, color: const Color(0xFFF2F6FA), child: product.imageUrl == null ? const Icon(Icons.bolt_rounded, color: AppColors.blue, size: 31) : Image.network(product.imageUrl!, fit: BoxFit.contain, errorBuilder: (_, _, _) => const Icon(Icons.bolt_rounded, color: AppColors.blue, size: 31)))),
      const SizedBox(width: 13),
      Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(category.toUpperCase(), style: const TextStyle(color: AppColors.muted, fontSize: 9, letterSpacing: .6, fontWeight: FontWeight.w700)),
        const SizedBox(height: 4),
        Text(product.name, maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(color: AppColors.ink, fontSize: 14, fontWeight: FontWeight.w700)),
        if (product.modelCode != null) ...[const SizedBox(height: 3), Text(product.modelCode!, style: const TextStyle(color: AppColors.muted, fontSize: 11))],
        if (product.priceMinor != null) ...[const SizedBox(height: 5), Text(_productPrice(product), style: const TextStyle(color: AppColors.ink, fontSize: 12, fontWeight: FontWeight.w700))],
        if (product.stockStatus != 'unknown') ...[const SizedBox(height: 3), Text(_stockLabel(product.stockStatus), style: TextStyle(color: product.stockStatus == 'instock' ? const Color(0xFF2D754A) : AppColors.muted, fontSize: 10, fontWeight: FontWeight.w600))],
        const SizedBox(height: 5),
        const Text('View product details', style: TextStyle(color: AppColors.blue, fontSize: 11, fontWeight: FontWeight.w700)),
      ])),
      const Icon(Icons.chevron_right_rounded, color: AppColors.muted),
    ])),
  ));
}

String _productPrice(ProductSummary product) {
  final digits = product.currencyMinorUnit.clamp(0, 4);
  final divisor = int.parse('1${'0' * digits}');
  final symbol = product.currencyCode == 'INR' ? '₹' : '${product.currencyCode} ';
  return NumberFormat.currency(locale: 'en_IN', name: product.currencyCode, symbol: symbol, decimalDigits: digits).format(product.priceMinor! / divisor);
}

String _stockLabel(String status) => switch (status) {
  'instock' => 'In stock',
  'outofstock' => 'Currently unavailable',
  'onbackorder' => 'Available on backorder',
  _ => '',
};
