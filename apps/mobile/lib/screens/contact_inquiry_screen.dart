import 'dart:io';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:material_ui/material_ui.dart';

import '../data/customer_profile_repository.dart';
import '../data/customer_requests_repository.dart';
import '../theme/app_theme.dart';
import '../widgets/app_components.dart';

class ContactInquiryScreen extends StatefulWidget {
  const ContactInquiryScreen({super.key});

  @override
  State<ContactInquiryScreen> createState() => _ContactInquiryScreenState();
}

class _ContactInquiryScreenState extends State<ContactInquiryScreen> {
  final _formKey = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _email = TextEditingController();
  final _phone = TextEditingController();
  final _company = TextEditingController();
  final _subject = TextEditingController();
  final _message = TextEditingController();
  final _requests = CustomerRequestsRepository();
  String _inquiryType = 'general';
  bool _sending = false;
  bool _sent = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    final user = FirebaseAuth.instance.currentUser;
    _name.text = user?.displayName ?? '';
    _email.text = user?.email ?? '';
    _loadProfile();
  }

  Future<void> _loadProfile() async {
    try {
      final profile = await CustomerProfileRepository().loadMine();
      if (!mounted || profile == null) return;
      if (_name.text.trim().isEmpty) _name.text = profile.name;
      if (_phone.text.trim().isEmpty) _phone.text = profile.mobileNumber;
      if (_company.text.trim().isEmpty)
        _company.text = profile.companyName ?? '';
    } catch (_) {
      // The form remains usable when the profile cache/API is unavailable.
    }
  }

  @override
  void dispose() {
    _name.dispose();
    _email.dispose();
    _phone.dispose();
    _company.dispose();
    _subject.dispose();
    _message.dispose();
    super.dispose();
  }

  String? _validatePhone(String? value) {
    final clean = value?.trim() ?? '';
    final digits = clean.replaceAll(RegExp(r'[^0-9]'), '');
    if (!RegExp(r'^\+?[0-9()\-\s]+$').hasMatch(clean) ||
        digits.length < 10 ||
        digits.length > 15) {
      return 'Enter 10–15 digits with an optional country code.';
    }
    return null;
  }

  Future<void> _submit() async {
    FocusScope.of(context).unfocus();
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _sending = true;
      _error = null;
    });
    try {
      await _requests.submitContactInquiry(
        name: _name.text,
        phone: _phone.text,
        companyName: _company.text,
        subject: _subject.text,
        message: _message.text,
        inquiryType: _inquiryType,
      );
      if (mounted) setState(() => _sent = true);
    } on HttpException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } catch (_) {
      if (mounted)
        setState(
          () => _error = 'We could not send your message. Check your connection and try again.',
        );
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = FirebaseAuth.instance.currentUser;
    if (user == null || !user.emailVerified) {
      return const Scaffold(
        body: SafeArea(
          child: Center(
            child: Padding(
              padding: EdgeInsets.all(24),
              child: Text(
                'Sign in and verify your email before sending an enquiry.',
                textAlign: TextAlign.center,
              ),
            ),
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(title: const Text('Contact EnerTech')),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 560),
            child: _sent
                ? Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(
                          Icons.check_circle_outline_rounded,
                          size: 48,
                          color: AppColors.blue,
                        ),
                        const SizedBox(height: 12),
                        const Text(
                          'Your enquiry was sent',
                          style: TextStyle(
                            fontSize: 21,
                            fontWeight: FontWeight.w800,
                            color: AppColors.ink,
                          ),
                        ),
                        const SizedBox(height: 8),
                        const Text(
                          'The EnerTech team will follow up using your verified email and phone number.',
                          textAlign: TextAlign.center,
                          style: TextStyle(color: AppColors.muted),
                        ),
                        const SizedBox(height: 18),
                        FilledButton(
                          onPressed: () => Navigator.of(context).pop(),
                          child: const Text('Back to support'),
                        ),
                      ],
                    ),
                  )
                : Form(
                    key: _formKey,
                    child: ListView(
                      padding: const EdgeInsets.fromLTRB(20, 18, 20, 28),
                      children: [
                        const Text(
                          'Send us a message',
                          style: TextStyle(
                            fontSize: 23,
                            fontWeight: FontWeight.w800,
                            color: AppColors.ink,
                          ),
                        ),
                        const SizedBox(height: 6),
                        const Text(
                          'Your verified account email is used for the reply. Include only details needed to help with this enquiry.',
                          style: TextStyle(
                            fontSize: 13,
                            height: 1.4,
                            color: AppColors.muted,
                          ),
                        ),
                        const SizedBox(height: 18),
                        TextFormField(
                          controller: _name,
                          textCapitalization: TextCapitalization.words,
                          textInputAction: TextInputAction.next,
                          validator: (value) => (value?.trim().length ?? 0) >= 2
                              ? null
                              : 'Enter your name.',
                          decoration: const InputDecoration(
                            labelText: 'Full name *',
                            prefixIcon: Icon(Icons.person_outline_rounded),
                          ),
                        ),
                        const SizedBox(height: 12),
                        TextFormField(
                          controller: _email,
                          readOnly: true,
                          decoration: const InputDecoration(
                            labelText: 'Verified email',
                            helperText:
                                'This address is linked to your sign-in.',
                            prefixIcon: Icon(Icons.verified_user_outlined),
                          ),
                        ),
                        const SizedBox(height: 12),
                        TextFormField(
                          controller: _phone,
                          keyboardType: TextInputType.phone,
                          textInputAction: TextInputAction.next,
                          validator: _validatePhone,
                          decoration: const InputDecoration(
                            labelText: 'Phone number *',
                            prefixIcon: Icon(Icons.phone_outlined),
                          ),
                        ),
                        const SizedBox(height: 12),
                        DropdownButtonFormField<String>(
                          initialValue: _inquiryType,
                          decoration: const InputDecoration(
                            labelText: 'What is this about? *',
                            prefixIcon: Icon(Icons.topic_outlined),
                          ),
                          items: const [
                            DropdownMenuItem(
                              value: 'general',
                              child: Text('General enquiry'),
                            ),
                            DropdownMenuItem(
                              value: 'sales',
                              child: Text('Sales or product enquiry'),
                            ),
                            DropdownMenuItem(
                              value: 'product',
                              child: Text('Product information'),
                            ),
                            DropdownMenuItem(
                              value: 'service',
                              child: Text('Service support'),
                            ),
                          ],
                          onChanged: _sending
                              ? null
                              : (value) {
                                  if (value != null)
                                    setState(() => _inquiryType = value);
                                },
                        ),
                        const SizedBox(height: 12),
                        TextFormField(
                          controller: _company,
                          textCapitalization: TextCapitalization.words,
                          textInputAction: TextInputAction.next,
                          decoration: const InputDecoration(
                            labelText: 'Company (optional)',
                            prefixIcon: Icon(Icons.business_outlined),
                          ),
                        ),
                        const SizedBox(height: 12),
                        TextFormField(
                          controller: _subject,
                          textInputAction: TextInputAction.next,
                          maxLength: 220,
                          decoration: const InputDecoration(
                            labelText: 'Subject (optional)',
                            prefixIcon: Icon(Icons.short_text_rounded),
                          ),
                        ),
                        const SizedBox(height: 4),
                        TextFormField(
                          controller: _message,
                          minLines: 4,
                          maxLines: 7,
                          maxLength: 10000,
                          textCapitalization: TextCapitalization.sentences,
                          validator: (value) =>
                              (value?.trim().length ?? 0) >= 5 ? null : 'Add a few details so we can route your enquiry.',
                          decoration: const InputDecoration(
                            labelText: 'Message *',
                            alignLabelWithHint: true,
                            prefixIcon: Icon(Icons.message_outlined),
                          ),
                        ),
                        if (_error != null) ...[
                          const SizedBox(height: 10),
                          NoticeCard(
                            message: _error!,
                            icon: Icons.error_outline_rounded,
                          ),
                        ],
                        const SizedBox(height: 14),
                        FilledButton.icon(
                          onPressed: _sending ? null : _submit,
                          icon: _sending
                              ? const SizedBox(
                                  width: 18,
                                  height: 18,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                    color: Colors.white,
                                  ),
                                )
                              : const Icon(Icons.send_rounded),
                          label: Text(_sending ? 'Sending…' : 'Send enquiry'),
                        ),
                      ],
                    ),
                  ),
          ),
        ),
      ),
    );
  }
}
