import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_dotenv/flutter_dotenv.dart';

import 'catalogue_models.dart';

class CatalogueException implements Exception {
  const CatalogueException(this.message);
  final String message;
  @override
  String toString() => message;
}

class CatalogueRepository {
  CatalogueRepository({String? baseUrl}) : _baseUrl = baseUrl ?? (const String.fromEnvironment('API_BASE_URL').isNotEmpty ? const String.fromEnvironment('API_BASE_URL') : (dotenv.env['API_BASE_URL'] ?? ''));

  final String _baseUrl;

  Future<List<ProductCategory>> getCategories() async {
    final json = await _getJson('/catalogue/categories');
    if (json is! List<dynamic>) throw const CatalogueException('The catalogue returned an unexpected category response.');
    return json.map((row) => ProductCategory.fromJson(row as Map<String, dynamic>)).toList(growable: false);
  }

  Future<ProductPageData> getProducts({String query = '', String? category, int limit = 24, int offset = 0}) async {
    final json = await _getJson('/catalogue/products', queryParameters: {
      'limit': '$limit',
      'offset': '$offset',
      if (query.trim().isNotEmpty) 'q': query.trim(),
      if (category != null && category.isNotEmpty) 'category': category,
    });
    if (json is! Map<String, dynamic>) throw const CatalogueException('The catalogue returned an unexpected product response.');
    return ProductPageData.fromJson(json);
  }

  Future<ProductDetails> getProduct(String slug) async {
    final json = await _getJson('/catalogue/products/${Uri.encodeComponent(slug)}');
    if (json is! Map<String, dynamic>) throw const CatalogueException('The catalogue returned an unexpected product response.');
    return ProductDetails.fromJson(json);
  }

  Future<dynamic> _getJson(String path, {Map<String, String>? queryParameters}) async {
    if (_baseUrl.trim().isEmpty) {
      throw const CatalogueException('Catalogue connection is not configured yet.');
    }
    final base = Uri.tryParse(_baseUrl);
    if (base == null || !base.hasScheme || !base.hasAuthority) {
      throw const CatalogueException('Catalogue connection settings are invalid.');
    }
    final root = base.path.endsWith('/') ? base : base.replace(path: '${base.path}/');
    final uri = root.resolve(path.startsWith('/') ? path.substring(1) : path).replace(queryParameters: queryParameters);
    final client = HttpClient()..connectionTimeout = const Duration(seconds: 6);
    try {
      final request = await client.getUrl(uri).timeout(const Duration(seconds: 8));
      request.headers.set(HttpHeaders.acceptHeader, 'application/json');
      final response = await request.close().timeout(const Duration(seconds: 8));
      final body = await response.transform(utf8.decoder).join().timeout(const Duration(seconds: 8));
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw CatalogueException('Catalogue service returned ${response.statusCode}. Try again shortly.');
      }
      return jsonDecode(body);
    } on CatalogueException {
      rethrow;
    } on TimeoutException {
      throw const CatalogueException('The catalogue is taking too long to respond. Check the connection and retry.');
    } on SocketException {
      throw const CatalogueException('Could not reach the catalogue. Check your connection and retry.');
    } on FormatException {
      throw const CatalogueException('The catalogue sent an unreadable response. Try again shortly.');
    } finally {
      client.close(force: true);
    }
  }
}
