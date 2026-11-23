import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_dotenv/flutter_dotenv.dart';

class AppContentRepository {
  AppContentRepository({String? baseUrl}) : _baseUrl = baseUrl ?? (const String.fromEnvironment('API_BASE_URL').isNotEmpty ? const String.fromEnvironment('API_BASE_URL') : ((dotenv.isInitialized ? dotenv.env['API_BASE_URL'] : null) ?? 'http://10.0.2.2:8000/api/v1'));
  final String _baseUrl;

  Future<List<Map<String, dynamic>>> loadPublishedKnowledge() async {
    if (_baseUrl.trim().isEmpty) return const [];
    final base = Uri.tryParse(_baseUrl);
    if (base == null || !base.hasScheme || !base.hasAuthority) return const [];
    final root = base.path.endsWith('/') ? base : base.replace(path: '${base.path}/');
    final client = HttpClient()..connectionTimeout = const Duration(seconds: 6);
    try {
      final request = await client.getUrl(root.resolve('knowledge')).timeout(const Duration(seconds: 8));
      request.headers.set(HttpHeaders.acceptHeader, 'application/json');
      final response = await request.close().timeout(const Duration(seconds: 8));
      if (response.statusCode < 200 || response.statusCode >= 300) return const [];
      final value = jsonDecode(await response.transform(utf8.decoder).join().timeout(const Duration(seconds: 8)));
      return value is List ? value.whereType<Map<String, dynamic>>().toList(growable: false) : const [];
    } on SocketException {
      return const [];
    } on TimeoutException {
      return const [];
    } on FormatException {
      return const [];
    } finally {
      client.close(force: true);
    }
  }

  Future<Map<String, dynamic>> loadPublished() async {
    if (_baseUrl.trim().isEmpty) return const {};
    final base = Uri.tryParse(_baseUrl);
    if (base == null || !base.hasScheme || !base.hasAuthority) return const {};
    final root = base.path.endsWith('/') ? base : base.replace(path: '${base.path}/');
    final uri = root.resolve('app/config');
    final client = HttpClient()..connectionTimeout = const Duration(seconds: 6);
    try {
      final request = await client.getUrl(uri).timeout(const Duration(seconds: 8));
      request.headers.set(HttpHeaders.acceptHeader, 'application/json');
      final response = await request.close().timeout(const Duration(seconds: 8));
      if (response.statusCode < 200 || response.statusCode >= 300) return const {};
      final value = jsonDecode(await response.transform(utf8.decoder).join().timeout(const Duration(seconds: 8)));
      return value is Map<String, dynamic> ? value : const {};
    } on SocketException {
      return const {};
    } on TimeoutException {
      return const {};
    } on FormatException {
      return const {};
    } finally {
      client.close(force: true);
    }
  }
}
