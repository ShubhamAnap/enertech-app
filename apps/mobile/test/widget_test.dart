import 'package:enertech_customer/app.dart';
import 'package:enertech_customer/data/catalogue_models.dart';
import 'package:enertech_customer/data/catalogue_repository.dart';
import 'package:enertech_customer/data/product_selection_store.dart';
import 'package:enertech_customer/screens/home_screen.dart';
import 'package:enertech_customer/theme/app_theme.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

void main() {
  testWidgets(
    'Startup blocks customer sign-in until app configuration exists',
    (tester) async {
      await tester.pumpWidget(const EnerTechApp());
      expect(find.text('App setup is incomplete'), findsOneWidget);
      expect(
        find.textContaining('Firebase and the HTTPS API endpoint'),
        findsOneWidget,
      );
      expect(find.text('Sign in'), findsNothing);
    },
  );

  testWidgets('Home renders CMS copy and routes search to products', (
    tester,
  ) async {
    int? selectedTab;
    final home = HomeScreen(
      onNavigate: (index) => selectedTab = index,
      onOpenCategory: (_) {},
      appContent: Future.value({
        'brand': {'display_name': 'EnerTech'},
        'home': {
          'search_hint': 'Find an inverter',
          'hero_title': 'Power built for uptime',
          'hero_description': 'CMS description',
          'hero_cta_label': 'Browse units',
          'intent_section_title': 'Select a service',
          'products_card_title': 'All units',
          'products_card_subtitle': 'Updated range',
          'visible_sections': <String>[],
          'section_order': <String>[],
        },
      }),
      catalogue: CatalogueRepository(baseUrl: ''),
      productSelection: ProductSelectionStore(),
      categories: Future.value(const <ProductCategory>[]),
      products: Future.value(const ProductPageData(items: [], total: 0)),
    );

    await tester.pumpWidget(MaterialApp(theme: AppTheme.light, home: home));
    await tester.pumpAndSettle();
    expect(find.text('Power built for uptime'), findsOneWidget);
    expect(find.text('Select a service'), findsOneWidget);
    expect(find.text('All units'), findsOneWidget);
    await tester.tap(find.text('Find an inverter'));
    expect(selectedTab, 1);
  });
}
