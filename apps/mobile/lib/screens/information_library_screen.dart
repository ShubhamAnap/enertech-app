import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';

import '../data/catalogue_models.dart';
import '../data/catalogue_repository.dart';
import '../theme/app_theme.dart';
import '../widgets/app_components.dart';

class InformationLibraryScreen extends StatefulWidget {
  const InformationLibraryScreen({
    super.key,
    required this.title,
    required this.icon,
  });
  final String title;
  final IconData icon;

  @override
  State<InformationLibraryScreen> createState() =>
      _InformationLibraryScreenState();
}

class _InformationLibraryScreenState extends State<InformationLibraryScreen> {
  final _query = TextEditingController();
  late Future<List<_LibraryDocument>> _documents;

  @override
  void initState() {
    super.initState();
    _documents = _loadDocuments();
  }

  @override
  void dispose() {
    _query.dispose();
    super.dispose();
  }

  Future<List<_LibraryDocument>> _loadDocuments() async {
    final repository = CatalogueRepository();
    final products = <ProductSummary>[];
    var offset = 0;
    var total = 0;
    do {
      final page = await repository.getProducts(limit: 500, offset: offset);
      products.addAll(page.items);
      total = page.total;
      offset += page.items.length;
      if (page.items.isEmpty) break;
    } while (offset < total);

    final warrantyOnly = widget.title.toLowerCase().contains('warranty');
    final requiredTitleTerms = RegExp(
      r'warranty|amc|guarantee|coverage',
      caseSensitive: false,
    );
    return [
      for (final product in products)
        for (final document in product.documents)
          if (document.url.startsWith('https://') &&
              (!warrantyOnly || requiredTitleTerms.hasMatch(document.title)))
            _LibraryDocument(product: product, document: document),
    ];
  }

  Future<void> _openDocument(_LibraryDocument entry) async {
    final uri = Uri.tryParse(entry.document.url);
    if (uri == null ||
        uri.scheme != 'https' ||
        !await launchUrl(uri, mode: LaunchMode.externalApplication)) {
      if (mounted)
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('This document could not be opened.')),
        );
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text(widget.title)),
    body: SafeArea(
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 12),
            child: TextField(
              controller: _query,
              onChanged: (_) => setState(() {}),
              decoration: InputDecoration(
                prefixIcon: const Icon(Icons.search_rounded),
                labelText: 'Search ${widget.title.toLowerCase()}',
                suffixIcon: _query.text.isEmpty
                    ? null
                    : IconButton(
                        onPressed: () {
                          _query.clear();
                          setState(() {});
                        },
                        icon: const Icon(Icons.clear_rounded),
                        tooltip: 'Clear search',
                      ),
              ),
            ),
          ),
          Expanded(
            child: FutureBuilder<List<_LibraryDocument>>(
              future: _documents,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done)
                  return const Center(child: CircularProgressIndicator());
                if (snapshot.hasError)
                  return const Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: NoticeCard(
                        message: 'Published documents could not be loaded. Check your connection and try again.',
                        icon: Icons.error_outline_rounded,
                      ),
                    ),
                  );
                final search = _query.text.trim().toLowerCase();
                final rows = (snapshot.data ?? const <_LibraryDocument>[])
                    .where(
                      (entry) =>
                          search.isEmpty ||
                          entry.product.name.toLowerCase().contains(search) ||
                          (entry.product.modelCode?.toLowerCase().contains(
                                search,
                              ) ??
                              false) ||
                          entry.document.title.toLowerCase().contains(search),
                    )
                    .toList(growable: false);
                if (rows.isEmpty) {
                  final message =
                      widget.title.toLowerCase().contains('warranty')
                      ? 'No published warranty or AMC documents are available. Coverage status is not inferred from product manuals.'
                      : 'Published product manuals and documents will appear here when available.';
                  return ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.all(20),
                    children: [
                      Card(
                        child: EmptyState(
                          icon: widget.icon,
                          title: 'No matching documents',
                          message: message,
                        ),
                      ),
                    ],
                  );
                }
                return RefreshIndicator(
                  onRefresh: () async {
                    final next = _loadDocuments();
                    setState(() => _documents = next);
                    await next;
                  },
                  child: ListView.separated(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.fromLTRB(20, 4, 20, 24),
                    itemCount: rows.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 8),
                    itemBuilder: (context, index) {
                      final entry = rows[index];
                      return Card(
                        child: ListTile(
                          onTap: () => _openDocument(entry),
                          leading: Container(
                            width: 40,
                            height: 40,
                            decoration: BoxDecoration(
                              color: const Color(0xFFEAF3FA),
                              borderRadius: BorderRadius.circular(11),
                            ),
                            child: Icon(
                              widget.icon,
                              color: AppColors.blue,
                              size: 20,
                            ),
                          ),
                          title: Text(
                            entry.document.title,
                            style: const TextStyle(
                              fontWeight: FontWeight.w700,
                              fontSize: 13,
                            ),
                          ),
                          subtitle: Text(
                            '${entry.product.name}${entry.product.modelCode == null ? '' : ' · ${entry.product.modelCode}'}',
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontSize: 11),
                          ),
                          trailing: const Icon(
                            Icons.open_in_new_rounded,
                            size: 18,
                          ),
                        ),
                      );
                    },
                  ),
                );
              },
            ),
          ),
        ],
      ),
    ),
  );
}

class _LibraryDocument {
  const _LibraryDocument({required this.product, required this.document});
  final ProductSummary product;
  final ProductDocument document;
}
