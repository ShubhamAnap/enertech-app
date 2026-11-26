class ProductSummary {
  const ProductSummary({
    required this.id,
    required this.slug,
    required this.name,
    required this.categoryId,
    this.categoryIds = const [],
    this.modelCode,
    this.summary,
    this.imageUrl,
    this.priceMinor,
    this.currencyCode = 'INR',
    this.currencyMinorUnit = 2,
    this.stockStatus = 'unknown',
    this.stockQuantity,
    this.documents = const [],
    this.catalogPdfUrl,
  });

  final String id;
  final String slug;
  final String name;
  final String categoryId;
  final List<String> categoryIds;
  final String? modelCode;
  final String? summary;
  final String? imageUrl;
  final int? priceMinor;
  final String currencyCode;
  final int currencyMinorUnit;
  final String stockStatus;
  final int? stockQuantity;
  final List<ProductDocument> documents;
  final String? catalogPdfUrl;

  factory ProductSummary.fromJson(Map<String, dynamic> json) {
    final parsedCatalogPdf = json['catalog_pdf_url'] as String?;
    final rawDocs = (json['documents'] as List<dynamic>? ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(ProductDocument.fromJson)
        .toList(growable: false);
    final resolvedDocs = rawDocs.isNotEmpty
        ? rawDocs
        : (parsedCatalogPdf != null && parsedCatalogPdf.startsWith('https://'))
            ? [ProductDocument(title: 'Product catalogue PDF', url: parsedCatalogPdf)]
            : const <ProductDocument>[];
    return ProductSummary(
      id: json['id'] as String,
      slug: json['slug'] as String,
      name: json['name'] as String,
      categoryId: json['category_id'] as String,
      categoryIds: (json['category_ids'] as List<dynamic>? ?? [json['category_id']])
          .whereType<String>()
          .toList(growable: false),
      modelCode: json['model_code'] as String?,
      summary: json['summary'] as String?,
      imageUrl: json['image_url'] as String?,
      priceMinor: json['price_minor'] as int?,
      currencyCode: json['currency_code'] as String? ?? 'INR',
      currencyMinorUnit: json['currency_minor_unit'] as int? ?? 2,
      stockStatus: json['stock_status'] as String? ?? 'unknown',
      stockQuantity: json['stock_quantity'] as int?,
      documents: resolvedDocs,
      catalogPdfUrl: parsedCatalogPdf ?? (resolvedDocs.isNotEmpty ? resolvedDocs.first.url : null),
    );
  }
}

class ProductDetails extends ProductSummary {
  const ProductDetails({
    required super.id,
    required super.slug,
    required super.name,
    required super.categoryId,
    super.categoryIds = const [],
    super.modelCode,
    super.summary,
    super.imageUrl,
    super.priceMinor,
    super.currencyCode,
    super.currencyMinorUnit,
    super.stockStatus,
    super.stockQuantity,
    super.documents = const [],
    super.catalogPdfUrl,
    this.description,
    this.applications = const [],
    this.features = const [],
    this.specifications = const {},
    this.galleryImages = const [],
  });
  final String? description;
  final List<String> applications;
  final List<String> features;
  final Map<String, dynamic> specifications;
  final List<String> galleryImages;
  factory ProductDetails.fromJson(Map<String, dynamic> json) {
    final parsedCatalogPdf = json['catalog_pdf_url'] as String?;
    final rawDocs = (json['documents'] as List<dynamic>? ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(ProductDocument.fromJson)
        .toList(growable: false);
    final resolvedDocs = rawDocs.isNotEmpty
        ? rawDocs
        : (parsedCatalogPdf != null && parsedCatalogPdf.startsWith('https://'))
            ? [ProductDocument(title: 'Product catalogue PDF', url: parsedCatalogPdf)]
            : const <ProductDocument>[];
    return ProductDetails(
      id: json['id'] as String,
      slug: json['slug'] as String,
      name: json['name'] as String,
      categoryId: json['category_id'] as String,
      categoryIds: (json['category_ids'] as List<dynamic>? ?? [json['category_id']])
          .whereType<String>()
          .toList(growable: false),
      modelCode: json['model_code'] as String?,
      summary: json['summary'] as String?,
      imageUrl: json['image_url'] as String?,
      priceMinor: json['price_minor'] as int?,
      currencyCode: json['currency_code'] as String? ?? 'INR',
      currencyMinorUnit: json['currency_minor_unit'] as int? ?? 2,
      stockStatus: json['stock_status'] as String? ?? 'unknown',
      stockQuantity: json['stock_quantity'] as int?,
      documents: resolvedDocs,
      catalogPdfUrl: parsedCatalogPdf ?? (resolvedDocs.isNotEmpty ? resolvedDocs.first.url : null),
      description: json['description'] as String?,
      applications: (json['applications'] as List<dynamic>? ?? const [])
          .whereType<String>()
          .toList(growable: false),
      features: (json['features'] as List<dynamic>? ?? const [])
          .whereType<String>()
          .toList(growable: false),
      specifications:
          (json['specifications'] as Map<String, dynamic>?) ?? const {},
      galleryImages: (json['gallery_images'] as List<dynamic>? ?? const [])
          .whereType<String>()
          .toList(growable: false),
    );
  }
}

class ProductDocument {
  const ProductDocument({required this.title, required this.url});
  final String title;
  final String url;
  factory ProductDocument.fromJson(Map<String, dynamic> json) =>
      ProductDocument(
        title: json['title'] as String? ?? 'Product document',
        url: json['url'] as String? ?? '',
      );
}

class ProductPageData {
  const ProductPageData({required this.items, required this.total});

  final List<ProductSummary> items;
  final int total;

  factory ProductPageData.fromJson(Map<String, dynamic> json) {
    final rows = json['items'] as List<dynamic>? ?? const [];
    return ProductPageData(
      items: rows
          .map((row) => ProductSummary.fromJson(row as Map<String, dynamic>))
          .toList(growable: false),
      total: json['total'] as int? ?? 0,
    );
  }
}

class ProductCategory {
  const ProductCategory({
    required this.id,
    required this.slug,
    required this.name,
    this.description,
    this.imageUrl,
  });

  final String id;
  final String slug;
  final String name;
  final String? description;
  final String? imageUrl;

  factory ProductCategory.fromJson(Map<String, dynamic> json) =>
      ProductCategory(
        id: json['id'] as String,
        slug: json['slug'] as String,
        name: json['name'] as String,
        description: json['description'] as String?,
        imageUrl: json['image_url'] as String?,
      );
}
