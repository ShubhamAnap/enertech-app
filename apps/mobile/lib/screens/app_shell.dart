import 'package:material_ui/material_ui.dart';

import '../data/catalogue_repository.dart';
import '../data/app_content_repository.dart';
import '../data/catalogue_models.dart';
import '../data/product_selection_store.dart';
import 'home_screen.dart';
import 'products_screen.dart';
import 'requests_screen.dart';
import 'support_screen.dart';
import 'account_screen.dart';

class AppShell extends StatefulWidget {
  const AppShell({super.key});

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  int _selectedIndex = 0;
  int _catalogueRefreshVersion = 0;
  String? _selectedCategorySlug;
  final CatalogueRepository _catalogue = CatalogueRepository();
  final ProductSelectionStore _productSelection = ProductSelectionStore();
  late Future<List<ProductCategory>> _categories = _catalogue.getCategories();
  late Future<Map<String, dynamic>> _appContent = AppContentRepository()
      .loadPublished();
  late Future<ProductPageData> _homepageProducts = _loadHomepageProducts();
  late Future<List<Map<String, dynamic>>> _knowledge = AppContentRepository()
      .loadPublishedKnowledge();

  Future<void> _refreshCatalogueAndHome() async {
    final nextCategories = _catalogue.getCategories();
    final nextContent = AppContentRepository().loadPublished();
    final nextKnowledge = AppContentRepository().loadPublishedKnowledge();
    setState(() {
      _categories = nextCategories;
      _appContent = nextContent;
      _knowledge = nextKnowledge;
      _homepageProducts = _loadHomepageProductsFrom(nextContent);
      _catalogueRefreshVersion++;
    });
    try {
      await Future.wait([nextCategories, nextContent, _homepageProducts]);
    } catch (_) {}
  }

  Future<ProductPageData> _loadHomepageProducts() =>
      _loadHomepageProductsFrom(_appContent);

  Future<ProductPageData> _loadHomepageProductsFrom(
    Future<Map<String, dynamic>> contentFuture,
  ) async {
    final content = await contentFuture;
    final home = content['home'];
    final selected = home is Map && home['featured_product_ids'] is List
        ? (home['featured_product_ids'] as List).map((value) => value.toString()).toList(growable: false)
        : const <String>[];
    if (selected.isNotEmpty) return _catalogue.getProductsByIds(selected);
    return _catalogue.getProducts(limit: 300);
  }

  @override
  Widget build(BuildContext context) {
    final pages = [
      HomeScreen(
        onNavigate: (index) => setState(() {
          if (index == 1) _selectedCategorySlug = null;
          _selectedIndex = index;
        }),
        onOpenCategory: (slug) => setState(() {
          _selectedCategorySlug = slug;
          _selectedIndex = 1;
        }),
        onRefresh: _refreshCatalogueAndHome,
        appContent: _appContent,
        catalogue: _catalogue,
        productSelection: _productSelection,
        categories: _categories,
        products: _homepageProducts,
      ),
      ProductsScreen(
        repository: _catalogue,
        selection: _productSelection,
        selectedCategorySlug: _selectedCategorySlug,
        refreshVersion: _catalogueRefreshVersion,
      ),
      RequestsScreen(
        onNavigate: (index) => setState(() => _selectedIndex = index),
      ),
      SupportScreen(
        appContent: _appContent,
        knowledge: _knowledge,
        onNavigate: (index) => setState(() {
          if (index == 1) _selectedCategorySlug = null;
          _selectedIndex = index;
        }),
      ),
      const AccountScreen(),
    ];
    return Scaffold(
      body: SafeArea(
        child: IndexedStack(index: _selectedIndex, children: pages),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _selectedIndex,
        onDestinationSelected: (index) =>
            setState(() => _selectedIndex = index),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.home_outlined),
            selectedIcon: Icon(Icons.home_rounded),
            label: 'Home',
          ),
          NavigationDestination(
            icon: Icon(Icons.grid_view_outlined),
            selectedIcon: Icon(Icons.grid_view_rounded),
            label: 'Products',
          ),
          NavigationDestination(
            icon: Icon(Icons.assignment_outlined),
            selectedIcon: Icon(Icons.assignment_rounded),
            label: 'Requests',
          ),
          NavigationDestination(
            icon: Icon(Icons.headset_mic_outlined),
            selectedIcon: Icon(Icons.headset_mic_rounded),
            label: 'Support',
          ),
          NavigationDestination(
            icon: Icon(Icons.person_outline_rounded),
            selectedIcon: Icon(Icons.person_rounded),
            label: 'Account',
          ),
        ],
      ),
    );
  }
}
