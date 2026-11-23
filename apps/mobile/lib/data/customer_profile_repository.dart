import 'dart:convert';
import 'dart:io';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';

class CustomerProfile {
  const CustomerProfile({required this.id, required this.customerType, required this.name, required this.mobileNumber, required this.email, required this.location, this.companyName, this.gstNumber});
  final String id;
  final String customerType;
  final String name;
  final String mobileNumber;
  final String email;
  final String location;
  final String? companyName;
  final String? gstNumber;

  factory CustomerProfile.fromJson(Map<String, dynamic> json) => CustomerProfile(
    id: json['id'] as String,
    customerType: json['customer_type'] as String,
    name: json['name'] as String,
    mobileNumber: json['mobile_number'] as String,
    email: json['email'] as String,
    location: json['location'] as String,
    companyName: json['company_name'] as String?,
    gstNumber: json['gst_number'] as String?,
  );
}

class CustomerProfileRepository {
  CustomerProfileRepository({String? baseUrl}) : _baseUrl = baseUrl ?? (const String.fromEnvironment('API_BASE_URL').isNotEmpty ? const String.fromEnvironment('API_BASE_URL') : (dotenv.env['API_BASE_URL'] ?? ''));
  final String _baseUrl;

  Future<CustomerProfile?> loadMine() async {
    final value = await _request('GET');
    return value == null ? null : CustomerProfile.fromJson(value as Map<String, dynamic>);
  }

  Future<CustomerProfile> save(Map<String, Object?> values) async => CustomerProfile.fromJson(await _request('PUT', body: values) as Map<String, dynamic>);

  Future<dynamic> _request(String method, {Map<String, Object?>? body}) async {
    final user = FirebaseAuth.instance.currentUser;
    if (user == null) throw const HttpException('Sign in to complete your customer profile.');
    if (!user.emailVerified) throw const HttpException('Verify your email before completing your profile.');
    final base = Uri.tryParse(_baseUrl);
    if (base == null || !base.hasScheme || !base.hasAuthority) throw const HttpException('The customer platform API is not configured.');
    final root = base.path.endsWith('/') ? base : base.replace(path: '${base.path}/');
    final uri = root.resolve('customers/me');
    final client = HttpClient()..connectionTimeout = const Duration(seconds: 8);
    try {
      final request = await (method == 'PUT' ? client.putUrl(uri) : client.getUrl(uri)).timeout(const Duration(seconds: 10));
      request.headers.set(HttpHeaders.acceptHeader, 'application/json');
      request.headers.set(HttpHeaders.authorizationHeader, 'Bearer ${await user.getIdToken()}');
      if (body != null) { request.headers.contentType = ContentType.json; request.write(jsonEncode(body)); }
      final response = await request.close().timeout(const Duration(seconds: 12));
      final text = await response.transform(utf8.decoder).join().timeout(const Duration(seconds: 12));
      final decoded = text.isEmpty ? null : jsonDecode(text);
      if (response.statusCode < 200 || response.statusCode >= 300) {
        final message = decoded is Map<String, dynamic> ? decoded['detail'] as String? : null;
        throw HttpException(message ?? 'Profile could not be loaded (${response.statusCode}).');
      }
      return decoded;
    } finally {
      client.close(force: true);
    }
  }
}
