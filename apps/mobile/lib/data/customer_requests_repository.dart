import 'dart:convert';
import 'dart:io';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart';

import 'customer_profile_repository.dart';

class CustomerRequestRecord {
  const CustomerRequestRecord({
    required this.id,
    required this.kind,
    required this.status,
    required this.payload,
    required this.createdAt,
    this.resolutionNote,
  });

  final String id;
  final String kind;
  final String status;
  final Map<String, dynamic> payload;
  final DateTime createdAt;
  final String? resolutionNote;

  factory CustomerRequestRecord.fromJson(Map<String, dynamic> json) => CustomerRequestRecord(
    id: json['id'] as String? ?? 'req-${DateTime.now().millisecondsSinceEpoch}',
    kind: json['kind'] as String? ?? 'service',
    status: json['status'] as String? ?? 'submitted',
    payload: (json['payload'] as Map<String, dynamic>?) ?? const {},
    createdAt: DateTime.tryParse(json['created_at'] as String? ?? '') ?? DateTime.now(),
    resolutionNote: json['resolution_note'] as String?,
  );
}

class CustomerRequestsRepository {
  CustomerRequestsRepository({String? baseUrl}) : _baseUrl = baseUrl;

  final String? _baseUrl;

  String get baseUrl => _baseUrl ?? CustomerProfileRepository.effectiveBaseUrl;

  static final List<CustomerRequestRecord> _localSubmittedRequests = [];

  Future<List<CustomerRequestRecord>> loadMine() async {
    try {
      final value = await _request('GET', '/requests');
      if (value is List<dynamic>) {
        final serverList = value.map((row) => CustomerRequestRecord.fromJson(row as Map<String, dynamic>)).toList();
        return [..._localSubmittedRequests, ...serverList];
      }
    } catch (e) {
      debugPrint('CustomerRequestsRepository.loadMine network note: $e');
    }
    return _localSubmittedRequests;
  }

  Future<CustomerRequestRecord> submitService({
    required String model,
    required String category,
    required String description,
    required String location,
    String? serial,
  }) async {
    final payload = {
      'product_model': model,
      'serial_number': serial,
      'problem_category': category,
      'description': description,
      'service_location': location,
    };
    try {
      final value = await _request('POST', '/requests/service', body: payload);
      return CustomerRequestRecord.fromJson(value as Map<String, dynamic>);
    } catch (e) {
      debugPrint('submitService offline note: $e, saved locally.');
      final local = CustomerRequestRecord(
        id: 'local-${DateTime.now().millisecondsSinceEpoch}',
        kind: 'service',
        status: 'submitted_offline',
        payload: payload,
        createdAt: DateTime.now(),
        resolutionNote: 'Saved locally on device (offline mode).',
      );
      _localSubmittedRequests.insert(0, local);
      return local;
    }
  }

  Future<CustomerRequestRecord> submitQuote({
    required String application,
    required String equipment,
    required bool capacityKnown,
    required String capacity,
    required int quantity,
    required String location,
    required String timeline,
  }) async {
    final payload = {
      'application': application,
      'equipment_or_load': equipment,
      'capacity_known': capacityKnown,
      'capacity': capacity.isEmpty ? null : capacity,
      'quantity': quantity,
      'project_location': location,
      'expected_timeline': timeline,
    };
    try {
      final value = await _request('POST', '/requests/quote', body: payload);
      return CustomerRequestRecord.fromJson(value as Map<String, dynamic>);
    } catch (e) {
      debugPrint('submitQuote offline note: $e, saved locally.');
      final local = CustomerRequestRecord(
        id: 'local-${DateTime.now().millisecondsSinceEpoch}',
        kind: 'quote',
        status: 'submitted_offline',
        payload: payload,
        createdAt: DateTime.now(),
        resolutionNote: 'Saved locally on device (offline mode).',
      );
      _localSubmittedRequests.insert(0, local);
      return local;
    }
  }

  Future<dynamic> _request(String method, String path, {Map<String, Object?>? body}) async {
    final user = FirebaseAuth.instance.currentUser;
    if (user == null) throw const HttpException('Sign in before submitting or tracking requests.');
    if (!user.emailVerified) throw const HttpException('Verify your email before submitting a request.');
    final base = Uri.tryParse(baseUrl);
    if (base == null || !base.hasScheme || !base.hasAuthority) {
      throw const HttpException('The customer platform API is not configured.');
    }
    final root = base.path.endsWith('/') ? base : base.replace(path: '${base.path}/');
    final uri = root.resolve(path.startsWith('/') ? path.substring(1) : path);
    final client = HttpClient()..connectionTimeout = const Duration(seconds: 4);
    try {
      final request = await (method == 'POST' ? client.postUrl(uri) : client.getUrl(uri)).timeout(const Duration(seconds: 5));
      request.headers.set(HttpHeaders.acceptHeader, 'application/json');
      request.headers.set(HttpHeaders.authorizationHeader, 'Bearer ${await user.getIdToken()}');
      if (body != null) {
        request.headers.contentType = ContentType.json;
        request.write(jsonEncode(body));
      }
      final response = await request.close().timeout(const Duration(seconds: 5));
      final text = await response.transform(utf8.decoder).join().timeout(const Duration(seconds: 5));
      final decoded = text.isEmpty ? null : jsonDecode(text);
      if (response.statusCode < 200 || response.statusCode >= 300) {
        final message = decoded is Map<String, dynamic> ? decoded['detail'] as String? : null;
        throw HttpException(message ?? 'The request could not be completed (${response.statusCode}).');
      }
      return decoded;
    } finally {
      client.close(force: true);
    }
  }
}
