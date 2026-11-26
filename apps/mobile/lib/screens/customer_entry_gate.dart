import 'dart:io';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

import '../data/customer_auth_service.dart';
import '../data/customer_profile_repository.dart';
import '../theme/app_theme.dart';
import '../widgets/app_components.dart';
import 'app_shell.dart';

class CustomerEntryGate extends StatefulWidget {
  const CustomerEntryGate({super.key});

  @override
  State<CustomerEntryGate> createState() => _CustomerEntryGateState();
}

class _CustomerEntryGateState extends State<CustomerEntryGate> {
  final _profiles = CustomerProfileRepository();
  String? _verificationDispatchError;

  @override
  Widget build(BuildContext context) {
    final apiUrl = Uri.tryParse(CustomerProfileRepository.effectiveBaseUrl);
    if (Firebase.apps.isEmpty ||
        apiUrl == null ||
        !apiUrl.hasScheme ||
        !apiUrl.hasAuthority) {
      return const _AppConfigurationPage();
    }
    return StreamBuilder<User?>(
      stream: FirebaseAuth.instance.userChanges(),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting &&
            !snapshot.hasData) {
          return const _LoadingPage();
        }
        final user = snapshot.data;
        if (user == null)
          return _CustomerAuthPage(
            onVerificationDispatchError: (message) =>
                setState(() => _verificationDispatchError = message),
          );
        if (!user.emailVerified) {
          return _EmailVerificationPage(
            user: user,
            initialError: _verificationDispatchError,
            onEmailSent: () =>
                setState(() => _verificationDispatchError = null),
            onVerified: () => setState(() {
              _verificationDispatchError = null;
            }),
          );
        }

        return FutureBuilder<CustomerProfile?>(
          key: ValueKey(user.uid),
          future: _profiles.loadMine(userUid: user.uid),
          builder: (context, profileSnapshot) {
            if (profileSnapshot.connectionState != ConnectionState.done) {
              return const _LoadingPage();
            }

            final profile = profileSnapshot.data;
            // When user has not completed onboarding, ALWAYS show role selection!
            if (profile == null) {
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
  const _CustomerAuthPage({required this.onVerificationDispatchError});
  final ValueChanged<String?> onVerificationDispatchError;

  @override
  State<_CustomerAuthPage> createState() => _CustomerAuthPageState();
}

class _CustomerAuthPageState extends State<_CustomerAuthPage> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _passwordFocus = FocusNode();
  final _auth = CustomerAuthService();
  bool _creating = false;
  bool _busy = false;
  String? _error;
  String? _notice;
  bool _showShaNotice = false;
  bool _passwordVisible = false;
  bool _resetBusy = false;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    _passwordFocus.dispose();
    super.dispose();
  }

  Future<void> _emailAuth() async {
    FocusScope.of(context).unfocus();
    final emailText = _email.text.trim();
    final passwordText = _password.text;

    if (!RegExp(r'^[^\s@]+@[^\s@]+\.[^\s@]+$').hasMatch(emailText)) {
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
        try {
          await result.user?.sendEmailVerification();
          widget.onVerificationDispatchError(null);
        } catch (_) {
          widget.onVerificationDispatchError(
            'Your account was created, but the verification email could not be sent. Tap “Resend verification email” after this screen opens.',
          );
        }
      } else {
        await auth.signInWithEmailAndPassword(
          email: emailText,
          password: passwordText,
        );
        widget.onVerificationDispatchError(null);
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
        final isHashError =
            error.code == '10' ||
            error.code == 'developer-error' ||
            msg.contains('certificate') ||
            msg.contains('hash') ||
            msg.contains('fingerprint');
        setState(() {
          _error = isHashError
              ? 'Google sign-in could not verify this build’s signing certificate. Register its release SHA-1 in Firebase, refresh the Android Firebase config, and install a build made with that config.'
              : _authMessage(error);
          _showShaNotice = isHashError;
        });
      }
    } catch (e) {
      if (mounted) {
        final errStr = e.toString().toLowerCase();
        final isHashError =
            errStr.contains('10') ||
            errStr.contains('certificate') ||
            errStr.contains('hash') ||
            errStr.contains('sign_in_failed');
        setState(() {
          _error = isHashError
              ? 'Google sign-in could not verify this build’s signing certificate. Register its release SHA-1 in Firebase, refresh the Android Firebase config, and install a build made with that config.'
              : 'Google sign-in could not be completed ($e). Please use email and password instead.';
          _showShaNotice = isHashError;
        });
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
    setState(() {
      _resetBusy = true;
      _error = null;
      _notice = null;
    });
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
    } catch (_) {
      if (mounted)
        setState(
          () => _error = 'Could not send a password reset email. Check your connection and try again.',
        );
    } finally {
      if (mounted) setState(() => _resetBusy = false);
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
                const SizedBox(height: 24),
                Text(
                  _creating
                      ? 'Create your account'
                      : 'Welcome to ${BrandIdentity.companyName}',
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

                if (_showShaNotice) ...[
                  const SizedBox(height: 12),
                  const NoticeCard(
                    message: 'In Firebase Console, open Project settings → General → Your apps → this Android app → SHA certificate fingerprints. Add the release APK’s SHA-1, save, download the refreshed google-services.json, then rebuild and install the APK.',
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

                // Email & Password
                AutofillGroup(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      TextField(
                        controller: _email,
                        keyboardType: TextInputType.emailAddress,
                        textCapitalization: TextCapitalization.none,
                        textInputAction: TextInputAction.next,
                        autocorrect: false,
                        autofillHints: const [AutofillHints.email],
                        onSubmitted: (_) =>
                            FocusScope.of(context).requestFocus(_passwordFocus),
                        decoration: const InputDecoration(
                          labelText: 'Email address',
                          prefixIcon: Icon(Icons.mail_outline_rounded),
                        ),
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: _password,
                        focusNode: _passwordFocus,
                        obscureText: !_passwordVisible,
                        textInputAction: TextInputAction.done,
                        autocorrect: false,
                        enableSuggestions: false,
                        autofillHints: [
                          _creating
                              ? AutofillHints.newPassword
                              : AutofillHints.password,
                        ],
                        onSubmitted: (_) {
                          if (!_busy) _emailAuth();
                        },
                        decoration: InputDecoration(
                          labelText: 'Password',
                          prefixIcon: const Icon(Icons.lock_outline_rounded),
                          suffixIcon: IconButton(
                            tooltip: _passwordVisible
                                ? 'Hide password'
                                : 'Show password',
                            onPressed: () => setState(
                              () => _passwordVisible = !_passwordVisible,
                            ),
                            icon: Icon(
                              _passwordVisible
                                  ? Icons.visibility_off_outlined
                                  : Icons.visibility_outlined,
                            ),
                          ),
                        ),
                      ),
                    ],
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
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : Text(_creating ? 'Create account' : 'Sign in'),
                ),

                if (!_creating)
                  Align(
                    alignment: Alignment.centerRight,
                    child: TextButton(
                      onPressed: _busy || _resetBusy ? null : _resetPassword,
                      child: _resetBusy
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Text('Forgot password?'),
                    ),
                  ),

                TextButton(
                  onPressed: _busy
                      ? null
                      : () => setState(() {
                          _creating = !_creating;
                          _passwordVisible = false;
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

class _EmailVerificationPage extends StatefulWidget {
  const _EmailVerificationPage({
    required this.user,
    required this.onVerified,
    required this.onEmailSent,
    this.initialError,
  });
  final User user;
  final VoidCallback onVerified;
  final VoidCallback onEmailSent;
  final String? initialError;

  @override
  State<_EmailVerificationPage> createState() => _EmailVerificationPageState();
}

class _EmailVerificationPageState extends State<_EmailVerificationPage> {
  bool _busy = false;
  String? _error;
  String? _notice;

  @override
  void initState() {
    super.initState();
    _error = widget.initialError;
  }

  Future<void> _resend() async {
    setState(() {
      _busy = true;
      _error = null;
      _notice = null;
    });
    try {
      await widget.user.sendEmailVerification();
      widget.onEmailSent();
      if (mounted)
        setState(
          () => _notice =
              'Verification email sent. Check your inbox and spam folder.',
        );
    } on FirebaseAuthException catch (error) {
      if (mounted) setState(() => _error = _authMessage(error));
    } catch (_) {
      if (mounted)
        setState(
          () => _error = 'Could not send the verification email. Check your connection and try again.',
        );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _checkVerification() async {
    setState(() {
      _busy = true;
      _error = null;
      _notice = null;
    });
    try {
      await widget.user.reload();
      final current = FirebaseAuth.instance.currentUser;
      if (current?.emailVerified == true) {
        widget.onVerified();
      } else if (mounted) {
        setState(
          () => _notice = 'This email is not verified yet. Open the verification link, then try again.',
        );
      }
    } on FirebaseAuthException catch (error) {
      if (mounted) setState(() => _error = _authMessage(error));
    } catch (_) {
      if (mounted)
        setState(
          () => _error = 'Could not check verification status. Try again.',
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
          padding: const EdgeInsets.all(22),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 460),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const _BrandMark(),
                const SizedBox(height: 24),
                const Text(
                  'Verify your email',
                  style: TextStyle(
                    fontSize: 25,
                    fontWeight: FontWeight.w800,
                    color: AppColors.ink,
                  ),
                ),
                const SizedBox(height: 8),
                const Text(
                  'Verify your account before setting up a customer or business profile. This keeps quote and service updates linked to the right account.',
                  style: TextStyle(
                    fontSize: 14,
                    height: 1.45,
                    color: AppColors.muted,
                  ),
                ),
                const SizedBox(height: 18),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(14),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Account email',
                          style: TextStyle(
                            fontSize: 12,
                            color: AppColors.muted,
                          ),
                        ),
                        const SizedBox(height: 4),
                        SelectableText(
                          widget.user.email ?? '',
                          style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w700,
                            color: AppColors.ink,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                if (_error != null) _InlineMessage(text: _error!, error: true),
                if (_notice != null)
                  _InlineMessage(text: _notice!, error: false),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: _busy ? null : _checkVerification,
                  child: _busy
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : const Text('I have verified my email'),
                ),
                const SizedBox(height: 8),
                OutlinedButton(
                  onPressed: _busy ? null : _resend,
                  child: const Text('Resend verification email'),
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
  );
}

class _AppConfigurationPage extends StatelessWidget {
  const _AppConfigurationPage();
  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 460),
            child: const Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const _BrandMark(),
                const SizedBox(height: 22),
                const Text(
                  'App setup is incomplete',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 23,
                    fontWeight: FontWeight.w800,
                    color: AppColors.ink,
                  ),
                ),
                const SizedBox(height: 8),
                const Text(
                  'Customer sign-in and app data are unavailable until Firebase and the HTTPS API endpoint are configured for this app build.',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 14,
                    height: 1.45,
                    color: AppColors.muted,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    ),
  );
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
    if (clean.length != 15) return 'Enter the 15-character GSTIN.';
    // Standard Indian GSTIN pattern: 2 digits + 10 alphanumeric PAN + 1 digit/letter + Z + 1 check digit
    final gstRegex = RegExp(
      r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$',
    );
    if (!gstRegex.hasMatch(clean)) {
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
      await _profiles.save({
        'customer_type': _type,
        'name': _name.text.trim(),
        'mobile_number': _mobile.text.trim(),
        'email': widget.user.email?.trim().toLowerCase() ?? '',
        'location': _location.text.trim(),
        'company_name': _isBusiness ? _company.text.trim() : null,
        'gst_number': _isBusiness ? _gst.text.trim().toUpperCase() : null,
      }, userUid: widget.user.uid);
      widget.onSaved();
    } on HttpException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } catch (_) {
      if (mounted)
        setState(
          () => _error = 'Your profile could not be saved. Check your connection and try again.',
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
                    'Choose the account type that best describes you. This helps our team route your product, quote, and support requests.',
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

                  // Full name (REQUIRED for all)
                  _ProfileField(
                    controller: _name,
                    label: 'Full Name *',
                    icon: Icons.person_outline_rounded,
                    textCapitalization: TextCapitalization.words,
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
                      final error = _required(
                        v,
                        'mobile number',
                        minLength: 10,
                      );
                      if (error != null) return error;
                      final clean = v!.trim();
                      final digits = clean.replaceAll(RegExp(r'[^0-9]'), '');
                      if (!RegExp(r'^\+?[0-9()\-\s]+$').hasMatch(clean) ||
                          digits.length < 10 ||
                          digits.length > 15) {
                        return 'Enter 10–15 digits, with an optional country code.';
                      }
                      return null;
                    },
                  ),
                  const SizedBox(height: 12),

                  // Verified Email
                  TextFormField(
                    initialValue: widget.user.email ?? '',
                    readOnly: true,
                    decoration: const InputDecoration(
                      labelText: 'Verified account email',
                      prefixIcon: Icon(Icons.email_outlined),
                      helperText: 'This email is linked to your sign-in and cannot be changed here.',
                    ),
                  ),
                  const SizedBox(height: 12),

                  // Location (REQUIRED for all)
                  _ProfileField(
                    controller: _location,
                    label: 'Location (City, State) *',
                    icon: Icons.location_on_outlined,
                    textCapitalization: TextCapitalization.words,
                    validator: (v) => _required(v, 'location (city, state)'),
                  ),

                  if (_isBusiness) ...[
                    const SizedBox(height: 12),
                    _ProfileField(
                      controller: _company,
                      label: 'Company / Business Name *',
                      icon: Icons.business_rounded,
                      textCapitalization: TextCapitalization.words,
                      validator: (v) => _required(v, 'company / business name'),
                    ),
                  ],

                  // GST Number (REQUIRED for Reseller, EPC, Distributor)
                  if (_isBusiness) ...[
                    const SizedBox(height: 12),
                    _ProfileField(
                      controller: _gst,
                      label: 'GSTIN / GST Number *',
                      icon: Icons.receipt_long_outlined,
                      textCapitalization: TextCapitalization.characters,
                      inputFormatters: [
                        FilteringTextInputFormatter.allow(
                          RegExp(r'[0-9A-Za-z]'),
                        ),
                        LengthLimitingTextInputFormatter(15),
                      ],
                      textInputAction: TextInputAction.done,
                      validator: _validateGst,
                    ),
                  ],

                  if (_error != null)
                    _InlineMessage(text: _error!, error: true),

                  const SizedBox(height: 20),
                  FilledButton(
                    onPressed: _busy ? null : _save,
                    child: _busy
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Text('Save and Continue'),
                  ),
                  const SizedBox(height: 6),
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
    this.inputFormatters,
    this.textInputAction = TextInputAction.next,
    this.validator,
  });
  final TextEditingController controller;
  final String label;
  final IconData icon;
  final TextInputType? keyboard;
  final TextCapitalization textCapitalization;
  final List<TextInputFormatter>? inputFormatters;
  final TextInputAction textInputAction;
  final String? Function(String?)? validator;

  @override
  Widget build(BuildContext context) => TextFormField(
    controller: controller,
    keyboardType: keyboard,
    textCapitalization: textCapitalization,
    inputFormatters: inputFormatters,
    textInputAction: textInputAction,
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
    final shape = RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(12),
      side: BorderSide(
        color: active ? AppColors.blue : AppColors.border,
        width: active ? 2 : 1,
      ),
    );
    return Semantics(
      button: true,
      selected: active,
      label: label,
      excludeSemantics: true,
      child: Material(
        color: active ? const Color(0xFFEAF3FA) : Colors.white,
        shape: shape,
        child: InkWell(
          onTap: () => onTap(value),
          customBorder: shape,
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: 48),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
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
          ),
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
  Widget build(BuildContext context) => Center(
    child: Image.asset(
      'assets/brand/enertech_logo.png',
      width: 232,
      height: 72,
      fit: BoxFit.contain,
      semanticLabel: '${BrandIdentity.companyName} — Answering All Power Needs',
    ),
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
  'google-not-configured' =>
    'Google sign-in needs the Firebase OAuth client ID configured.',
  'popup-closed-by-user' || 'canceled' => 'Sign-in was cancelled.',
  _ => error.message ?? 'Authentication could not be completed. Try again.',
};
