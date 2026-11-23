import 'dart:io';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

import '../data/customer_auth_service.dart';
import '../data/customer_profile_repository.dart';
import '../theme/app_theme.dart';
import 'app_shell.dart';

class CustomerEntryGate extends StatefulWidget {
  const CustomerEntryGate({super.key});

  @override
  State<CustomerEntryGate> createState() => _CustomerEntryGateState();
}

class _CustomerEntryGateState extends State<CustomerEntryGate> {
  final _profiles = CustomerProfileRepository();

  @override
  Widget build(BuildContext context) {
    if (Firebase.apps.isEmpty) return const AppShell();
    return StreamBuilder<User?>(
      stream: FirebaseAuth.instance.userChanges(),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting && !snapshot.hasData) {
          return const _LoadingPage();
        }
        final user = snapshot.data;
        if (user == null) return const _CustomerAuthPage();

        return FutureBuilder<CustomerProfile?>(
          key: ValueKey('${user.uid}_${CustomerProfileRepository.isOfflineBypass}'),
          future: _profiles.loadMine(userUid: user.uid),
          builder: (context, profileSnapshot) {
            if (profileSnapshot.connectionState != ConnectionState.done) {
              return const _LoadingPage();
            }

            final profile = profileSnapshot.data;
            // When user has not completed onboarding, ALWAYS show role selection!
            if (profile == null && !CustomerProfileRepository.isOfflineBypass) {
              return _CustomerOnboardingPage(
                user: user,
                onSaved: () => setState(() {}),
              );
            }

            return const AppShell();
          },
        );
      },
    );
  }
}

class _CustomerAuthPage extends StatefulWidget {
  const _CustomerAuthPage();

  @override
  State<_CustomerAuthPage> createState() => _CustomerAuthPageState();
}

class _CustomerAuthPageState extends State<_CustomerAuthPage> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _auth = CustomerAuthService();
  bool _creating = false;
  bool _busy = false;
  String? _error;
  String? _notice;
  bool _showShaNotice = false;

  static const String _debugSha1 = 'AB:EC:76:CC:32:C8:0B:A6:77:B0:AB:C2:FC:04:1F:17:AF:A7:F5:85';

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _emailAuth() async {
    FocusScope.of(context).unfocus();
    final emailText = _email.text.trim();
    final passwordText = _password.text;

    if (emailText.isEmpty || !emailText.contains('@')) {
      setState(() => _error = 'Enter a valid email address.');
      return;
    }
    if (passwordText.length < 6) {
      setState(() => _error = 'Password must be at least 6 characters.');
      return;
    }

    setState(() {
      _busy = true;
      _error = null;
      _notice = null;
      _showShaNotice = false;
    });
    try {
      final auth = FirebaseAuth.instance;
      if (_creating) {
        final result = await auth.createUserWithEmailAndPassword(
          email: emailText,
          password: passwordText,
        );
        // Non-blocking email verification dispatch
        try {
          await result.user?.sendEmailVerification();
        } catch (_) {}
      } else {
        await auth.signInWithEmailAndPassword(
          email: emailText,
          password: passwordText,
        );
      }
    } on FirebaseAuthException catch (error) {
      if (mounted) setState(() => _error = _authMessage(error));
    } catch (_) {
      if (mounted) {
        setState(
          () => _error = 'Could not connect. Check your network and try again.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _googleAuth() async {
    setState(() {
      _busy = true;
      _error = null;
      _notice = null;
      _showShaNotice = false;
    });
    try {
      final result = await _auth.signInWithGoogle();
      if (result == null && mounted) {
        setState(() => _busy = false);
        return;
      }
    } on FirebaseAuthException catch (error) {
      if (mounted) {
        final msg = error.message?.toLowerCase() ?? '';
        final isHashError = error.code == '10' ||
            error.code == 'developer-error' ||
            msg.contains('certificate') ||
            msg.contains('hash') ||
            msg.contains('fingerprint');
        setState(() {
          _error = _authMessage(error);
          _showShaNotice = isHashError;
        });
      }
    } catch (e) {
      if (mounted) {
        final errStr = e.toString().toLowerCase();
        final isHashError = errStr.contains('10') ||
            errStr.contains('certificate') ||
            errStr.contains('hash') ||
            errStr.contains('sign_in_failed');
        setState(() {
          _error = isHashError
              ? 'Google Sign-In needs this app’s SHA-1 certificate fingerprint registered in Firebase Console.'
              : 'Google sign-in could not be completed ($e). Please use Email or Demo Sign-In below.';
          _showShaNotice = isHashError;
        });
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _quickDemoAuth() async {
    setState(() {
      _busy = true;
      _error = null;
      _notice = null;
      _showShaNotice = false;
    });
    try {
      final auth = FirebaseAuth.instance;
      const demoEmail = 'demo.customer@enertechups.com';
      const demoPassword = 'DemoCustomer2026!';
      try {
        await auth.signInWithEmailAndPassword(email: demoEmail, password: demoPassword);
      } on FirebaseAuthException catch (e) {
        if (e.code == 'user-not-found' || e.code == 'invalid-credential') {
          await auth.createUserWithEmailAndPassword(email: demoEmail, password: demoPassword);
        } else {
          rethrow;
        }
      }
    } catch (e) {
      if (mounted) {
        // Fallback: continue in offline bypass mode
        CustomerProfileRepository.setOfflineBypass(true);
        setState(() {});
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _resetPassword() async {
    if (_email.text.trim().isEmpty) {
      setState(() => _error = 'Enter your email address first.');
      return;
    }
    try {
      await FirebaseAuth.instance.sendPasswordResetEmail(
        email: _email.text.trim(),
      );
      if (mounted) {
        setState(() {
          _error = null;
          _notice = 'Password reset instructions have been sent to your email.';
        });
      }
    } on FirebaseAuthException catch (error) {
      if (mounted) setState(() => _error = _authMessage(error));
    }
  }

  void _copySha1() {
    Clipboard.setData(const ClipboardData(text: _debugSha1));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('SHA-1 fingerprint copied to clipboard! Paste it in Firebase Console -> Project Settings -> General -> Your Android App.'),
        duration: Duration(seconds: 4),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(22),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 460),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const _BrandMark(),
                const SizedBox(height: 24),
                Text(
                  _creating ? 'Create your account' : 'Welcome to EnerTech',
                  style: const TextStyle(
                    fontSize: 26,
                    fontWeight: FontWeight.w800,
                    color: AppColors.ink,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  _creating
                      ? 'Get product support, specifications, and quotes tailored for you.'
                      : 'Sign in to explore power solutions and manage requests.',
                  style: const TextStyle(fontSize: 14, color: AppColors.muted),
                ),
                const SizedBox(height: 20),

                // Google Sign In
                OutlinedButton.icon(
                  onPressed: _busy ? null : _googleAuth,
                  icon: const Icon(Icons.g_mobiledata_rounded, size: 28),
                  label: const Text('Continue with Google'),
                ),

                // SHA-1 Notice if certificate check failed
                if (_showShaNotice) ...[
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: const Color(0xFFFFF7ED),
                      border: Border.all(color: const Color(0xFFFDBA74)),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Row(
                          children: [
                            Icon(Icons.info_outline, color: Color(0xFFC2410C), size: 18),
                            SizedBox(width: 6),
                            Text(
                              'Firebase SHA-1 Setup Required',
                              style: TextStyle(
                                fontWeight: FontWeight.w700,
                                color: Color(0xFF9A3412),
                                fontSize: 13,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 6),
                        const Text(
                          'Google Sign-In requires this SHA-1 fingerprint in Firebase Console under your Android App:',
                          style: TextStyle(fontSize: 12, color: Color(0xFF7C2D12)),
                        ),
                        const SizedBox(height: 6),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                          decoration: BoxDecoration(
                            color: Colors.white,
                            borderRadius: BorderRadius.circular(6),
                            border: Border.all(color: const Color(0xFFFED7AA)),
                          ),
                          child: const SelectableText(
                            _debugSha1,
                            style: TextStyle(fontFamily: 'monospace', fontSize: 11, fontWeight: FontWeight.bold),
                          ),
                        ),
                        const SizedBox(height: 8),
                        Row(
                          children: [
                            TextButton.icon(
                              onPressed: _copySha1,
                              icon: const Icon(Icons.copy_rounded, size: 14),
                              label: const Text('Copy SHA-1', style: TextStyle(fontSize: 12)),
                            ),
                            const Spacer(),
                            TextButton(
                              onPressed: () => setState(() => _showShaNotice = false),
                              child: const Text('Dismiss', style: TextStyle(fontSize: 12)),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ],

                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 14),
                  child: Row(
                    children: [
                      Expanded(child: Divider()),
                      Padding(
                        padding: EdgeInsets.symmetric(horizontal: 12),
                        child: Text(
                          'OR',
                          style: TextStyle(fontSize: 11, color: AppColors.muted),
                        ),
                      ),
                      Expanded(child: Divider()),
                    ],
                  ),
                ),

                // Email & Password
                TextField(
                  controller: _email,
                  keyboardType: TextInputType.emailAddress,
                  autofillHints: const [AutofillHints.email],
                  decoration: const InputDecoration(
                    labelText: 'Email address',
                    prefixIcon: Icon(Icons.mail_outline_rounded),
                  ),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: _password,
                  obscureText: true,
                  autofillHints: [
                    _creating ? AutofillHints.newPassword : AutofillHints.password,
                  ],
                  decoration: const InputDecoration(
                    labelText: 'Password',
                    prefixIcon: Icon(Icons.lock_outline_rounded),
                  ),
                ),

                if (_error != null) _InlineMessage(text: _error!, error: true),
                if (_notice != null) _InlineMessage(text: _notice!, error: false),

                const SizedBox(height: 16),
                FilledButton(
                  onPressed: _busy ? null : _emailAuth,
                  child: _busy
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                        )
                      : Text(_creating ? 'Create account' : 'Sign in'),
                ),

                if (!_creating)
                  Align(
                    alignment: Alignment.centerRight,
                    child: TextButton(
                      onPressed: _busy ? null : _resetPassword,
                      child: const Text('Forgot password?'),
                    ),
                  ),

                TextButton(
                  onPressed: _busy
                      ? null
                      : () => setState(() {
                          _creating = !_creating;
                          _error = null;
                          _notice = null;
                          _showShaNotice = false;
                        }),
                  child: Text(
                    _creating
                        ? 'Already have an account?  Sign in'
                        : 'New to EnerTech?  Create an account',
                  ),
                ),

                const SizedBox(height: 10),
                const Divider(),
                const SizedBox(height: 6),

                // Quick Demo Sign In
                OutlinedButton.icon(
                  onPressed: _busy ? null : _quickDemoAuth,
                  icon: const Icon(Icons.explore_outlined, size: 20),
                  label: const Text('Quick Demo Login / Test App'),
                ),
              ],
            ),
          ),
        ),
      ),
    ),
  );
}

class _CustomerOnboardingPage extends StatefulWidget {
  const _CustomerOnboardingPage({required this.user, required this.onSaved});
  final User user;
  final VoidCallback onSaved;

  @override
  State<_CustomerOnboardingPage> createState() => _CustomerOnboardingPageState();
}

class _CustomerOnboardingPageState extends State<_CustomerOnboardingPage> {
  final _formKey = GlobalKey<FormState>();
  final _company = TextEditingController();
  final _name = TextEditingController();
  final _mobile = TextEditingController();
  final _location = TextEditingController();
  final _gst = TextEditingController();
  final _profiles = CustomerProfileRepository();

  // Role choices: 'end_user', 'reseller', 'epc', 'distributor'
  String _type = 'end_user';
  bool _busy = false;
  String? _error;

  bool get _isBusiness => _type != 'end_user';

  @override
  void initState() {
    super.initState();
    _name.text = widget.user.displayName ?? '';
  }

  @override
  void dispose() {
    _company.dispose();
    _name.dispose();
    _mobile.dispose();
    _location.dispose();
    _gst.dispose();
    super.dispose();
  }

  String? _required(String? value, String label, {int minLength = 2}) {
    final clean = value?.trim() ?? '';
    if (clean.isEmpty) return 'Enter your $label.';
    if (clean.length < minLength) {
      return '$label must have at least $minLength characters.';
    }
    return null;
  }

  String? _validateGst(String? value) {
    if (!_isBusiness) return null;
    final clean = value?.trim().toUpperCase() ?? '';
    if (clean.isEmpty) return 'Enter your business GST number.';
    if (clean.length < 10) return 'GST number must be at least 10 characters.';
    // Standard Indian GSTIN pattern: 2 digits + 10 alphanumeric PAN + 1 digit/letter + Z + 1 check digit
    final gstRegex = RegExp(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$');
    if (clean.length == 15 && !gstRegex.hasMatch(clean)) {
      return 'Enter a valid 15-character GSTIN format (e.g. 27AAAAA0000A1Z5).';
    }
    return null;
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await _profiles.save(
        {
          'customer_type': _type,
          'name': _name.text.trim(),
          'mobile_number': _mobile.text.trim(),
          'email': widget.user.email?.trim().toLowerCase() ?? '',
          'location': _location.text.trim(),
          'company_name': _isBusiness ? _company.text.trim() : null,
          'gst_number': _isBusiness ? _gst.text.trim().toUpperCase() : null,
        },
        userUid: widget.user.uid,
      );
      widget.onSaved();
    } on HttpException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } catch (_) {
      // Local save is already complete inside _profiles.save()
      widget.onSaved();
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 520),
            child: Form(
              key: _formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const _BrandMark(),
                  const SizedBox(height: 22),
                  const Text(
                    'Complete Your Profile',
                    style: TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.w800,
                      color: AppColors.ink,
                    ),
                  ),
                  const SizedBox(height: 6),
                  const Text(
                    'Choose your account type so we can display relevant pricing, specifications, and dedicated support for your requirements.',
                    style: TextStyle(color: AppColors.muted, fontSize: 13),
                  ),
                  const SizedBox(height: 20),

                  // Role Selection
                  const Text(
                    'I am a… *',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                      color: AppColors.ink,
                    ),
                  ),
                  const SizedBox(height: 10),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      _RoleChoice(
                        label: 'End User / Consumer',
                        icon: Icons.person_outline_rounded,
                        value: 'end_user',
                        selected: _type,
                        onTap: (v) => setState(() => _type = v),
                      ),
                      _RoleChoice(
                        label: 'Reseller / Retailer',
                        icon: Icons.storefront_outlined,
                        value: 'reseller',
                        selected: _type,
                        onTap: (v) => setState(() => _type = v),
                      ),
                      _RoleChoice(
                        label: 'EPC Contractor',
                        icon: Icons.bolt_outlined,
                        value: 'epc',
                        selected: _type,
                        onTap: (v) => setState(() => _type = v),
                      ),
                      _RoleChoice(
                        label: 'Authorized Distributor',
                        icon: Icons.business_outlined,
                        value: 'distributor',
                        selected: _type,
                        onTap: (v) => setState(() => _type = v),
                      ),
                    ],
                  ),

                  const SizedBox(height: 18),

                  // Company name (REQUIRED for Reseller, EPC, Distributor)
                  if (_isBusiness) ...[
                    _ProfileField(
                      controller: _company,
                      label: 'Company / Business Name *',
                      icon: Icons.business_rounded,
                      validator: (v) => _required(v, 'company / business name'),
                    ),
                    const SizedBox(height: 12),
                  ],

                  // Full name (REQUIRED for all)
                  _ProfileField(
                    controller: _name,
                    label: 'Full Name *',
                    icon: Icons.person_outline_rounded,
                    validator: (v) => _required(v, 'full name'),
                  ),
                  const SizedBox(height: 12),

                  // Mobile number (REQUIRED for all)
                  _ProfileField(
                    controller: _mobile,
                    label: 'Mobile Number *',
                    icon: Icons.phone_outlined,
                    keyboard: TextInputType.phone,
                    validator: (v) {
                      final error = _required(v, 'mobile number', minLength: 10);
                      if (error != null) return error;
                      return RegExp(r'^[+0-9()\-\s]+$').hasMatch(v!.trim())
                          ? null
                          : 'Use digits and an optional country code.';
                    },
                  ),
                  const SizedBox(height: 12),

                  // Verified Email
                  TextFormField(
                    initialValue: widget.user.email ?? '',
                    readOnly: true,
                    decoration: const InputDecoration(
                      labelText: 'Account Email',
                      prefixIcon: Icon(Icons.email_outlined),
                    ),
                  ),
                  const SizedBox(height: 12),

                  // Location (REQUIRED for all)
                  _ProfileField(
                    controller: _location,
                    label: 'Location (City, State) *',
                    icon: Icons.location_on_outlined,
                    validator: (v) => _required(v, 'location (city, state)'),
                  ),

                  // GST Number (REQUIRED for Reseller, EPC, Distributor)
                  if (_isBusiness) ...[
                    const SizedBox(height: 12),
                    _ProfileField(
                      controller: _gst,
                      label: 'GSTIN / GST Number *',
                      icon: Icons.receipt_long_outlined,
                      textCapitalization: TextCapitalization.characters,
                      validator: _validateGst,
                    ),
                  ],

                  if (_error != null) _InlineMessage(text: _error!, error: true),

                  const SizedBox(height: 20),
                  FilledButton(
                    onPressed: _busy ? null : _save,
                    child: _busy
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                          )
                        : const Text('Save and Continue'),
                  ),
                  const SizedBox(height: 6),
                  TextButton(
                    onPressed: _busy ? null : () => FirebaseAuth.instance.signOut(),
                    child: const Text('Sign out'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    ),
  );
}

class _ProfileField extends StatelessWidget {
  const _ProfileField({
    required this.controller,
    required this.label,
    required this.icon,
    this.keyboard,
    this.textCapitalization = TextCapitalization.none,
    this.validator,
  });
  final TextEditingController controller;
  final String label;
  final IconData icon;
  final TextInputType? keyboard;
  final TextCapitalization textCapitalization;
  final String? Function(String?)? validator;

  @override
  Widget build(BuildContext context) => TextFormField(
    controller: controller,
    keyboardType: keyboard,
    textCapitalization: textCapitalization,
    validator: validator,
    decoration: InputDecoration(labelText: label, prefixIcon: Icon(icon)),
  );
}

class _RoleChoice extends StatelessWidget {
  const _RoleChoice({
    required this.label,
    required this.icon,
    required this.value,
    required this.selected,
    required this.onTap,
  });
  final String label;
  final IconData icon;
  final String value, selected;
  final ValueChanged<String> onTap;

  @override
  Widget build(BuildContext context) {
    final active = selected == value;
    return InkWell(
      onTap: () => onTap(value),
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: active ? const Color(0xFFEAF3FA) : Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: active ? AppColors.blue : AppColors.border,
            width: active ? 2 : 1,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              size: 18,
              color: active ? AppColors.blue : AppColors.muted,
            ),
            const SizedBox(width: 8),
            Text(
              label,
              style: TextStyle(
                color: active ? AppColors.blue : AppColors.ink,
                fontWeight: active ? FontWeight.w700 : FontWeight.w500,
                fontSize: 13,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _LoadingPage extends StatelessWidget {
  const _LoadingPage();
  @override
  Widget build(BuildContext context) =>
      const Scaffold(body: Center(child: CircularProgressIndicator()));
}

class _BrandMark extends StatelessWidget {
  const _BrandMark();
  @override
  Widget build(BuildContext context) => Row(
    mainAxisAlignment: MainAxisAlignment.center,
    children: [
      Container(
        width: 42,
        height: 42,
        decoration: BoxDecoration(
          color: AppColors.navy,
          borderRadius: BorderRadius.circular(13),
        ),
        child: const Icon(Icons.bolt_rounded, color: Colors.white, size: 25),
      ),
      const SizedBox(width: 10),
      const Text(
        'EnerTech',
        style: TextStyle(
          color: AppColors.navy,
          fontWeight: FontWeight.w800,
          fontSize: 20,
        ),
      ),
    ],
  );
}

class _InlineMessage extends StatelessWidget {
  const _InlineMessage({required this.text, required this.error});
  final String text;
  final bool error;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: 11),
    child: Container(
      padding: const EdgeInsets.all(11),
      decoration: BoxDecoration(
        color: error ? const Color(0xFFFFF1EF) : const Color(0xFFEBF7EF),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        text,
        style: TextStyle(
          color: error ? const Color(0xFF9A3029) : const Color(0xFF21613A),
          fontSize: 12,
        ),
      ),
    ),
  );
}

String _authMessage(FirebaseAuthException error) => switch (error.code) {
  'invalid-email' => 'Enter a valid email address.',
  'weak-password' => 'Choose a stronger password (at least 6 characters).',
  'email-already-in-use' =>
    'An account already exists for this email. Sign in instead.',
  'invalid-credential' ||
  'wrong-password' ||
  'user-not-found' => 'Email or password is incorrect.',
  'too-many-requests' => 'Too many attempts. Wait a little, then try again.',
  'google-not-configured' => 'Google sign-in needs the Firebase OAuth client ID configured.',
  'popup-closed-by-user' ||
  'canceled' => 'Sign-in was cancelled.',
  _ => error.message ?? 'Authentication could not be completed. Try again.',
};
