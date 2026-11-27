import 'dart:convert';
import 'dart:io';

import 'package:firebase_auth/firebase_auth.dart';

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

  factory CustomerRequestRecord.fromJson(
    Map<String, dynamic> json,
  ) => CustomerRequestRecord(
    id: json['id'] as String? ?? 'req-${DateTime.now().millisecondsSinceEpoch}',
    kind: json['kind'] as String? ?? 'service',
    status: json['status'] as String? ?? 'submitted',
    payload: (json['payload'] as Map<String, dynamic>?) ?? const {},
    createdAt:
        DateTime.tryParse(json['created_at'] as String? ?? '') ??
        DateTime.now(),
    resolutionNote: json['resolution_note'] as String?,
  );
}

class CustomerRequestsRepository {
  CustomerRequestsRepository({String? baseUrl}) : _baseUrl = baseUrl;

  final String? _baseUrl;

  String get baseUrl => _baseUrl ?? CustomerProfileRepository.effectiveBaseUrl;

  Future<List<CustomerRequestRecord>> loadMine() async {
    final value = await _request('GET', '/requests');
    if (value is! List<dynamic>)
      throw const FormatException(
        'The request service returned an invalid response.',
      );
    return value
        .map(
          (row) => CustomerRequestRecord.fromJson(row as Map<String, dynamic>),
        )
        .toList(growable: false);
  }

  Future<String> uploadServicePhoto(File file) async {
    final user = FirebaseAuth.instance.currentUser;
    if (user == null) {
      throw const HttpException('Sign in before uploading photos.');
    }
    if (!user.emailVerified) {
      throw const HttpException('Verify your email before uploading photos.');
    }
    final base = Uri.tryParse(baseUrl);
    if (base == null || !base.hasScheme || !base.hasAuthority) {
      throw const HttpException('The customer platform API is not configured.');
    }
    final bytes = await file.readAsBytes();
    if (bytes.isEmpty || bytes.length > 10 * 1024 * 1024) {
      throw const HttpException('Choose a photo smaller than 10 MB.');
    }
    final root = base.path.endsWith('/')
        ? base
        : base.replace(path: '${base.path}/');
    final uri = root.resolve('requests/service/upload');
    final rawName = file.uri.pathSegments.isNotEmpty
        ? file.uri.pathSegments.last
        : 'photo.jpg';
    final safeName = rawName.replaceAll(RegExp(r'[^A-Za-z0-9._-]'), '_');
    final lower = safeName.toLowerCase();
    final contentType = lower.endsWith('.png')
        ? 'image/png'
        : lower.endsWith('.webp')
            ? 'image/webp'
            : 'image/jpeg';
    final boundary = 'enertechBoundary${DateTime.now().microsecondsSinceEpoch}';
    final header = utf8.encode(
      '--$boundary\r\n'
      'Content-Disposition: form-data; name="file"; filename="$safeName"\r\n'
      'Content-Type: $contentType\r\n\r\n',
    );
    final footer = utf8.encode('\r\n--$boundary--\r\n');
    final totalLength = header.length + bytes.length + footer.length;

    final client = HttpClient()..connectionTimeout = const Duration(seconds: 10);
    try {
      final request = await client
          .postUrl(uri)
          .timeout(const Duration(seconds: 15));
      request.headers.set(HttpHeaders.acceptHeader, 'application/json');
      request.headers.set(
        HttpHeaders.authorizationHeader,
        'Bearer ${await user.getIdToken()}',
      );
      request.headers.contentType = ContentType(
        'multipart',
        'form-data',
        parameters: {'boundary': boundary},
      );
      request.contentLength = totalLength;
      request.add(header);
      request.add(bytes);
      request.add(footer);
      final response = await request.close().timeout(
        const Duration(seconds: 30),
      );
      final text = await response
          .transform(utf8.decoder)
          .join()
          .timeout(const Duration(seconds: 15));
      final decoded = text.isEmpty ? null : jsonDecode(text);
      if (response.statusCode < 200 || response.statusCode >= 300) {
        final message = decoded is Map<String, dynamic>
            ? decoded['detail'] as String?
            : null;
        throw HttpException(
          message ?? 'Could not upload photo (${response.statusCode}).',
        );
      }
      final url = decoded is Map<String, dynamic>
          ? decoded['url'] as String?
          : null;
      if (url == null || !url.startsWith('https://')) {
        throw const HttpException('Upload did not return a valid photo URL.');
      }
      return url;
    } finally {
      client.close(force: true);
    }
  }

  Future<CustomerRequestRecord> submitService({
    required String model,
    required String category,
    required String description,
    required String location,
    String? serial,
    List<String> attachments = const [],
  }) async {
    final payload = {
      'product_model': model,
      'serial_number': serial,
      'problem_category': category,
      'description': description,
      'service_location': location,
      if (attachments.isNotEmpty) 'attachments': attachments,
    };
    final value = await _request('POST', '/requests/service', body: payload);
    return CustomerRequestRecord.fromJson(value as Map<String, dynamic>);
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
    final value = await _request('POST', '/requests/quote', body: payload);
    return CustomerRequestRecord.fromJson(value as Map<String, dynamic>);
  }

  Future<CustomerRequestRecord> submitWarranty({
    required String name,
    required String email,
    required String mobile,
    required String serial,
    required String purchaseDate,
  }) async {
    final value = await _request('POST', '/requests/warranty', body: {
      'customer_name': name,
      'email': email,
      'mobile_number': mobile,
      'serial_number': serial,
      'purchase_date': purchaseDate,
    });
    return CustomerRequestRecord.fromJson(value as Map<String, dynamic>);
  }

  Future<CustomerRequestRecord> submitAmc({
    required String serial,
    required String location,
    required String purchaseDate,
  }) async {
    final value = await _request('POST', '/requests/amc', body: {
      'serial_number': serial,
      'location': location,
      'purchase_date': purchaseDate,
    });
    return CustomerRequestRecord.fromJson(value as Map<String, dynamic>);
  }

  Future<void> submitContactInquiry({
    required String name,
    required String phone,
    required String message,
    required String inquiryType,
    String? companyName,
    String? subject,
  }) async {
    await _request(
      'POST',
      '/requests/contact-inquiry',
      body: {
        'name': name.trim(),
        'phone': phone.trim(),
        'company_name': companyName?.trim().isEmpty == true
            ? null
            : companyName?.trim(),
        'subject': subject?.trim().isEmpty == true ? null : subject?.trim(),
        'message': message.trim(),
        'inquiry_type': inquiryType,
      },
    );
  }

  Future<dynamic> _request(
    String method,
    String path, {
    Map<String, Object?>? body,
  }) async {
    final user = FirebaseAuth.instance.currentUser;
    if (user == null)
      throw const HttpException(
        'Sign in before submitting or tracking requests.',
      );
    if (!user.emailVerified)
      throw const HttpException(
        'Verify your email before submitting a request.',
      );
    final base = Uri.tryParse(baseUrl);
    if (base == null || !base.hasScheme || !base.hasAuthority) {
      throw const HttpException('The customer platform API is not configured.');
    }
    final root = base.path.endsWith('/')
        ? base
        : base.replace(path: '${base.path}/');
    final uri = root.resolve(path.startsWith('/') ? path.substring(1) : path);
    final client = HttpClient()..connectionTimeout = const Duration(seconds: 10);
    try {
      final request =
          await (method == 'POST' ? client.postUrl(uri) : client.getUrl(uri))
              .timeout(const Duration(seconds: 15));
      request.headers.set(HttpHeaders.acceptHeader, 'application/json');
      request.headers.set(
        HttpHeaders.authorizationHeader,
        'Bearer ${await user.getIdToken()}',
      );
      if (body != null) {
        request.headers.contentType = ContentType.json;
        request.write(jsonEncode(body));
      }
      final response = await request.close().timeout(
        const Duration(seconds: 15),
      );
      final text = await response
          .transform(utf8.decoder)
          .join()
          .timeout(const Duration(seconds: 15));
      final decoded = text.isEmpty ? null : jsonDecode(text);
      if (response.statusCode < 200 || response.statusCode >= 300) {
        final message = decoded is Map<String, dynamic>
            ? decoded['detail'] as String?
            : null;
        throw HttpException(
          message ??
              'The request could not be completed (${response.statusCode}).',
        );
      }
      return decoded;
    } finally {
      client.close(force: true);
    }
  }
}
