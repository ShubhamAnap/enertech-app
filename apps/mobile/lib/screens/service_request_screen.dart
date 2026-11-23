import 'package:material_ui/material_ui.dart';

import '../data/customer_requests_repository.dart';
import '../theme/app_theme.dart';
import '../widgets/app_components.dart';

class ServiceRequestScreen extends StatefulWidget {
  const ServiceRequestScreen({super.key});

  @override
  State<ServiceRequestScreen> createState() => _ServiceRequestScreenState();
}

class _ServiceRequestScreenState extends State<ServiceRequestScreen> {
  final _model = TextEditingController();
  final _serial = TextEditingController();
  final _description = TextEditingController();
  final _location = TextEditingController();
  String? _issue;
  bool _working = false;
  String? _error;

  Future<void> _submit() async {
    if (_model.text.trim().isEmpty || _description.text.trim().length < 10 || _location.text.trim().isEmpty || _issue == null) {
      setState(() => _error = 'Add the product model, issue category, at least 10 characters about the issue, and service location.');
      return;
    }
    setState(() { _working = true; _error = null; });
    try {
      final result = await CustomerRequestsRepository().submitService(model: _model.text.trim(), serial: _serial.text.trim().isEmpty ? null : _serial.text.trim(), category: _issue!, description: _description.text.trim(), location: _location.text.trim());
      if (!mounted) return;
      await showDialog<void>(context: context, builder: (context) => AlertDialog(title: const Text('Request submitted'), content: Text('Your service request is recorded. You can track its status in My requests. Reference: ${result.id.substring(0, 8).toUpperCase()}'), actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Done'))]));
      if (mounted) Navigator.pop(context);
    } catch (error) {
      setState(() => _error = error.toString().replaceFirst('HttpException: ', ''));
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

  @override
  void dispose() { _model.dispose(); _serial.dispose(); _description.dispose(); _location.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('New service request')),
    body: ListView(padding: const EdgeInsets.fromLTRB(20, 8, 20, 28), children: [
      const Text('Tell us about the equipment and issue.', style: TextStyle(color: AppColors.muted, fontSize: 13)),
      const SizedBox(height: 16),
      Card(child: Padding(padding: const EdgeInsets.all(15), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Equipment', style: TextStyle(color: AppColors.ink, fontSize: 14, fontWeight: FontWeight.w700)),
        const SizedBox(height: 11),
        TextField(controller: _model, textCapitalization: TextCapitalization.characters, decoration: const InputDecoration(labelText: 'Product model', hintText: 'Enter model name or number')),
        const SizedBox(height: 10),
        TextField(controller: _serial, textCapitalization: TextCapitalization.characters, decoration: const InputDecoration(labelText: 'Serial number (optional)', hintText: 'Enter serial number if known')),
      ]))),
      const SizedBox(height: 10),
      Card(child: Padding(padding: const EdgeInsets.all(15), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('What is happening?', style: TextStyle(color: AppColors.ink, fontSize: 14, fontWeight: FontWeight.w700)),
        const SizedBox(height: 11),
        DropdownButtonFormField<String>(initialValue: _issue, decoration: const InputDecoration(labelText: 'Issue category'), items: const [DropdownMenuItem(value: 'alarm', child: Text('Alarm or fault')), DropdownMenuItem(value: 'battery', child: Text('Battery concern')), DropdownMenuItem(value: 'performance', child: Text('Performance issue')), DropdownMenuItem(value: 'installation', child: Text('Installation or maintenance')), DropdownMenuItem(value: 'other', child: Text('Other'))], onChanged: (value) => setState(() => _issue = value)),
        const SizedBox(height: 10),
        TextField(controller: _description, maxLines: 4, textCapitalization: TextCapitalization.sentences, decoration: const InputDecoration(alignLabelWithHint: true, labelText: 'Describe the issue', hintText: 'What happened? When did it start?')),
      ]))),
      const SizedBox(height: 10),
      Card(child: Padding(padding: const EdgeInsets.all(15), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Service location', style: TextStyle(color: AppColors.ink, fontSize: 14, fontWeight: FontWeight.w700)),
        const SizedBox(height: 11),
        TextField(controller: _location, textCapitalization: TextCapitalization.words, decoration: const InputDecoration(hintText: 'City, state, or PIN code')),
        const SizedBox(height: 10),
        OutlinedButton.icon(onPressed: null, icon: const Icon(Icons.add_photo_alternate_outlined), label: const Text('Add photos or video')),
      ]))),
      const SizedBox(height: 12),
      const NoticeCard(message: 'Request details are sent to EnerTech when you submit. Do not include passwords, payment details, or unrelated personal information. Photo uploads are not available yet.'),
      if (_error != null) ...[const SizedBox(height: 8), Text(_error!, style: const TextStyle(color: Color(0xFF9A3029), fontSize: 12))],
      const SizedBox(height: 15),
      FilledButton(onPressed: _working ? null : _submit, child: _working ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2)) : const Text('Submit service request')),
    ]),
  );
}
