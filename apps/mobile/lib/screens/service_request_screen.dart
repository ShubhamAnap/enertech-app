import 'dart:io';

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
  final _formKey = GlobalKey<FormState>();
  final _model = TextEditingController();
  final _serial = TextEditingController();
  final _description = TextEditingController();
  final _location = TextEditingController();
  String? _issue;
  bool _working = false;
  String? _error;

  Future<void> _submit() async {
    FocusScope.of(context).unfocus();
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _working = true;
      _error = null;
    });
    try {
      final result = await CustomerRequestsRepository().submitService(
        model: _model.text.trim(),
        serial: _serial.text.trim().isEmpty ? null : _serial.text.trim(),
        category: _issue!,
        description: _description.text.trim(),
        location: _location.text.trim(),
      );
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Request submitted'),
          content: Text(
            'Your service request is recorded. Track it in My requests. Reference: ${result.id.substring(0, 8).toUpperCase()}',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Done'),
            ),
          ],
        ),
      );
      if (mounted) Navigator.pop(context);
    } on HttpException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } catch (_) {
      if (mounted) {
        setState(
          () => _error = 'Could not send the service request. Check your connection and try again.',
        );
      }
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

  @override
  void dispose() {
    _model.dispose();
    _serial.dispose();
    _description.dispose();
    _location.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('New service request')),
    body: SafeArea(
      child: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 28),
          children: [
            const Text(
              'Tell us about the equipment and issue.',
              style: TextStyle(color: AppColors.muted, fontSize: 13),
            ),
            const SizedBox(height: 16),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(15),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Equipment',
                      style: TextStyle(
                        color: AppColors.ink,
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 11),
                    TextFormField(
                      controller: _model,
                      textCapitalization: TextCapitalization.characters,
                      textInputAction: TextInputAction.next,
                      maxLength: 120,
                      validator: (value) => (value?.trim().isNotEmpty ?? false)
                          ? null
                          : 'Enter the product model.',
                      decoration: const InputDecoration(
                        labelText: 'Product model *',
                        hintText: 'Enter model name or number',
                      ),
                    ),
                    const SizedBox(height: 10),
                    TextFormField(
                      controller: _serial,
                      textCapitalization: TextCapitalization.characters,
                      textInputAction: TextInputAction.next,
                      maxLength: 120,
                      decoration: const InputDecoration(
                        labelText: 'Serial number (optional)',
                        hintText: 'Enter serial number if known',
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 10),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(15),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'What is happening?',
                      style: TextStyle(
                        color: AppColors.ink,
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 11),
                    DropdownButtonFormField<String>(
                      initialValue: _issue,
                      validator: (value) =>
                          value == null ? 'Choose the issue category.' : null,
                      decoration: const InputDecoration(
                        labelText: 'Issue category *',
                      ),
                      items: const [
                        DropdownMenuItem(
                          value: 'alarm',
                          child: Text('Alarm or fault'),
                        ),
                        DropdownMenuItem(
                          value: 'battery',
                          child: Text('Battery concern'),
                        ),
                        DropdownMenuItem(
                          value: 'performance',
                          child: Text('Performance issue'),
                        ),
                        DropdownMenuItem(
                          value: 'installation',
                          child: Text('Installation or maintenance'),
                        ),
                        DropdownMenuItem(value: 'other', child: Text('Other')),
                      ],
                      onChanged: _working
                          ? null
                          : (value) => setState(() => _issue = value),
                    ),
                    const SizedBox(height: 10),
                    TextFormField(
                      controller: _description,
                      minLines: 4,
                      maxLines: 6,
                      maxLength: 4000,
                      textCapitalization: TextCapitalization.sentences,
                      textInputAction: TextInputAction.next,
                      validator: (value) => (value?.trim().length ?? 0) >= 10
                          ? null
                          : 'Describe the issue in at least 10 characters.',
                      decoration: const InputDecoration(
                        alignLabelWithHint: true,
                        labelText: 'Describe the issue *',
                        hintText: 'What happened? When did it start?',
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 10),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(15),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Service location',
                      style: TextStyle(
                        color: AppColors.ink,
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 11),
                    TextFormField(
                      controller: _location,
                      textCapitalization: TextCapitalization.words,
                      textInputAction: TextInputAction.done,
                      maxLength: 500,
                      validator: (value) => (value?.trim().length ?? 0) >= 2
                          ? null
                          : 'Enter a city, state, or PIN code.',
                      decoration: const InputDecoration(
                        labelText: 'City, state, or PIN code *',
                      ),
                    ),
                    const SizedBox(height: 10),
                    OutlinedButton.icon(
                      onPressed: null,
                      icon: const Icon(Icons.add_photo_alternate_outlined),
                      label: const Text('Photo uploads not available'),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),
            const NoticeCard(
              message: 'Your request is sent to EnerTech when submitted. Photo uploads are not available yet. Do not include passwords, payment details, or unrelated personal information.',
            ),
            if (_error != null) ...[
              const SizedBox(height: 10),
              NoticeCard(message: _error!, icon: Icons.error_outline_rounded),
            ],
            const SizedBox(height: 15),
            FilledButton(
              onPressed: _working ? null : _submit,
              child: _working
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('Submit service request'),
            ),
          ],
        ),
      ),
    ),
  );
}

