import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';

import '../data/catalogue_models.dart';
import '../data/catalogue_repository.dart';
import '../data/product_formatters.dart';
import '../data/product_selection_store.dart';
import '../theme/app_theme.dart';
import '../widgets/app_components.dart';
import 'solution_finder_screen.dart';

class ProductDetailScreen extends StatefulWidget {
  const ProductDetailScreen({
    super.key,
    required this.repository,
    required this.selection,
    required this.product,
    required this.category,
    this.categorySlug,
  });
  final CatalogueRepository repository;
  final ProductSelectionStore selection;
  final ProductSummary product;
  final String category;
  final String? categorySlug;

  @override
  State<ProductDetailScreen> createState() => _ProductDetailScreenState();
}

class _ProductDetailScreenState extends State<ProductDetailScreen> {
  late Future<ProductDetails> _detail = widget.repository.getProduct(
    widget.product.slug, category: widget.categorySlug,
  );

  void _retryDetails() {
    setState(() {
      _detail = widget.repository.getProduct(widget.product.slug, category: widget.categorySlug);
    });
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(
        widget.product.name,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
      ),
      leading: const BackButton(),
    ),
    body: FutureBuilder<ProductDetails>(
      future: _detail,
      builder: (context, snapshot) {
        final product = snapshot.data;
        final image = product?.imageUrl ?? widget.product.imageUrl;
        final gallery = product?.galleryImages ?? const <String>[];
        return ListView(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 28),
          children: [
            Container(
              height: 230,
              decoration: BoxDecoration(
                color: Colors.white,
                border: Border.all(color: AppColors.border),
                borderRadius: BorderRadius.circular(20),
              ),
              clipBehavior: Clip.antiAlias,
              child: image == null
                  ? Container(
                      color: const Color(0xFFF4F7FB),
                      child: Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Container(
                              width: 72,
                              height: 72,
                              decoration: BoxDecoration(
                                color: AppColors.blue.withValues(alpha: 0.1),
                                borderRadius: BorderRadius.circular(20),
                              ),
                              child: const Icon(
                                Icons.bolt_rounded,
                                color: AppColors.blue,
                                size: 44,
                              ),
                            ),
                            const SizedBox(height: 10),
                            const Text(
                              'EnerTech Power Solution',
                              style: TextStyle(
                                color: AppColors.ink,
                                fontWeight: FontWeight.w700,
                                fontSize: 13,
                              ),
                            ),
                            const SizedBox(height: 2),
                            const Text(
                              'Certified Industrial Equipment',
                              style: TextStyle(
                                color: AppColors.muted,
                                fontSize: 11,
                              ),
                            ),
                          ],
                        ),
                      ),
                    )
                  : Image.network(
                      image,
                      fit: BoxFit.contain,
                      errorBuilder: (_, _, _) => Container(
                        color: const Color(0xFFF4F7FB),
                        child: Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Container(
                                width: 72,
                                height: 72,
                                decoration: BoxDecoration(
                                  color: AppColors.blue.withValues(alpha: 0.1),
                                  borderRadius: BorderRadius.circular(20),
                                ),
                                child: const Icon(
                                  Icons.bolt_rounded,
                                  color: AppColors.blue,
                                  size: 44,
                                ),
                              ),
                              const SizedBox(height: 10),
                              const Text(
                                'EnerTech Power Solution',
                                style: TextStyle(
                                  color: AppColors.ink,
                                  fontWeight: FontWeight.w700,
                                  fontSize: 13,
                                ),
                              ),
                              const SizedBox(height: 2),
                              const Text(
                                'Certified Industrial Equipment',
                                style: TextStyle(
                                  color: AppColors.muted,
                                  fontSize: 11,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
            ),
            if (gallery.isNotEmpty) ...[
              const SizedBox(height: 9),
              SizedBox(
                height: 64,
                child: ListView(
                  scrollDirection: Axis.horizontal,
                  children: gallery
                      .map(
                        (url) => Padding(
                          padding: const EdgeInsets.only(right: 8),
                          child: ClipRRect(
                            borderRadius: BorderRadius.circular(10),
                            child: Image.network(
                              url,
                              width: 64,
                              height: 64,
                              fit: BoxFit.cover,
                              errorBuilder: (_, _, _) => const SizedBox(
                                width: 64,
                                child: Icon(Icons.image_not_supported_outlined),
                              ),
                            ),
                          ),
                        ),
                      )
                      .toList(),
                ),
              ),
            ],
            const SizedBox(height: 17),
            Text(
              widget.category.toUpperCase(),
              style: const TextStyle(
                color: AppColors.muted,
                letterSpacing: .7,
                fontSize: 10,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              product?.name ?? widget.product.name,
              style: const TextStyle(
                color: AppColors.ink,
                fontSize: 23,
                height: 1.2,
                fontWeight: FontWeight.w800,
              ),
            ),
            if ((product?.modelCode ?? widget.product.modelCode) != null) ...[
              const SizedBox(height: 4),
              Text(
                'Model ${product?.modelCode ?? widget.product.modelCode}',
                style: const TextStyle(color: AppColors.muted, fontSize: 13),
              ),
            ],
            if ((product?.summary ?? widget.product.summary)?.isNotEmpty ==
                true) ...[
              const SizedBox(height: 11),
              Text(
                product?.summary ?? widget.product.summary!,
                style: const TextStyle(
                  color: AppColors.muted,
                  fontSize: 14,
                  height: 1.5,
                ),
              ),
            ],
            if ((product?.description ?? '').isNotEmpty) ...[
              const SizedBox(height: 8),
              _ProductDescription(
                text: formatProductDescription(product!.description!),
              ),
            ],
            if ((product?.priceMinor ?? widget.product.priceMinor) != null) ...[
              const SizedBox(height: 12),
              Text(
                _productPrice(product ?? widget.product),
                style: const TextStyle(
                  color: AppColors.navy,
                  fontSize: 21,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
            if ((product?.stockStatus ?? widget.product.stockStatus) !=
                'unknown') ...[
              const SizedBox(height: 5),
              Text(
                _stockLabel(product?.stockStatus ?? widget.product.stockStatus),
                style: TextStyle(
                  color:
                      (product?.stockStatus ?? widget.product.stockStatus) ==
                          'instock'
                      ? const Color(0xFF2D754A)
                      : AppColors.muted,
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
            const SizedBox(height: 22),
            const Text(
              'Technical specifications',
              style: TextStyle(
                color: AppColors.ink,
                fontSize: 16,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 9),
            if (snapshot.connectionState == ConnectionState.waiting)
              const Padding(
                padding: EdgeInsets.all(16),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (snapshot.hasError && product == null)
              EmptyState(
                icon: Icons.wifi_off_rounded,
                title: 'Specifications unavailable',
                message: 'Reconnect and retry to load the published technical specifications.',
                actionLabel: 'Retry',
                onAction: _retryDetails,
              )
            else if (product == null || product.specifications.isEmpty)
              const Card(
                child: Padding(
                  padding: EdgeInsets.symmetric(horizontal: 14, vertical: 2),
                  child: EmptyState(
                    icon: Icons.fact_check_outlined,
                    title: 'Specifications not published',
                    message: 'Verified technical specifications have not been added for this product yet.',
                  ),
                ),
              )
            else
              Card(
                child: Column(
                  children: product.specifications.entries
                      .map(
                        (entry) => Padding(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 14,
                            vertical: 11,
                          ),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Expanded(
                                child: Text(
                                  entry.key,
                                  style: const TextStyle(
                                    color: AppColors.muted,
                                    fontSize: 12,
                                  ),
                                ),
                              ),
                              const SizedBox(width: 12),
                              Flexible(
                                child: Text(
                                  _display(entry.value),
                                  textAlign: TextAlign.end,
                                  style: const TextStyle(
                                    color: AppColors.ink,
                                    fontSize: 12,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                      )
                      .toList(),
                ),
              ),
            if (product?.applications.isNotEmpty == true) ...[
              const SizedBox(height: 18),
              const Text(
                'Applications',
                style: TextStyle(
                  color: AppColors.ink,
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 7,
                runSpacing: 7,
                children: product!.applications
                    .map((value) => Chip(label: Text(value)))
                    .toList(),
              ),
            ],
            if (product?.features.isNotEmpty == true) ...[
              const SizedBox(height: 18),
              const Text(
                'Key features',
                style: TextStyle(
                  color: AppColors.ink,
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 8),
              ...product!.features.map(
                (value) => Padding(
                  padding: const EdgeInsets.only(bottom: 7),
                  child: Row(
                    children: [
                      const Icon(
                        Icons.check_circle_outline_rounded,
                        color: AppColors.blue,
                        size: 17,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          value,
                          style: const TextStyle(
                            color: AppColors.muted,
                            fontSize: 12,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
            const SizedBox(height: 18),
            const Text(
              'Documents',
              style: TextStyle(
                color: AppColors.ink,
                fontSize: 16,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 9),
            if ((product?.documents ?? widget.product.documents).isNotEmpty)
              ...(product?.documents ?? widget.product.documents).map(
                (document) => Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Card(
                    child: ListTile(
                      leading: const Icon(
                        Icons.picture_as_pdf_outlined,
                        color: AppColors.blue,
                      ),
                      title: Text(
                        document.title,
                        style: const TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      subtitle: const Text(
                        'PDF document',
                        style: TextStyle(fontSize: 11),
                      ),
                      trailing: const Icon(Icons.open_in_new_rounded, size: 18),
                      onTap: () async {
                        final uri = Uri.tryParse(document.url);
                        if (uri != null && uri.scheme == 'https')
                          await launchUrl(
                            uri,
                            mode: LaunchMode.externalApplication,
                          );
                      },
                    ),
                  ),
                ),
              )
            else if (snapshot.connectionState == ConnectionState.done)
              const NoticeCard(
                message: 'No product brochure or datasheet is available for this product.',
              ),
            const SizedBox(height: 18),
            const NoticeCard(
              message: 'Product details are shown from the published catalogue. Confirm technical suitability with EnerTech before making a selection.',
            ),
            const SizedBox(height: 20),
            FilledButton.icon(
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => SolutionFinderScreen(
                    initialProducts: product?.name ?? widget.product.name,
                  ),
                ),
              ),
              icon: const Icon(Icons.request_quote_outlined),
              label: const Text('Request a quotation'),
            ),
            const SizedBox(height: 9),
            OutlinedButton.icon(
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => const SolutionFinderScreen(),
                ),
              ),
              icon: const Icon(Icons.support_agent_rounded),
              label: const Text('Ask an expert'),
            ),
          ],
        );
      },
    ),
  );

  String _display(Object? value) =>
      value is List ? value.join(', ') : value?.toString() ?? '—';

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
}

class _ProductDescription extends StatelessWidget {
  const _ProductDescription({required this.text});
  final String text;

  static final _heading = RegExp(
    r'^(Product Overview|Key Features|Technical Specifications|Specifications|Applications)$',
    caseSensitive: false,
  );

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      for (final line in text.split('\n'))
        if (line.trim().isEmpty)
          const SizedBox(height: 8)
        else if (_heading.hasMatch(line.trim()))
          Padding(
            padding: const EdgeInsets.only(top: 8, bottom: 3),
            child: Text(
              line.trim(),
              style: const TextStyle(
                color: AppColors.ink,
                fontSize: 14,
                fontWeight: FontWeight.w700,
              ),
            ),
          )
        else if (line.trimLeft().startsWith('• '))
          Padding(
            padding: const EdgeInsets.only(bottom: 5),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Padding(
                  padding: EdgeInsets.only(top: 3, right: 7),
                  child: Icon(Icons.circle, size: 6, color: AppColors.blue),
                ),
                Expanded(
                  child: Text(
                    line.trimLeft().substring(2),
                    style: const TextStyle(
                      color: AppColors.muted,
                      fontSize: 13,
                      height: 1.5,
                    ),
                  ),
                ),
              ],
            ),
          )
        else
          Text(
            line.trim(),
            style: const TextStyle(
              color: AppColors.muted,
              fontSize: 13,
              height: 1.5,
            ),
          ),
    ],
  );
}
