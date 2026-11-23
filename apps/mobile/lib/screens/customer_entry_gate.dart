import 'dart:io';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
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
        if (snapshot.connectionState == ConnectionState.waiting &&
            !snapshot.hasData) {
          return const _LoadingPage();
        }
        final user = snapshot.data;
        if (user == null) return const _CustomerAuthPage();
        if (!user.emailVerified) return _VerifyEmailPage(user: user);
        return FutureBuilder<CustomerProfile?>(
          key: ValueKey(user.uid),
          future: _profiles.loadMine(),
          builder: (context, profileSnapshot) {
            if (profileSnapshot.connectionState != ConnectionState.done)
              return const _LoadingPage();
            if (profileSnapshot.hasError) {
              return _ProfileLoadError(
                onRetry: () => setState(() {}),
                error: profileSnapshot.error,
              );
            }
            final profile = profileSnapshot.data;
            if (profile == null)
              return _CustomerOnboardingPage(
                user: user,
                onSaved: () => setState(() {}),
              );
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

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _emailAuth() async {
    FocusScope.of(context).unfocus();
    setState(() {
      _busy = true;
      _error = null;
      _notice = null;
    });
    try {
      final auth = FirebaseAuth.instance;
      if (_creating) {
        final result = await auth.createUserWithEmailAndPassword(
          email: _email.text.trim(),
          password: _password.text,
        );
        await result.user?.sendEmailVerification();
        if (mounted)
          setState(
            () => _notice = 'We sent a verification link to your email. Open it to continue.',
          );
      } else {
        await auth.signInWithEmailAndPassword(
          email: _email.text.trim(),
          password: _password.text,
        );
      }
    } on FirebaseAuthException catch (error) {
      if (mounted) setState(() => _error = _authMessage(error));
    } catch (_) {
      if (mounted)
        setState(
          () => _error = 'Could not connect. Check your network and try again.',
        );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _googleAuth() async {
    setState(() {
      _busy = true;
      _error = null;
      _notice = null;
    });
    try {
      await _auth.signInWithGoogle();
    } on FirebaseAuthException catch (error) {
      if (mounted) setState(() => _error = _authMessage(error));
    } catch (_) {
      if (mounted)
        setState(
          () => _error =
              'Google sign-in could not be completed. Please try again.',
        );
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
      if (mounted)
        setState(() {
          _error = null;
          _notice = 'Password reset instructions have been sent.';
        });
    } on FirebaseAuthException catch (error) {
      if (mounted) setState(() => _error = _authMessage(error));
    }
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
                const SizedBox(height: 28),
                Text(
                  _creating ? 'Create your account' : 'Welcome to EnerTech',
                  style: const TextStyle(
                    fontSize: 26,
                    fontWeight: FontWeight.w800,
                    color: AppColors.ink,
                  ),
                ),
                const SizedBox(height: 7),
                Text(
                  _creating ? 'Get product support and updates made for you.' : 'Sign in to explore products and get the right support.',
                  style: const TextStyle(fontSize: 14, color: AppColors.muted),
                ),
                const SizedBox(height: 22),
                OutlinedButton.icon(
                  onPressed: _busy ? null : _googleAuth,
                  icon: const Icon(Icons.g_mobiledata_rounded, size: 26),
                  label: const Text('Continue with Google'),
                ),
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 16),
                  child: Row(
                    children: [
                      Expanded(child: Divider()),
                      Padding(
                        padding: EdgeInsets.symmetric(horizontal: 12),
                        child: Text(
                          'OR',
                          style: TextStyle(
                            fontSize: 11,
                            color: AppColors.muted,
                          ),
                        ),
                      ),
                      Expanded(child: Divider()),
                    ],
                  ),
                ),
                TextField(
                  controller: _email,
                  keyboardType: TextInputType.emailAddress,
                  autofillHints: const [AutofillHints.email],
                  decoration: const InputDecoration(
                    labelText: 'Email address',
                    prefixIcon: Icon(Icons.mail_outline_rounded),
                  ),
                ),
                const SizedBox(height: 11),
                TextField(
                  controller: _password,
                  obscureText: true,
                  autofillHints: [
                    _creating
                        ? AutofillHints.newPassword
                        : AutofillHints.password,
                  ],
                  decoration: const InputDecoration(
                    labelText: 'Password',
                    prefixIcon: Icon(Icons.lock_outline_rounded),
                  ),
                ),
                if (_error != null) _InlineMessage(text: _error!, error: true),
                if (_notice != null)
                  _InlineMessage(text: _notice!, error: false),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: _busy ? null : _emailAuth,
                  child: _busy
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
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
                        }),
                  child: Text(
                    _creating
                        ? 'Already have an account?  Sign in'
                        : 'New to EnerTech?  Create an account',
                  ),
                ),
                const SizedBox(height: 8),
                const Text(
                  'Your account is protected by Firebase Authentication.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: AppColors.muted, fontSize: 12),
                ),
              ],
            ),
          ),
        ),
      ),
    ),
  );
}

class _VerifyEmailPage extends StatefulWidget {
  const _VerifyEmailPage({required this.user});
  final User user;

  @override
  State<_VerifyEmailPage> createState() => _VerifyEmailPageState();
}

class _VerifyEmailPageState extends State<_VerifyEmailPage> {
  bool _busy = false;
  String? _notice;
  String? _error;

  Future<void> _checkVerification() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.user.reload();
      await FirebaseAuth.instance.currentUser?.getIdToken(true);
      if (FirebaseAuth.instance.currentUser?.emailVerified != true && mounted) {
        setState(
          () => _error = 'Email not verified yet. Open the link in your inbox, then check again.',
        );
      }
    } catch (_) {
      if (mounted)
        setState(() => _error = 'Could not check verification. Try again.');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _resend() async {
    try {
      await widget.user.sendEmailVerification();
      if (mounted)
        setState(() => _notice = 'A new verification link has been sent.');
    } on FirebaseAuthException catch (error) {
      if (mounted) setState(() => _error = _authMessage(error));
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 440),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Icon(
                  Icons.mark_email_read_outlined,
                  size: 54,
                  color: AppColors.blue,
                ),
                const SizedBox(height: 18),
                const Text(
                  'Verify your email',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.w800,
                    color: AppColors.ink,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  'We sent a link to ${widget.user.email ?? 'your email'}. Verify it to finish setting up your profile.',
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: AppColors.muted),
                ),
                if (_error != null) _InlineMessage(text: _error!, error: true),
                if (_notice != null)
                  _InlineMessage(text: _notice!, error: false),
                const SizedBox(height: 18),
                FilledButton(
                  onPressed: _busy ? null : _checkVerification,
                  child: Text(_busy ? 'Checking…' : 'I have verified my email'),
                ),
                TextButton(
                  onPressed: _resend,
                  child: const Text('Resend verification email'),
                ),
                TextButton(
                  onPressed: () => FirebaseAuth.instance.signOut(),
                  child: const Text('Use a different account'),
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
  State<_CustomerOnboardingPage> createState() =>
      _CustomerOnboardingPageState();
}

class _CustomerOnboardingPageState extends State<_CustomerOnboardingPage> {
  final _formKey = GlobalKey<FormState>();
  final _company = TextEditingController();
  final _name = TextEditingController();
  final _mobile = TextEditingController();
  final _location = TextEditingController();
  final _gst = TextEditingController();
  final _profiles = CustomerProfileRepository();
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
    if (clean.length < minLength)
      return '$label must have at least $minLength characters.';
    return null;
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await _profiles.save({
        'customer_type': _type,
        'name': _name.text.trim(),
        'mobile_number': _mobile.text.trim(),
        'email': widget.user.email!.trim().toLowerCase(),
        'location': _location.text.trim(),
        'company_name': _isBusiness ? _company.text.trim() : null,
        'gst_number': _isBusiness ? _gst.text.trim().toUpperCase() : null,
      });
      widget.onSaved();
    } on HttpException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } catch (_) {
      if (mounted)
        setState(
          () => _error = 'We could not save your details. Check your connection and try again.',
        );
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
                  const SizedBox(height: 25),
                  const Text(
                    'Let’s set up your profile',
                    style: TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.w800,
                      color: AppColors.ink,
                    ),
                  ),
                  const SizedBox(height: 6),
                  const Text(
                    'Tell us how you use EnerTech so we can make the app more useful for you.',
                    style: TextStyle(color: AppColors.muted, fontSize: 13),
                  ),
                  const SizedBox(height: 18),
                  const Text(
                    'I am a…',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                      color: AppColors.ink,
                    ),
                  ),
                  const SizedBox(height: 9),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      _RoleChoice(
                        label: 'End User',
                        value: 'end_user',
                        selected: _type,
                        onTap: (v) => setState(() => _type = v),
                      ),
                      _RoleChoice(
                        label: 'Reseller',
                        value: 'reseller',
                        selected: _type,
                        onTap: (v) => setState(() => _type = v),
                      ),
                      _RoleChoice(
                        label: 'EPC',
                        value: 'epc',
                        selected: _type,
                        onTap: (v) => setState(() => _type = v),
                      ),
                      _RoleChoice(
                        label: 'Distributor',
                        value: 'distributor',
                        selected: _type,
                        onTap: (v) => setState(() => _type = v),
                      ),
                    ],
                  ),
                  if (_isBusiness) ...[
                    const SizedBox(height: 14),
                    _ProfileField(
                      controller: _company,
                      label: 'Company name',
                      icon: Icons.business_outlined,
                      validator: (v) => _required(v, 'company name'),
                    ),
                  ],
                  const SizedBox(height: 12),
                  _ProfileField(
                    controller: _name,
                    label: 'Full name',
                    icon: Icons.person_outline_rounded,
                    validator: (v) => _required(v, 'name'),
                  ),
                  const SizedBox(height: 12),
                  _ProfileField(
                    controller: _mobile,
                    label: 'Mobile number',
                    icon: Icons.phone_outlined,
                    keyboard: TextInputType.phone,
                    validator: (v) {
                      final error = _required(v, 'mobile number', minLength: 7);
                      if (error != null) return error;
                      return RegExp(r'^[+0-9()\-\s]+$').hasMatch(v!.trim())
                          ? null
                          : 'Use digits and an optional + country code.';
                    },
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    initialValue: widget.user.email ?? '',
                    readOnly: true,
                    decoration: const InputDecoration(
                      labelText: 'Verified email',
                      prefixIcon: Icon(Icons.verified_user_outlined),
                    ),
                  ),
                  const SizedBox(height: 12),
                  _ProfileField(
                    controller: _location,
                    label: 'Location (city, state)',
                    icon: Icons.location_on_outlined,
                    validator: (v) => _required(v, 'location'),
                  ),
                  if (_isBusiness) ...[
                    const SizedBox(height: 12),
                    _ProfileField(
                      controller: _gst,
                      label: 'GST number',
                      icon: Icons.receipt_long_outlined,
                      textCapitalization: TextCapitalization.characters,
                      validator: (v) =>
                          _required(v, 'GST number', minLength: 2),
                    ),
                  ],
                  if (_error != null)
                    _InlineMessage(text: _error!, error: true),
                  const SizedBox(height: 18),
                  FilledButton(
                    onPressed: _busy ? null : _save,
                    child: _busy
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Text('Save and continue'),
                  ),
                  TextButton(
                    onPressed: _busy
                        ? null
                        : () => FirebaseAuth.instance.signOut(),
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
    required this.value,
    required this.selected,
    required this.onTap,
  });
  final String label, value, selected;
  final ValueChanged<String> onTap;
  @override
  Widget build(BuildContext context) {
    final active = selected == value;
    return ChoiceChip(
      label: Text(label),
      selected: active,
      onSelected: (_) => onTap(value),
      selectedColor: const Color(0xFFEAF3FA),
      side: BorderSide(color: active ? AppColors.blue : AppColors.border),
      labelStyle: TextStyle(
        color: active ? AppColors.blue : AppColors.ink,
        fontWeight: active ? FontWeight.w700 : FontWeight.w500,
      ),
    );
  }
}

class _ProfileLoadError extends StatelessWidget {
  const _ProfileLoadError({required this.onRetry, this.error});
  final VoidCallback onRetry;
  final Object? error;
  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(
                Icons.cloud_off_outlined,
                size: 44,
                color: AppColors.muted,
              ),
              const SizedBox(height: 12),
              const Text(
                'Could not load your profile',
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w700,
                  color: AppColors.ink,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                error is HttpException
                    ? (error as HttpException).message
                    : 'Check your connection and try again.',
                textAlign: TextAlign.center,
                style: const TextStyle(color: AppColors.muted),
              ),
              const SizedBox(height: 14),
              FilledButton(onPressed: onRetry, child: const Text('Try again')),
              TextButton(
                onPressed: () => FirebaseAuth.instance.signOut(),
                child: const Text('Sign out'),
              ),
            ],
          ),
        ),
      ),
    ),
  );
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
  'google-not-configured' => 'Google sign-in needs the Firebase OAuth client ID configured before building.',
  _ => error.message ?? 'Authentication could not be completed. Try again.',
};
