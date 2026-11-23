import 'dart:convert';
import 'dart:io';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';

class CustomerRequestRecord {
  const CustomerRequestRecord({required this.id, required this.kind, required this.status, required this.payload, required this.createdAt, this.resolutionNote});
  final String id;
  final String kind;
  final String status;
  final Map<String, dynamic> payload;
  final DateTime createdAt;
  final String? resolutionNote;

  factory CustomerRequestRecord.fromJson(Map<String, dynamic> json) => CustomerRequestRecord(
    id: json['id'] as String, kind: json['kind'] as String, status: json['status'] as String,
    payload: (json['payload'] as Map<String, dynamic>?) ?? const {},
    createdAt: DateTime.tryParse(json['created_at'] as String? ?? '') ?? DateTime.now(),
    resolutionNote: json['resolution_note'] as String?,
  );
}

class CustomerRequestsRepository {
  CustomerRequestsRepository({String? baseUrl}) : _baseUrl = baseUrl ?? (const String.fromEnvironment('API_BASE_URL').isNotEmpty ? const String.fromEnvironment('API_BASE_URL') : ((dotenv.isInitialized ? dotenv.env['API_BASE_URL'] : null) ?? 'http://10.0.2.2:8000/api/v1'));
  final String _baseUrl;

  Future<List<CustomerRequestRecord>> loadMine() async {
    final value = await _request('GET', '/requests');
    if (value is! List<dynamic>) throw const HttpException('The API returned an unexpected request list.');
    return value.map((row) => CustomerRequestRecord.fromJson(row as Map<String, dynamic>)).toList(growable: false);
  }

  Future<CustomerRequestRecord> submitService({required String model, required String category, required String description, required String location, String? serial}) async {
    final value = await _request('POST', '/requests/service', body: {
      'product_model': model, 'serial_number': serial, 'problem_category': category,
      'description': description, 'service_location': location,
    });
    return CustomerRequestRecord.fromJson(value as Map<String, dynamic>);
  }

  Future<CustomerRequestRecord> submitQuote({required String application, required String equipment, required bool capacityKnown, required String capacity, required int quantity, required String location, required String timeline}) async {
    final value = await _request('POST', '/requests/quote', body: {
      'application': application, 'equipment_or_load': equipment, 'capacity_known': capacityKnown,
      'capacity': capacity.isEmpty ? null : capacity, 'quantity': quantity,
      'project_location': location, 'expected_timeline': timeline,
    });
    return CustomerRequestRecord.fromJson(value as Map<String, dynamic>);
  }

  Future<dynamic> _request(String method, String path, {Map<String, Object?>? body}) async {
    final user = FirebaseAuth.instance.currentUser;
    if (user == null) throw const HttpException('Sign in before submitting or tracking requests.');
    if (!user.emailVerified) throw const HttpException('Verify your email before submitting a request.');
    final base = Uri.tryParse(_baseUrl);
    if (base == null || !base.hasScheme || !base.hasAuthority) throw const HttpException('The customer platform API is not configured.');
    final root = base.path.endsWith('/') ? base : base.replace(path: '${base.path}/');
    final uri = root.resolve(path.startsWith('/') ? path.substring(1) : path);
    final client = HttpClient()..connectionTimeout = const Duration(seconds: 8);
    try {
      final request = await (method == 'POST' ? client.postUrl(uri) : client.getUrl(uri)).timeout(const Duration(seconds: 10));
      request.headers.set(HttpHeaders.acceptHeader, 'application/json');
      request.headers.set(HttpHeaders.authorizationHeader, 'Bearer ${await user.getIdToken()}');
      if (body != null) {
        request.headers.contentType = ContentType.json;
        request.write(jsonEncode(body));
      }
      final response = await request.close().timeout(const Duration(seconds: 12));
      final text = await response.transform(utf8.decoder).join().timeout(const Duration(seconds: 12));
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
