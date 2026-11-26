import 'package:material_ui/material_ui.dart';

import '../data/catalogue_models.dart';
import '../data/catalogue_repository.dart';
import '../data/product_selection_store.dart';
import '../theme/app_theme.dart';
import '../widgets/app_components.dart';
import 'product_detail_screen.dart';
import 'solution_finder_screen.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({
    super.key,
    required this.onNavigate,
    required this.onOpenCategory,
    required this.appContent,
    required this.catalogue,
    required this.categories,
    required this.products,
    required this.productSelection,
    this.onRefresh,
  });
  final ValueChanged<int> onNavigate;
  final ValueChanged<String> onOpenCategory;
  final Future<void> Function()? onRefresh;
  final Future<Map<String, dynamic>> appContent;
  final CatalogueRepository catalogue;
  final Future<List<ProductCategory>> categories;
  final Future<ProductPageData> products;
  final ProductSelectionStore productSelection;

  void _openSolutionFinder(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => const SolutionFinderScreen()),
    );
  }

  @override
  Widget build(BuildContext context) => RefreshIndicator(
    onRefresh: onRefresh ?? () async {},
    child: CustomScrollView(
      physics: const AlwaysScrollableScrollPhysics(),
      slivers: [
      SliverPadding(
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 28),
        sliver: SliverList.list(
          children: [
            Row(
              children: [
                Image.asset(
                  'assets/brand/enertech_logo.png',
                  width: 116,
                  height: 38,
                  fit: BoxFit.contain,
                  semanticLabel: 'EnerTech logo',
                ),
                const SizedBox(width: 10),
                const Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Welcome to',
                        style: TextStyle(color: AppColors.muted, fontSize: 11),
                      ),
                      SizedBox(height: 2),
                      Text(
                        BrandIdentity.companyName,
                        style: TextStyle(
                          color: AppColors.ink,
                          fontSize: 14,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ],
                  ),
                ),
                IconButton(
                  tooltip: 'Track requests',
                  onPressed: () => onNavigate(2),
                  icon: const Icon(
                    Icons.assignment_outlined,
                    color: AppColors.blue,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 18),
            FutureBuilder<Map<String, dynamic>>(
              future: appContent,
              builder: (context, snapshot) {
                final home = snapshot.data?['home'] is Map
                    ? snapshot.data!['home'] as Map
                    : const <String, dynamic>{};
                final hint =
                    home['search_hint'] is String &&
                        (home['search_hint'] as String).isNotEmpty
                    ? home['search_hint'] as String
                    : 'Search products, models, applications…';
                return Material(
                  color: Theme.of(context).colorScheme.surface,
                  borderRadius: BorderRadius.circular(14),
                  child: InkWell(
                    borderRadius: BorderRadius.circular(14),
                    onTap: () => onNavigate(1),
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 15,
                        vertical: 14,
                      ),
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(14),
                        border: Border.all(
                          color: Theme.of(context).colorScheme.outlineVariant,
                        ),
                      ),
                      child: Row(
                        children: [
                          const Icon(Icons.search_rounded, size: 20),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Text(
                              hint,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: Theme.of(context).textTheme.bodyMedium
                                  ?.copyWith(color: AppColors.muted),
                            ),
                          ),
                          const Icon(Icons.tune_rounded, size: 19),
                        ],
                      ),
                    ),
                  ),
                );
              },
            ),
            const SizedBox(height: 18),
            FutureBuilder<Map<String, dynamic>>(
              future: appContent,
              builder: (context, snapshot) {
                final home = snapshot.data?['home'] is Map
                    ? snapshot.data!['home'] as Map
                    : const <String, dynamic>{};
                final configuredTitle = home['hero_title'] is String
                    ? (home['hero_title'] as String).trim()
                    : '';
                final configuredDescription = home['hero_description'] is String
                    ? (home['hero_description'] as String).trim()
                    : '';
                final title = configuredTitle.isEmpty
                    ? 'Reliable power.\nUninterrupted operations.'
                    : configuredTitle;
                final description = configuredDescription.isEmpty
                    ? 'Find the right solution for your requirement.'
                    : configuredDescription;
                final buttonLabel =
                    home['hero_cta_label'] is String &&
                        (home['hero_cta_label'] as String).isNotEmpty
                    ? home['hero_cta_label'] as String
                    : 'Explore solutions';
                final ctaTarget =
                    home['hero_cta_target'] as String? ?? 'solution_finder';
                return Column(
                  children: [
                    Container(
                      padding: const EdgeInsets.fromLTRB(18, 17, 18, 18),
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(
                          colors: [Color(0xFF173B64), Color(0xFF102C4D)],
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                        ),
                        borderRadius: BorderRadius.circular(20),
                        boxShadow: const [
                          BoxShadow(
                            color: Color(0x1416385F),
                            blurRadius: 18,
                            offset: Offset(0, 8),
                          ),
                        ],
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 9,
                              vertical: 5,
                            ),
                            decoration: BoxDecoration(
                              color: Colors.white.withValues(alpha: .12),
                              borderRadius: BorderRadius.circular(20),
                            ),
                            child: const Text(
                              'POWER SOLUTIONS FOR YOUR BUSINESS',
                              style: TextStyle(
                                color: Color(0xFFCAE4F5),
                                letterSpacing: .45,
                                fontSize: 9,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                          const SizedBox(height: 13),
                          Text(
                            title,
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 21,
                              height: 1.18,
                              fontWeight: FontWeight.w800,
                              letterSpacing: -.4,
                            ),
                          ),
                          const SizedBox(height: 7),
                          Text(
                            description,
                            style: const TextStyle(
                              color: Color(0xFFD3E0EC),
                              fontSize: 12,
                            ),
                          ),
                          const SizedBox(height: 15),
                          SizedBox(
                            width: double.infinity,
                            child: FilledButton.tonalIcon(
                              style: FilledButton.styleFrom(
                                backgroundColor: Colors.white,
                                foregroundColor: AppColors.navy,
                                alignment: Alignment.centerLeft,
                              ),
                              onPressed: () => ctaTarget == 'products'
                                  ? onNavigate(1)
                                  : ctaTarget == 'support'
                                  ? onNavigate(3)
                                  : _openSolutionFinder(context),
                              icon: const Icon(
                                Icons.arrow_forward_rounded,
                                size: 17,
                              ),
                              label: Text(buttonLabel),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                );
              },
            ),
            const SizedBox(height: 24),
            FutureBuilder<Map<String, dynamic>>(
              future: appContent,
              builder: (context, snapshot) {
                final home = snapshot.data?['home'] is Map
                    ? snapshot.data!['home'] as Map
                    : const <String, dynamic>{};
                String text(String field, String fallback) =>
                    home[field] is String && (home[field] as String).isNotEmpty
                    ? home[field] as String
                    : fallback;
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    SectionTitle(
                      title: text(
                        'intent_section_title',
                        'What are you looking for?',
                      ),
                    ),
                    const SizedBox(height: 8),
                    GridView.count(
                      crossAxisCount: 2,
                      crossAxisSpacing: 10,
                      mainAxisSpacing: 10,
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      childAspectRatio: 1.72,
                      children: [
                        IntentCard(
                          icon: Icons.grid_view_rounded,
                          title: text(
                            'products_card_title',
                            'Explore products',
                          ),
                          subtitle: text(
                            'products_card_subtitle',
                            'Browse the catalogue',
                          ),
                          onTap: () => onNavigate(1),
                        ),
                        IntentCard(
                          icon: Icons.bolt_rounded,
                          title: text('solution_card_title', 'Find a solution'),
                          subtitle: text(
                            'solution_card_subtitle',
                            'Guided requirement',
                          ),
                          onTap: () => _openSolutionFinder(context),
                        ),
                        IntentCard(
                          icon: Icons.request_quote_outlined,
                          title: text('quote_card_title', 'Request a quote'),
                          subtitle: text(
                            'quote_card_subtitle',
                            'Tell us what you need',
                          ),
                          onTap: () => _openSolutionFinder(context),
                        ),
                        IntentCard(
                          icon: Icons.support_agent_rounded,
                          title: text(
                            'support_card_title',
                            'Service & support',
                          ),
                          subtitle: text(
                            'support_card_subtitle',
                            'Get help with equipment',
                          ),
                          onTap: () => onNavigate(3),
                        ),
                      ],
                    ),
                  ],
                );
              },
            ),
            const SizedBox(height: 23),
            FutureBuilder<Map<String, dynamic>>(
              future: appContent,
              builder: (context, snapshot) {
                final home = snapshot.data?['home'] is Map
                    ? snapshot.data!['home'] as Map
                    : const <String, dynamic>{};
                return _cmsSections(context, home);
              },
            ),
          ],
        ),
      ),
    ],
    ),
  );

  Widget _cmsSections(BuildContext context, Map<dynamic, dynamic> home) {
    final defaults = [
      'categories',
      'featured_products',
      'requests',
      'announcements',
    ];
    final visibleRaw = home['visible_sections'];
    final visible = visibleRaw is List
        ? visibleRaw.map((item) => item.toString()).toSet()
        : defaults.toSet();
    final orderRaw = home['section_order'];
    final order = orderRaw is List
        ? orderRaw.map((item) => item.toString()).toList()
        : [...defaults, 'announcements'];
    final sectionWidgets = <Widget>[];
    for (final key in order) {
      if (!visible.contains(key)) continue;
      switch (key) {
        case 'categories':
          sectionWidgets.add(_featuredCategories(context, home));
          break;
        case 'featured_products':
          sectionWidgets.add(_featuredProducts(context, home));
          break;
        case 'requests':
          sectionWidgets.add(_requestsShortcut(context));
          break;
        case 'announcements':
          if (home['announcement_visible'] == true &&
              ((home['announcement_title'] as String?)?.isNotEmpty ?? false)) {
            sectionWidgets.add(
              Padding(
                padding: const EdgeInsets.only(top: 14),
                child: NoticeCard(
                  message:
                      '${home['announcement_title']} ${home['announcement_body'] ?? ''}',
                ),
              ),
            );
          }
          break;
      }
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: sectionWidgets,
    );
  }

  Widget _featuredCategories(
    BuildContext context,
    Map<dynamic, dynamic> home,
  ) => FutureBuilder<List<ProductCategory>>(
    future: categories,
    builder: (context, snapshot) {
      final idsRaw = home['featured_category_ids'];
      final ids = idsRaw is List
          ? idsRaw.map((item) => item.toString()).toSet()
          : <String>{};
      final values = (snapshot.data ?? const <ProductCategory>[])
          .where((category) => ids.isEmpty || ids.contains(category.id))
          .take(8)
          .toList();
      return Padding(
        padding: const EdgeInsets.only(top: 22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SectionTitle(
              title: 'Explore by category',
              actionLabel: 'View all',
              onAction: () => onNavigate(1),
            ),
            const SizedBox(height: 9),
            if (snapshot.connectionState == ConnectionState.waiting)
              const LinearProgressIndicator(minHeight: 2)
            else if (values.isEmpty)
              const NoticeCard(
                message: 'Published product categories will appear here.',
              ),
            if (values.isNotEmpty)
              SizedBox(
                height: 104,
                child: ListView(
                  scrollDirection: Axis.horizontal,
                  children: values.map<Widget>((category) {
                    final image = category.imageUrl == null
                        ? const Icon(
                            Icons.grid_view_rounded,
                            color: AppColors.blue,
                          )
                        : Image.network(
                            category.imageUrl!,
                            fit: BoxFit.contain,
                            errorBuilder: (_, _, _) => const Icon(
                              Icons.grid_view_rounded,
                              color: AppColors.blue,
                            ),
                          );
                    return SizedBox(
                      width: 150,
                      child: Card(
                        child: InkWell(
                          onTap: () => onOpenCategory(category.slug),
                          borderRadius: BorderRadius.circular(15),
                          child: Padding(
                            padding: const EdgeInsets.all(11),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Expanded(child: Center(child: image)),
                                const SizedBox(height: 7),
                                Text(
                                  category.name,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: const TextStyle(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    );
                  }).toList(),
                ),
              ),
          ],
        ),
      );
    },
  );

  Widget _featuredProducts(BuildContext context, Map<dynamic, dynamic> home) =>
      FutureBuilder<List<dynamic>>(
        future: Future.wait([products, categories]),
        builder: (context, snapshot) {
          final pageData = snapshot.data != null ? snapshot.data![0] as ProductPageData : null;
          final catList = snapshot.data != null ? snapshot.data![1] as List<ProductCategory> : const <ProductCategory>[];
          final catById = {for (final cat in catList) cat.id: cat.name};
          final idsRaw = home['featured_product_ids'];
          final ids = idsRaw is List
              ? idsRaw.map((item) => item.toString()).toSet()
              : <String>{};
          final values = (pageData?.items ?? const <ProductSummary>[])
              .where((product) => ids.isEmpty || ids.contains(product.id))
              .take(6)
              .toList();
          return Padding(
            padding: const EdgeInsets.only(top: 22),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SectionTitle(
                  title: 'Featured products',
                  actionLabel: 'View all',
                  onAction: () => onNavigate(1),
                ),
                const SizedBox(height: 9),
                if (snapshot.connectionState == ConnectionState.waiting)
                  const LinearProgressIndicator(minHeight: 2)
                else if (values.isEmpty)
                  const NoticeCard(
                    message: 'Featured products will appear here when products are published and selected in the CMS.',
                  ),
                for (final product in values)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Card(
                      child: ListTile(
                        leading: product.imageUrl == null
                            ? const Icon(
                                Icons.bolt_rounded,
                                color: AppColors.blue,
                              )
                            : Image.network(
                                product.imageUrl!,
                                width: 46,
                                height: 46,
                                fit: BoxFit.contain,
                                errorBuilder: (_, _, _) => const Icon(
                                  Icons.bolt_rounded,
                                  color: AppColors.blue,
                                ),
                              ),
                        title: Text(
                          product.name,
                          style: const TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        subtitle: Text(
                          product.summary ??
                              product.modelCode ??
                              catById[product.categoryId] ??
                              'Published product',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontSize: 11),
                        ),
                        trailing: const Icon(Icons.chevron_right_rounded),
                        onTap: () => Navigator.of(context).push(
                          MaterialPageRoute<void>(
                            builder: (_) => ProductDetailScreen(
                              repository: catalogue,
                              selection: productSelection,
                              product: product,
                              category: catById[product.categoryId] ?? 'Product',
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          );
        },
      );

  Widget _requestsShortcut(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: 22),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SectionTitle(
          title: 'Your requests',
          actionLabel: 'View all',
          onAction: () => onNavigate(2),
        ),
        const SizedBox(height: 8),
        Card(
          child: InkWell(
            onTap: () => onNavigate(2),
            borderRadius: BorderRadius.circular(15),
            child: const Padding(
              padding: EdgeInsets.symmetric(horizontal: 15, vertical: 14),
              child: Row(
                children: [
                  Icon(
                    Icons.assignment_outlined,
                    color: AppColors.blue,
                    size: 23,
                  ),
                  SizedBox(width: 11),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Track enquiries and service',
                          style: TextStyle(
                            color: AppColors.ink,
                            fontSize: 12,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        SizedBox(height: 3),
                        Text(
                          'View request status and updates.',
                          style: TextStyle(
                            color: AppColors.muted,
                            fontSize: 11,
                          ),
                        ),
                      ],
                    ),
                  ),
                  Icon(Icons.chevron_right_rounded, color: AppColors.muted),
                ],
              ),
            ),
          ),
        ),
      ],
    ),
  );
}
