import 'package:material_ui/material_ui.dart';

import '../data/catalogue_repository.dart';
import '../data/app_content_repository.dart';
import '../data/catalogue_models.dart';
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
  late final CatalogueRepository _catalogue = CatalogueRepository();
  late final Future<List<ProductCategory>> _categories = _catalogue.getCategories();
  late final Future<ProductPageData> _homepageProducts = _catalogue.getProducts(limit: 100);
  late final Future<Map<String, dynamic>> _appContent = AppContentRepository().loadPublished();
  late final Future<List<Map<String, dynamic>>> _knowledge = AppContentRepository().loadPublishedKnowledge();

  @override
  Widget build(BuildContext context) {
    final pages = [
      HomeScreen(onNavigate: (index) => setState(() => _selectedIndex = index), appContent: _appContent, catalogue: _catalogue, categories: _categories, products: _homepageProducts),
      ProductsScreen(repository: _catalogue),
      RequestsScreen(onNavigate: (index) => setState(() => _selectedIndex = index)),
      SupportScreen(appContent: _appContent, knowledge: _knowledge),
      const AccountScreen(),
    ];
    return Scaffold(
      body: SafeArea(child: IndexedStack(index: _selectedIndex, children: pages)),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _selectedIndex,
        onDestinationSelected: (index) => setState(() => _selectedIndex = index),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.home_outlined), selectedIcon: Icon(Icons.home_rounded), label: 'Home'),
          NavigationDestination(icon: Icon(Icons.grid_view_outlined), selectedIcon: Icon(Icons.grid_view_rounded), label: 'Products'),
          NavigationDestination(icon: Icon(Icons.assignment_outlined), selectedIcon: Icon(Icons.assignment_rounded), label: 'Requests'),
          NavigationDestination(icon: Icon(Icons.headset_mic_outlined), selectedIcon: Icon(Icons.headset_mic_rounded), label: 'Support'),
          NavigationDestination(icon: Icon(Icons.person_outline_rounded), selectedIcon: Icon(Icons.person_rounded), label: 'Account'),
        ],
      ),
    );
  }
}
