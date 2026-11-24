import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:shared_preferences/shared_preferences.dart';

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

  String get roleDisplayName => switch (customerType) {
    'reseller' => 'Reseller / Retailer',
    'epc' => 'EPC Contractor',
    'distributor' => 'Authorized Distributor',
    _ => 'End User / Consumer',
  };

  bool get isBusiness => customerType != 'end_user';

  factory CustomerProfile.fromJson(Map<String, dynamic> json) =>
      CustomerProfile(
        id:
            json['id'] as String? ??
            'profile-${DateTime.now().millisecondsSinceEpoch}',
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

  static final Map<String, CustomerProfile> _cachedProfiles = {};
  static String? _customBaseUrl;

  static const String _prefProfilePrefix = 'enertech_profile_';
  static const String _prefOnboardingPrefix = 'enertech_onboarding_done_';

  static void setCustomBaseUrl(String url) {
    _customBaseUrl = url.trim();
  }

  static String get effectiveBaseUrl {
    if (_customBaseUrl != null && _customBaseUrl!.isNotEmpty) {
      return _customBaseUrl!;
    }
    const envArg = String.fromEnvironment('API_BASE_URL');
    if (envArg.isNotEmpty) return envArg;
    if (dotenv.isInitialized &&
        dotenv.env['API_BASE_URL'] != null &&
        dotenv.env['API_BASE_URL']!.isNotEmpty) {
      return dotenv.env['API_BASE_URL']!;
    }
    return '';
  }

  String get baseUrl => _baseUrl ?? effectiveBaseUrl;

  /// Loads current user's profile.
  /// Returns null if the user has NOT completed onboarding yet,
  /// so that the onboarding role-selection screen is guaranteed to show.
  Future<CustomerProfile?> loadMine({String? userUid}) async {
    final uid = userUid ?? FirebaseAuth.instance.currentUser?.uid;
    if (uid == null) return null;

    // 1. Check local SharedPreferences
    final prefs = await SharedPreferences.getInstance();
    final isDone = prefs.getBool('$_prefOnboardingPrefix$uid') ?? false;
    final cachedJson = prefs.getString('$_prefProfilePrefix$uid');

    if (cachedJson != null && cachedJson.isNotEmpty) {
      try {
        final decoded = jsonDecode(cachedJson) as Map<String, dynamic>;
        _cachedProfiles[uid] = CustomerProfile.fromJson(decoded);
      } catch (e) {
        debugPrint('Error decoding local profile: $e');
      }
    }

    // 2. Try fetching from remote backend API if possible
    try {
      final value = await _request('GET');
      if (value != null && value is Map<String, dynamic>) {
        final remote = CustomerProfile.fromJson(value);
        _cachedProfiles[uid] = remote;
        await prefs.setString(
          '$_prefProfilePrefix$uid',
          jsonEncode(remote.toJson()),
        );
        await prefs.setBool('$_prefOnboardingPrefix$uid', true);
        return remote;
      }
      if (value == null) {
        _cachedProfiles.remove(uid);
        await prefs.remove('$_prefProfilePrefix$uid');
        await prefs.setBool('$_prefOnboardingPrefix$uid', false);
        return null;
      }
    } catch (e) {
      debugPrint(
        'Backend profile fetch note (falling back to local cache): $e',
      );
    }

    // 3. If onboarding was completed locally, return the cached profile
    if (isDone && _cachedProfiles[uid] != null) {
      return _cachedProfiles[uid];
    }

    // 4. If onboarding was never completed for this user, return null so onboarding screen opens!
    return null;
  }

  /// Saves user's onboarding profile persistently in local SharedPreferences
  /// and attempts to sync to the backend API.
  Future<CustomerProfile> save(
    Map<String, Object?> values, {
    String? userUid,
  }) async {
    final user = FirebaseAuth.instance.currentUser;
    final uid =
        userUid ??
        user?.uid ??
        'profile-${DateTime.now().millisecondsSinceEpoch}';

    // The backend is authoritative: never tell a new customer their profile was
    // saved if the API rejected it or could not persist it.
    final value = await _request('PUT', body: values);
    if (value is! Map<String, dynamic>) {
      throw const HttpException(
        'The customer platform returned an invalid profile response.',
      );
    }
    final savedProfile = CustomerProfile.fromJson(value);
    _cachedProfiles[uid] = savedProfile;

    // Cache only after the backend confirms the save.
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(
        '$_prefProfilePrefix$uid',
        jsonEncode(savedProfile.toJson()),
      );
      await prefs.setBool('$_prefOnboardingPrefix$uid', true);
    } catch (e) {
      debugPrint('Error writing to SharedPreferences: $e');
    }
    return savedProfile;
  }

  /// Clears local profile cache on sign out
  static void clearCache() {
    _cachedProfiles.clear();
  }

  Future<dynamic> _request(String method, {Map<String, Object?>? body}) async {
    final user = FirebaseAuth.instance.currentUser;
    if (user == null)
      throw const HttpException('Sign in to access your customer profile.');
    final base = Uri.tryParse(baseUrl);
    if (base == null || !base.hasScheme || !base.hasAuthority) {
      throw const HttpException('The customer platform API is not configured.');
    }
    final root = base.path.endsWith('/')
        ? base
        : base.replace(path: '${base.path}/');
    final uri = root.resolve('customers/me');
    final client = HttpClient()..connectionTimeout = const Duration(seconds: 4);
    try {
      final request =
          await (method == 'PUT' ? client.putUrl(uri) : client.getUrl(uri))
              .timeout(const Duration(seconds: 4));
      request.headers.set(HttpHeaders.acceptHeader, 'application/json');
      final token = await user.getIdToken();
      if (token == null || token.isEmpty) {
        throw const HttpException(
          'Your sign-in session could not be verified. Sign in again.',
        );
      }
      request.headers.set(HttpHeaders.authorizationHeader, 'Bearer $token');
      if (body != null) {
        request.headers.contentType = ContentType.json;
        request.write(jsonEncode(body));
      }
      final response = await request.close().timeout(
        const Duration(seconds: 4),
      );
      final text = await response
          .transform(utf8.decoder)
          .join()
          .timeout(const Duration(seconds: 4));
      final decoded = text.isEmpty ? null : jsonDecode(text);
      if (response.statusCode < 200 || response.statusCode >= 300) {
        final message = decoded is Map<String, dynamic>
            ? decoded['detail'] as String?
            : null;
        throw HttpException(
          message ?? 'Profile error (${response.statusCode}).',
        );
      }
      return decoded;
    } finally {
      client.close(force: true);
    }
  }
}
