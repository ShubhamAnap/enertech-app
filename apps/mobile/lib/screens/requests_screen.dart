import 'dart:io';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:material_ui/material_ui.dart';

import '../data/customer_requests_repository.dart';
import '../theme/app_theme.dart';
import '../widgets/app_components.dart';
import 'solution_finder_screen.dart';

class RequestsScreen extends StatefulWidget {
  const RequestsScreen({super.key, required this.onNavigate});
  final ValueChanged<int> onNavigate;

  @override
  State<RequestsScreen> createState() => _RequestsScreenState();
}

class _RequestsScreenState extends State<RequestsScreen> {
  final _repository = CustomerRequestsRepository();
  late Future<List<CustomerRequestRecord>> _requests = _repository.loadMine();

  void _reload() => setState(() => _requests = _repository.loadMine());

  @override
  Widget build(BuildContext context) => ListView(padding: const EdgeInsets.fromLTRB(20, 22, 20, 28), children: [
    const Text('My requests', style: TextStyle(color: AppColors.ink, fontSize: 24, fontWeight: FontWeight.w800)),
    const SizedBox(height: 5),
    const Text('Enquiries, quotations, and service updates in one place.', style: TextStyle(color: AppColors.muted, fontSize: 13)),
    const SizedBox(height: 18),
    FutureBuilder<List<CustomerRequestRecord>>(future: _requests, builder: (context, snapshot) {
      if (FirebaseAuth.instance.currentUser == null) return Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(children: [const NoticeCard(message: 'Sign in to view your requests and updates.'), const SizedBox(height: 8), TextButton(onPressed: () => widget.onNavigate(4), child: const Text('Go to account'))])));
      if (snapshot.connectionState == ConnectionState.waiting) return const Center(child: Padding(padding: EdgeInsets.all(24), child: CircularProgressIndicator()));
      if (snapshot.hasError) return EmptyState(icon: Icons.wifi_off_rounded, title: 'Requests unavailable', message: snapshot.error is HttpException ? (snapshot.error as HttpException).message : 'Could not load your requests. Check your connection and try again.', actionLabel: 'Retry', onAction: _reload);
      final rows = snapshot.data ?? const <CustomerRequestRecord>[];
      if (rows.isEmpty) return Card(child: EmptyState(icon: Icons.inbox_outlined, title: 'No requests yet', message: 'Start a guided enquiry or service request. Your updates will appear here.', actionLabel: 'Find a solution', onAction: () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const SolutionFinderScreen()))));
      return Column(children: [for (final request in rows) Padding(padding: const EdgeInsets.only(bottom: 10), child: Card(child: Padding(padding: const EdgeInsets.all(15), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [Expanded(child: Text(request.kind == 'service' ? 'Service request' : 'Quote enquiry', style: const TextStyle(color: AppColors.ink, fontWeight: FontWeight.w700))), Container(padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5), decoration: BoxDecoration(color: const Color(0xFFEAF3FA), borderRadius: BorderRadius.circular(20)), child: Text(_status(request.status), style: const TextStyle(color: AppColors.blue, fontSize: 10, fontWeight: FontWeight.w700)))]),
        const SizedBox(height: 8),
        Text(_summary(request), style: const TextStyle(color: AppColors.muted, fontSize: 12)),
        if (request.resolutionNote?.isNotEmpty == true) ...[const SizedBox(height: 8), Text(request.resolutionNote!, style: const TextStyle(color: AppColors.ink, fontSize: 12))],
        const SizedBox(height: 8),
        Text(request.createdAt.toLocal().toString().split('.').first, style: const TextStyle(color: AppColors.muted, fontSize: 10)),
      ]))))]);
    }),
    const SizedBox(height: 8),
    OutlinedButton.icon(onPressed: _reload, icon: const Icon(Icons.refresh_rounded), label: const Text('Refresh requests')),
  ]);

  String _status(String value) => value.replaceAll('_', ' ').split(' ').map((word) => word.isEmpty ? word : '${word[0].toUpperCase()}${word.substring(1)}').join(' ');
  String _summary(CustomerRequestRecord request) => request.kind == 'service' ? '${request.payload['product_model'] ?? 'Equipment'} · ${request.payload['problem_category'] ?? 'Issue'}' : '${request.payload['application'] ?? 'Application'} · Qty ${request.payload['quantity'] ?? 1}';
}
