import 'dart:io';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:material_ui/material_ui.dart';

import '../data/customer_requests_repository.dart';
import '../theme/app_theme.dart';

class WarrantyAmcScreen extends StatelessWidget {
  const WarrantyAmcScreen({super.key});

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Warranty & AMC')),
    body: ListView(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 28),
      children: [
        const Text(
          'How can we help with your product?',
          style: TextStyle(color: AppColors.muted, fontSize: 13),
        ),
        const SizedBox(height: 16),
        _Choice(
          icon: Icons.verified_outlined,
          title: 'Register warranty',
          subtitle: 'Send your purchase and product details for review',
          onTap: () => Navigator.push(
            context,
            MaterialPageRoute<void>(
              builder: (_) => const _RequestForm(isWarranty: true),
            ),
          ),
        ),
        const SizedBox(height: 10),
        _Choice(
          icon: Icons.handyman_outlined,
          title: 'AMC',
          subtitle: 'Request an annual maintenance contract',
          onTap: () => Navigator.push(
            context,
            MaterialPageRoute<void>(
              builder: (_) => const _RequestForm(isWarranty: false),
            ),
          ),
        ),
      ],
    ),
  );
}

class _Choice extends StatelessWidget {
  const _Choice({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Card(
    child: ListTile(
      contentPadding: const EdgeInsets.all(14),
      leading: Icon(icon, color: AppColors.blue),
      title: Text(
        title,
        style: const TextStyle(
          color: AppColors.ink,
          fontWeight: FontWeight.w700,
          fontSize: 14,
        ),
      ),
      subtitle: Text(
        subtitle,
        style: const TextStyle(color: AppColors.muted, fontSize: 11),
      ),
      trailing: const Icon(Icons.chevron_right_rounded, color: AppColors.muted),
      onTap: onTap,
    ),
  );
}

class _RequestForm extends StatefulWidget {
  const _RequestForm({required this.isWarranty});
  final bool isWarranty;

  @override
  State<_RequestForm> createState() => _RequestFormState();
}

class _RequestFormState extends State<_RequestForm> {
  final _formKey = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _email = TextEditingController();
  final _mobile = TextEditingController();
  final _serial = TextEditingController();
  final _location = TextEditingController();
  DateTime? _purchaseDate;
  bool _working = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _email.text = FirebaseAuth.instance.currentUser?.email ?? '';
  }

  @override
  void dispose() {
    for (final controller in [_name, _email, _mobile, _serial, _location]) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> _chooseDate() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _purchaseDate ?? now,
      firstDate: DateTime(1980),
      lastDate: now,
    );
    if (picked != null && mounted) setState(() => _purchaseDate = picked);
  }

  Future<void> _submit() async {
    FocusScope.of(context).unfocus();
    if (!_formKey.currentState!.validate()) return;
    if (_purchaseDate == null) {
      setState(() => _error = 'Choose the date of purchase.');
      return;
    }
    setState(() {
      _working = true;
      _error = null;
    });
    try {
      final date =
          '${_purchaseDate!.year.toString().padLeft(4, '0')}-'
          '${_purchaseDate!.month.toString().padLeft(2, '0')}-'
          '${_purchaseDate!.day.toString().padLeft(2, '0')}';
      final repo = CustomerRequestsRepository();
      final result = widget.isWarranty
          ? await repo.submitWarranty(
              name: _name.text.trim(),
              email: _email.text.trim(),
              mobile: _mobile.text.trim(),
              serial: _serial.text.trim(),
              purchaseDate: date,
            )
          : await repo.submitAmc(
              serial: _serial.text.trim(),
              location: _location.text.trim(),
              purchaseDate: date,
            );
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: const Text('Request submitted'),
          content: Text(
            'Your ${widget.isWarranty ? 'warranty registration' : 'AMC request'} '
            'is recorded for review. Track it in My requests. '
            'Reference: ${result.id.substring(0, 8).toUpperCase()}',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('Done'),
            ),
          ],
        ),
      );
      if (mounted) Navigator.pop(context);
    } on HttpException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } catch (_) {
      if (mounted)
        setState(
          () => _error = 'Could not submit the request. Check your connection and try again.',
        );
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

  String? _required(String? value) =>
      value?.trim().isNotEmpty == true ? null : 'This field is required.';

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(widget.isWarranty ? 'Register warranty' : 'AMC request'),
    ),
    body: SafeArea(
      child: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 28),
          children: [
            Text(
              widget.isWarranty
                  ? 'Share your purchase details for warranty review.'
                  : 'Share your product details for AMC review.',
              style: const TextStyle(color: AppColors.muted, fontSize: 13),
            ),
            const SizedBox(height: 16),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(15),
                child: Column(
                  children: [
                    if (widget.isWarranty) ...[
                      TextFormField(
                        controller: _name,
                        maxLength: 180,
                        textCapitalization: TextCapitalization.words,
                        validator: _required,
                        decoration: const InputDecoration(
                          labelText: 'Customer name *',
                        ),
                      ),
                      const SizedBox(height: 10),
                      TextFormField(
                        controller: _email,
                        readOnly: true,
                        validator: (value) => value?.contains('@') == true
                            ? null
                            : 'Sign in with a verified email address.',
                        decoration: const InputDecoration(labelText: 'Email *'),
                      ),
                      const SizedBox(height: 10),
                      TextFormField(
                        controller: _mobile,
                        maxLength: 30,
                        keyboardType: TextInputType.phone,
                        validator: (value) =>
                            RegExp(r'^\+?[0-9\s()-]{7,30}$')
                                .hasMatch(value?.trim() ?? '')
                            ? null
                            : 'Enter a valid mobile number.',
                        decoration: const InputDecoration(
                          labelText: 'Mobile number *',
                        ),
                      ),
                      const SizedBox(height: 10),
                    ],
                    TextFormField(
                      controller: _serial,
                      maxLength: 120,
                      textCapitalization: TextCapitalization.characters,
                      validator: _required,
                      decoration: const InputDecoration(
                        labelText: 'Product serial number *',
                      ),
                    ),
                    if (!widget.isWarranty) ...[
                      const SizedBox(height: 10),
                      TextFormField(
                        controller: _location,
                        maxLength: 500,
                        textCapitalization: TextCapitalization.words,
                        validator: _required,
                        decoration: const InputDecoration(
                          labelText: 'Location *',
                        ),
                      ),
                    ],
                    const SizedBox(height: 10),
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      title: const Text('Date of purchase *'),
                      subtitle: Text(
                        _purchaseDate == null
                            ? 'Choose date'
                            : '${_purchaseDate!.day}/${_purchaseDate!.month}/${_purchaseDate!.year}',
                      ),
                      trailing: const Icon(Icons.calendar_today_outlined),
                      onTap: _working ? null : _chooseDate,
                    ),
                  ],
                ),
              ),
            ),
            if (_error != null) ...[
              const SizedBox(height: 10),
              Text(_error!, style: const TextStyle(color: Colors.red)),
            ],
            const SizedBox(height: 16),
            FilledButton(
              onPressed: _working ? null : _submit,
              child: Text(_working ? 'Submitting…' : 'Submit request'),
            ),
          ],
        ),
      ),
    ),
  );
}
