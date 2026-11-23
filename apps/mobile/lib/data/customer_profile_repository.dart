import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';

class CustomerProfile {
  const CustomerProfile({
    required this.id,
    required this.customerType,
    required this.name,
    required this.mobileNumber,
    required this.email,
    required this.location,
    this.companyName,
    this.gstNumber,
  });

  final String id;
  final String customerType;
  final String name;
  final String mobileNumber;
  final String email;
  final String location;
  final String? companyName;
  final String? gstNumber;

  factory CustomerProfile.fromJson(Map<String, dynamic> json) => CustomerProfile(
    id: json['id'] as String? ?? 'profile-${DateTime.now().millisecondsSinceEpoch}',
    customerType: json['customer_type'] as String? ?? 'end_user',
    name: json['name'] as String? ?? 'Customer',
    mobileNumber: json['mobile_number'] as String? ?? '',
    email: json['email'] as String? ?? '',
    location: json['location'] as String? ?? '',
    companyName: json['company_name'] as String?,
    gstNumber: json['gst_number'] as String?,
  );

  Map<String, dynamic> toJson() => {
    'id': id,
    'customer_type': customerType,
    'name': name,
    'mobile_number': mobileNumber,
    'email': email,
    'location': location,
    if (companyName != null) 'company_name': companyName,
    if (gstNumber != null) 'gst_number': gstNumber,
  };
}

class CustomerProfileRepository {
  CustomerProfileRepository({String? baseUrl}) : _baseUrl = baseUrl;

  final String? _baseUrl;

  static CustomerProfile? _cachedProfile;
  static bool _offlineBypass = false;
  static String? _customBaseUrl;

  static void setOfflineBypass(bool value) {
    _offlineBypass = value;
  }

  static bool get isOfflineBypass => _offlineBypass;

  static void setCustomBaseUrl(String url) {
    _customBaseUrl = url.trim();
  }

  static String get effectiveBaseUrl {
    if (_customBaseUrl != null && _customBaseUrl!.isNotEmpty) {
      return _customBaseUrl!;
    }
    const envArg = String.fromEnvironment('API_BASE_URL');
    if (envArg.isNotEmpty) return envArg;
    if (dotenv.isInitialized && dotenv.env['API_BASE_URL'] != null && dotenv.env['API_BASE_URL']!.isNotEmpty) {
      return dotenv.env['API_BASE_URL']!;
    }
    return 'http://10.0.2.2:8000/api/v1';
  }

  String get baseUrl => _baseUrl ?? effectiveBaseUrl;

  Future<CustomerProfile?> loadMine({bool allowOfflineFallback = true}) async {
    if (_offlineBypass && _cachedProfile != null) {
      return _cachedProfile;
    }
    try {
      final value = await _request('GET');
      if (value == null) return null;
      _cachedProfile = CustomerProfile.fromJson(value as Map<String, dynamic>);
      return _cachedProfile;
    } catch (e) {
      debugPrint('CustomerProfileRepository.loadMine network note: $e');
      if (allowOfflineFallback) {
        final user = FirebaseAuth.instance.currentUser;
        if (user != null) {
          if (_cachedProfile != null) return _cachedProfile;
          final fallback = CustomerProfile(
            id: user.uid,
            customerType: 'end_user',
            name: (user.displayName != null && user.displayName!.trim().isNotEmpty)
                ? user.displayName!.trim()
                : (user.email?.split('@').first ?? 'EnerTech Customer'),
            mobileNumber: user.phoneNumber ?? '',
            email: user.email ?? '',
            location: 'India',
          );
          _cachedProfile = fallback;
          return fallback;
        }
      }
      rethrow;
    }
  }

  Future<CustomerProfile> save(Map<String, Object?> values) async {
    try {
      final value = await _request('PUT', body: values);
      final profile = CustomerProfile.fromJson(value as Map<String, dynamic>);
      _cachedProfile = profile;
      return profile;
    } catch (e) {
      debugPrint('CustomerProfileRepository.save network note, saving locally: $e');
      final user = FirebaseAuth.instance.currentUser;
      final local = CustomerProfile(
        id: user?.uid ?? 'profile-${DateTime.now().millisecondsSinceEpoch}',
        customerType: (values['customer_type'] as String?) ?? 'end_user',
        name: (values['name'] as String?) ?? user?.displayName ?? 'Customer',
        mobileNumber: (values['mobile_number'] as String?) ?? '',
        email: (values['email'] as String?) ?? user?.email ?? '',
        location: (values['location'] as String?) ?? '',
        companyName: values['company_name'] as String?,
        gstNumber: values['gst_number'] as String?,
      );
      _cachedProfile = local;
      return local;
    }
  }

  Future<dynamic> _request(String method, {Map<String, Object?>? body}) async {
    final user = FirebaseAuth.instance.currentUser;
    if (user == null) throw const HttpException('Sign in to complete your customer profile.');
    if (!user.emailVerified) throw const HttpException('Verify your email before completing your profile.');
    final base = Uri.tryParse(baseUrl);
    if (base == null || !base.hasScheme || !base.hasAuthority) {
      throw const HttpException('The customer platform API is not configured.');
    }
    final root = base.path.endsWith('/') ? base : base.replace(path: '${base.path}/');
    final uri = root.resolve('customers/me');
    final client = HttpClient()..connectionTimeout = const Duration(seconds: 4);
    try {
      final request = await (method == 'PUT' ? client.putUrl(uri) : client.getUrl(uri)).timeout(const Duration(seconds: 5));
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
        throw HttpException(message ?? 'Profile could not be loaded (${response.statusCode}).');
      }
      return decoded;
    } finally {
      client.close(force: true);
    }
  }
}
