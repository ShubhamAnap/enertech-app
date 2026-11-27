import 'dart:convert';
import 'dart:io';

import 'customer_profile_repository.dart';

class LegalVersions {
  const LegalVersions({required this.privacyId, required this.termsId});
  final String privacyId;
  final String termsId;
}

class LegalRepository {
  static const pagesBaseUrl = String.fromEnvironment(
    'LEGAL_PAGES_BASE_URL',
    defaultValue: 'https://cms.enertechups.cloud',
  );

  static Uri pageUrl(String page) => Uri.parse('$pagesBaseUrl/$page');

  Future<LegalVersions> loadCurrent() async {
    final base = Uri.tryParse(CustomerProfileRepository.effectiveBaseUrl);
    if (base == null || !base.hasScheme || !base.hasAuthority) {
      throw const HttpException('The customer platform API is not configured.');
    }
    final root = base.path.endsWith('/') ? base : base.replace(path: '${base.path}/');
    final client = HttpClient()..connectionTimeout = const Duration(seconds: 5);
    try {
      final request = await client.getUrl(root.resolve('legal/current')).timeout(const Duration(seconds: 5));
      request.headers.set(HttpHeaders.acceptHeader, 'application/json');
      final response = await request.close().timeout(const Duration(seconds: 5));
      final body = await response.transform(utf8.decoder).join().timeout(const Duration(seconds: 5));
      if (response.statusCode != 200) {
        throw const HttpException('Privacy Policy and Terms are not published yet. Please try again later.');
      }
      final json = jsonDecode(body) as Map<String, dynamic>;
      final privacy = json['privacy_policy'] as Map<String, dynamic>;
      final terms = json['terms'] as Map<String, dynamic>;
      return LegalVersions(privacyId: privacy['id'] as String, termsId: terms['id'] as String);
    } finally {
      client.close(force: true);
    }
  }
}
