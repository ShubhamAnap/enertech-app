import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';

import 'catalogue_models.dart';
import 'customer_profile_repository.dart';

class CatalogueException implements Exception {
  const CatalogueException(this.message);
  final String message;
  @override
  String toString() => message;
}

class CatalogueRepository {
  CatalogueRepository({String? baseUrl})
      : _baseUrl = baseUrl;

  final String? _baseUrl;

  String get baseUrl => _baseUrl ?? CustomerProfileRepository.effectiveBaseUrl;

  static const List<ProductCategory> _fallbackCategories = [
    ProductCategory(
      id: 'cat-online-ups',
      slug: 'online-ups',
      name: 'Online UPS Systems',
      description: 'True online double-conversion UPS systems for critical loads.',
    ),
    ProductCategory(
      id: 'cat-solar',
      slug: 'solar-inverters',
      name: 'Solar Hybrid Inverters',
      description: 'High-efficiency bi-directional solar inverters with MPPT.',
    ),
    ProductCategory(
      id: 'cat-bess',
      slug: 'bess',
      name: 'Battery Energy Storage (BESS)',
      description: 'Scalable LiFePO4 energy storage systems for industrial continuity.',
    ),
    ProductCategory(
      id: 'cat-ahf',
      slug: 'active-filters',
      name: 'Active Harmonic Filters',
      description: 'Dynamic power factor correction and harmonic distortion mitigation.',
    ),
  ];

  static const List<ProductDetails> _fallbackProducts = [
    ProductDetails(
      id: 'prod-maxipro-33',
      slug: 'maxipro-33-ups',
      name: 'EnerTech Maxi-Pro 33 (10kVA - 500kVA)',
      categoryId: 'cat-online-ups',
      modelCode: 'ET-MP-33',
      summary: 'Heavy-duty 3-phase industrial double-conversion online UPS.',
      description: 'Engineered for extreme power environments, medical imaging, IT servers, and process industries. Features galvanic isolation and high overload capability.',
      applications: ['Hospitals & Healthcare', 'Data Centers', 'Continuous Process Plants', 'Commercial Towers'],
      features: ['Galvanic Isolation Transformer', 'True Double Conversion Online Topology', 'Parallel redundancy up to 8 units', 'Intelligent battery management (IBMS)'],
      specifications: {'Topology': 'Online Double Conversion', 'Input Voltage': '400V 3-Phase ±20%', 'Output Power Factor': '0.9 / 1.0', 'Efficiency': '> 94%'},
    ),
    ProductDetails(
      id: 'prod-sunmax-hybrid',
      slug: 'sunmax-hybrid-inverter',
      name: 'EnerTech SunMax Hybrid (5kVA - 50kVA)',
      categoryId: 'cat-solar',
      modelCode: 'ET-SM-HYB',
      summary: 'Bi-directional solar hybrid inverter with intelligent grid synchronization.',
      description: 'Seamless integration of solar photovoltaic generation, grid power, and battery storage. Zero changeover time ensures uninterrupted power.',
      applications: ['Rooftop Solar for Commercial Buildings', 'Petrol Pumps', 'Institutions', 'Telecom Towers'],
      features: ['Dual MPPT Tracking', 'Zero Export Control Support', 'Generator Compatible', 'Remote cloud monitoring'],
      specifications: {'Capacity Range': '5kVA - 50kVA', 'MPPT Efficiency': '99.2%', 'Battery Support': 'Lead Acid & LiFePO4', 'Changeover Time': '< 5ms'},
    ),
    ProductDetails(
      id: 'prod-powervault-bess',
      slug: 'powervault-bess',
      name: 'EnerTech PowerVault BESS (20kWh - 500kWh)',
      categoryId: 'cat-bess',
      modelCode: 'ET-PV-BESS',
      summary: 'Modular LiFePO4 Battery Energy Storage System with BMS.',
      description: 'Industrial-grade energy storage designed for peak shaving, demand response, and backup power during grid failures.',
      applications: ['Microgrids', 'Renewable Energy Integration', 'Industrial Peak Shaving', 'EV Fast Charging Hubs'],
      features: ['Automated thermal management', 'Modular slide-in rack architecture', '> 6000 cycles lifecycle', 'Tier-1 LFP cells with multi-stage BMS'],
      specifications: {'Cell Chemistry': 'Lithium Iron Phosphate (LiFePO4)', 'Depth of Discharge': '90%', 'Communication': 'CAN / RS485 / Modbus', 'Design Life': '> 15 Years'},
    ),
    ProductDetails(
      id: 'prod-puresine-ahf',
      slug: 'puresine-ahf',
      name: 'EnerTech PureSine AHF-300',
      categoryId: 'cat-ahf',
      modelCode: 'ET-PS-AHF',
      summary: '3-Level topology active harmonic filter and power factor stabilizer.',
      description: 'Mitigates harmonics up to the 50th order, balances 3-phase unbalanced loads, and achieves near-unity power factor dynamically.',
      applications: ['Steel & Rolling Mills', 'Textile Plants', 'IT Parks', 'Heavy Machinery Facilities'],
      features: ['Dynamic response in < 5ms', 'Mitigates 2nd to 50th harmonics', 'Selectable compensation modes', 'Modular rack-mountable design'],
      specifications: {'Compensation Range': '50A to 600A modular', 'Target THDi': '< 3%', 'Efficiency': '> 97.5%', 'Response Time': '< 5ms'},
    ),
  ];

  Future<List<ProductCategory>> getCategories() async {
    try {
      final json = await _getJson('/catalogue/categories');
      if (json is List<dynamic> && json.isNotEmpty) {
        return json.map((row) => ProductCategory.fromJson(row as Map<String, dynamic>)).toList(growable: false);
      }
    } catch (e) {
      debugPrint('CatalogueRepository.getCategories network note: $e, using fallback data.');
    }
    return _fallbackCategories;
  }

  Future<ProductPageData> getProducts({String query = '', String? category, int limit = 24, int offset = 0}) async {
    try {
      final json = await _getJson('/catalogue/products', queryParameters: {
        'limit': '$limit',
        'offset': '$offset',
        if (query.trim().isNotEmpty) 'q': query.trim(),
        if (category != null && category.isNotEmpty) 'category': category,
      });
      if (json is Map<String, dynamic>) {
        final data = ProductPageData.fromJson(json);
        if (data.items.isNotEmpty) return data;
      }
    } catch (e) {
      debugPrint('CatalogueRepository.getProducts network note: $e, using fallback data.');
    }

    // Filter fallback products
    var filtered = _fallbackProducts.where((p) {
      if (category != null && category.isNotEmpty) {
        final cat = _fallbackCategories.where((c) => c.slug == category || c.id == category).firstOrNull;
        if (cat != null && p.categoryId != cat.id) return false;
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
      debugPrint('CatalogueRepository.getProduct network note: $e, using fallback.');
    }

    final found = _fallbackProducts.where((p) => p.slug == slug || p.id == slug).firstOrNull;
    if (found != null) return found;

    throw const CatalogueException('Product could not be found.');
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
