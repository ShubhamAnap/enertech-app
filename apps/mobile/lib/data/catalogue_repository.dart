import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'catalogue_models.dart';
import 'customer_profile_repository.dart';

class CatalogueException implements Exception {
  const CatalogueException(this.message);
  final String message;
  @override
  String toString() => message;
}

class CatalogueRepository {
  CatalogueRepository({String? baseUrl}) : _baseUrl = baseUrl;

  final String? _baseUrl;

  String get baseUrl => _baseUrl ?? CustomerProfileRepository.effectiveBaseUrl;

  static const String _categoriesCacheKey = 'enertech_cached_categories_v1';
  static const String _productsCacheKey = 'enertech_cached_products_v1';

  Future<List<ProductCategory>> getCategories() async {
    // 1. Try local cache first for instant opening
    List<ProductCategory> cached = [];
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(_categoriesCacheKey);
      if (raw != null && raw.isNotEmpty) {
        final decoded = jsonDecode(raw);
        if (decoded is List) {
          cached = decoded.map((row) => ProductCategory.fromJson(row as Map<String, dynamic>)).toList();
        }
      }
    } catch (_) {}

    // 2. Fetch fresh categories from backend API
    try {
      final json = await _getJson('/catalogue/categories');
      if (json is List<dynamic> && json.isNotEmpty) {
        final fresh = json.map((row) => ProductCategory.fromJson(row as Map<String, dynamic>)).toList(growable: false);
        // Save to cache asynchronously
        unawaited(SharedPreferences.getInstance().then((p) => p.setString(_categoriesCacheKey, jsonEncode(json))));
        return fresh;
      }
    } catch (e) {
      debugPrint('CatalogueRepository.getCategories network note: $e');
    }

    return cached;
  }

  Future<ProductPageData> getProducts({String query = '', String? category, int limit = 24, int offset = 0}) async {
    // 1. Try local cache first for instant display
    List<ProductSummary> cachedProducts = [];
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(_productsCacheKey);
      if (raw != null && raw.isNotEmpty) {
        final decoded = jsonDecode(raw);
        if (decoded is Map<String, dynamic>) {
          cachedProducts = ProductPageData.fromJson(decoded).items;
        }
      }
    } catch (_) {}

    // 2. Fetch fresh products from backend API
    try {
      final json = await _getJson('/catalogue/products', queryParameters: {
        'limit': '$limit',
        'offset': '$offset',
        if (query.trim().isNotEmpty) 'q': query.trim(),
        if (category != null && category.isNotEmpty) 'category': category,
      });
      if (json is Map<String, dynamic>) {
        final freshData = ProductPageData.fromJson(json);
        if (freshData.items.isNotEmpty) {
          // Cache whole catalogue when query is empty
          if (query.trim().isEmpty && (category == null || category.isEmpty)) {
            unawaited(SharedPreferences.getInstance().then((p) => p.setString(_productsCacheKey, jsonEncode(json))));
          }
          return freshData;
        }
      }
    } catch (e) {
      debugPrint('CatalogueRepository.getProducts network note: $e');
    }

    // 3. If network fails or empty, filter cached real products
    var filtered = cachedProducts.where((p) {
      if (category != null && category.isNotEmpty && p.categoryId != category) {
        return false;
      }
      if (query.trim().isNotEmpty) {
        final q = query.trim().toLowerCase();
        final match = p.name.toLowerCase().contains(q) ||
            (p.summary?.toLowerCase().contains(q) ?? false) ||
            (p.modelCode?.toLowerCase().contains(q) ?? false);
        if (!match) return false;
      }
      return true;
    }).toList();

    return ProductPageData(
      items: filtered.skip(offset).take(limit).toList(),
      total: filtered.length,
    );
  }

  Future<ProductDetails> getProduct(String slug) async {
    try {
      final json = await _getJson('/catalogue/products/${Uri.encodeComponent(slug)}');
      if (json is Map<String, dynamic>) {
        return ProductDetails.fromJson(json);
      }
    } catch (e) {
      debugPrint('CatalogueRepository.getProduct network note: $e');
    }

    throw const CatalogueException('Product could not be loaded from server.');
  }

  Future<dynamic> _getJson(String path, {Map<String, String>? queryParameters}) async {
    final base = Uri.tryParse(baseUrl);
    if (base == null || !base.hasScheme || !base.hasAuthority) {
      throw const CatalogueException('Catalogue connection settings are invalid.');
    }
    final root = base.path.endsWith('/') ? base : base.replace(path: '${base.path}/');
    final uri = root.resolve(path.startsWith('/') ? path.substring(1) : path).replace(queryParameters: queryParameters);
    final client = HttpClient()..connectionTimeout = const Duration(seconds: 4);
    try {
      final request = await client.getUrl(uri).timeout(const Duration(seconds: 5));
      request.headers.set(HttpHeaders.acceptHeader, 'application/json');
      final response = await request.close().timeout(const Duration(seconds: 5));
      final body = await response.transform(utf8.decoder).join().timeout(const Duration(seconds: 5));
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw CatalogueException('Catalogue service returned ${response.statusCode}.');
      }
      return jsonDecode(body);
    } finally {
      client.close(force: true);
    }
  }
}
