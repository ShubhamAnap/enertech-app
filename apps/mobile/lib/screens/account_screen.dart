import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:material_ui/material_ui.dart';

import '../data/customer_profile_repository.dart';
import '../theme/app_theme.dart';
import '../widgets/app_components.dart';

class AccountScreen extends StatefulWidget {
  const AccountScreen({super.key});

  @override
  State<AccountScreen> createState() => _AccountScreenState();
}

class _AccountScreenState extends State<AccountScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _profiles = CustomerProfileRepository();
  bool _createAccount = false;
  bool _working = false;
  String? _message;
  String? _error;

  bool get _configured => Firebase.apps.isNotEmpty;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  void _changeServerUrl(BuildContext context) {
    final controller = TextEditingController(text: CustomerProfileRepository.effectiveBaseUrl);
    showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Backend API Server'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Configure the backend endpoint for catalogue and profile synchronization:',
              style: TextStyle(fontSize: 13, color: AppColors.muted),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: controller,
              decoration: const InputDecoration(
                labelText: 'API Base URL',
                hintText: 'e.g. http://192.168.1.50:8000/api/v1',
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () {
              final newUrl = controller.text.trim();
              if (newUrl.isNotEmpty) {
                CustomerProfileRepository.setCustomBaseUrl(newUrl);
                setState(() {});
                Navigator.of(ctx).pop();
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text('Server URL set to: $newUrl')),
                );
              }
            },
            child: const Text('Save'),
          ),
        ],
      ),
    );
  }

  void _editProfile(BuildContext context, CustomerProfile profile, User user) {
    final nameCtrl = TextEditingController(text: profile.name);
    final mobileCtrl = TextEditingController(text: profile.mobileNumber);
    final locationCtrl = TextEditingController(text: profile.location);
    final companyCtrl = TextEditingController(text: profile.companyName ?? '');
    final gstCtrl = TextEditingController(text: profile.gstNumber ?? '');
    String selectedRole = profile.customerType;

    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setSheetState) {
          final isBusiness = selectedRole != 'end_user';
          return Padding(
            padding: EdgeInsets.only(
              left: 20,
              right: 20,
              top: 20,
              bottom: MediaQuery.of(ctx).viewInsets.bottom + 20,
            ),
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text(
                    'Edit Profile & Account Type',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: AppColors.ink),
                  ),
                  const SizedBox(height: 14),
                  const Text('Account Type', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: AppColors.muted)),
                  const SizedBox(height: 6),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      _RoleChip(
                        label: 'End User',
                        selected: selectedRole == 'end_user',
                        onTap: () => setSheetState(() => selectedRole = 'end_user'),
                      ),
                      _RoleChip(
                        label: 'Reseller',
                        selected: selectedRole == 'reseller',
                        onTap: () => setSheetState(() => selectedRole = 'reseller'),
                      ),
                      _RoleChip(
                        label: 'EPC Contractor',
                        selected: selectedRole == 'epc',
                        onTap: () => setSheetState(() => selectedRole = 'epc'),
                      ),
                      _RoleChip(
                        label: 'Distributor',
                        selected: selectedRole == 'distributor',
                        onTap: () => setSheetState(() => selectedRole = 'distributor'),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  if (isBusiness) ...[
                    TextField(
                      controller: companyCtrl,
                      decoration: const InputDecoration(labelText: 'Company / Business Name *', prefixIcon: Icon(Icons.business_rounded)),
                    ),
                    const SizedBox(height: 10),
                    TextField(
                      controller: gstCtrl,
                      textCapitalization: TextCapitalization.characters,
                      decoration: const InputDecoration(labelText: 'GSTIN / GST Number *', prefixIcon: Icon(Icons.receipt_long_outlined)),
                    ),
                    const SizedBox(height: 10),
                  ],
                  TextField(
                    controller: nameCtrl,
                    decoration: const InputDecoration(labelText: 'Full Name *', prefixIcon: Icon(Icons.person_outline_rounded)),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: mobileCtrl,
                    keyboardType: TextInputType.phone,
                    decoration: const InputDecoration(labelText: 'Mobile Number *', prefixIcon: Icon(Icons.phone_outlined)),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: locationCtrl,
                    decoration: const InputDecoration(labelText: 'Location (City, State) *', prefixIcon: Icon(Icons.location_on_outlined)),
                  ),
                  const SizedBox(height: 18),
                  FilledButton(
                    onPressed: () async {
                      final name = nameCtrl.text.trim();
                      final mobile = mobileCtrl.text.trim();
                      final location = locationCtrl.text.trim();
                      final company = companyCtrl.text.trim();
                      final gst = gstCtrl.text.trim().toUpperCase();

                      if (name.isEmpty || mobile.isEmpty || location.isEmpty) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('Please fill all required fields.')),
                        );
                        return;
                      }
                      if (isBusiness && (company.isEmpty || gst.isEmpty)) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('Company name and GST number are required for business accounts.')),
                        );
                        return;
                      }

                      await _profiles.save(
                        {
                          'customer_type': selectedRole,
                          'name': name,
                          'mobile_number': mobile,
                          'email': user.email ?? '',
                          'location': location,
                          'company_name': isBusiness ? company : null,
                          'gst_number': isBusiness ? gst : null,
                        },
                        userUid: user.uid,
                      );
                      if (mounted) {
                        Navigator.of(ctx).pop();
                        setState(() {});
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('Profile updated successfully!')),
                        );
                      }
                    },
                    child: const Text('Save Changes'),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Future<void> _submit() async {
    setState(() { _working = true; _error = null; _message = null; });
    try {
      final auth = FirebaseAuth.instance;
      if (_createAccount) {
        final credential = await auth.createUserWithEmailAndPassword(email: _email.text.trim(), password: _password.text);
        try {
          await credential.user?.sendEmailVerification();
        } catch (_) {}
        setState(() => _message = 'Account created successfully!');
      } else {
        await auth.signInWithEmailAndPassword(email: _email.text.trim(), password: _password.text);
      }
    } on FirebaseAuthException catch (exception) {
      setState(() => _error = switch (exception.code) {
        'invalid-email' => 'Enter a valid email address.',
        'weak-password' => 'Choose a stronger password (at least 6 characters).',
        'email-already-in-use' => 'An account already exists for this email.',
        'invalid-credential' || 'wrong-password' || 'user-not-found' => 'Email or password is incorrect.',
        'too-many-requests' => 'Too many attempts. Wait a little, then try again.',
        _ => exception.message ?? 'Authentication could not be completed. Try again.',
      });
    } catch (_) {
      setState(() => _error = 'Authentication could not be completed. Check your connection and try again.');
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

  Future<void> _resetPassword() async {
    if (_email.text.trim().isEmpty) { setState(() => _error = 'Enter your email address first.'); return; }
    try {
      await FirebaseAuth.instance.sendPasswordResetEmail(email: _email.text.trim());
      setState(() { _error = null; _message = 'Password reset instructions have been sent to your email.'; });
    } on FirebaseAuthException catch (exception) {
      setState(() => _error = exception.message ?? 'Could not send the password reset email.');
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!_configured) return _buildSetup();
    return StreamBuilder<User?>(
      stream: FirebaseAuth.instance.authStateChanges(),
      builder: (context, snapshot) => snapshot.data == null ? _buildSignIn() : _buildAccount(snapshot.data!),
    );
  }

  Widget _buildSetup() => ListView(padding: const EdgeInsets.fromLTRB(20, 22, 20, 28), children: [
    const Text('Account', style: TextStyle(color: AppColors.ink, fontSize: 24, fontWeight: FontWeight.w800)),
    const SizedBox(height: 5),
    const Text('Create an account or sign in to manage your requests.', style: TextStyle(color: AppColors.muted, fontSize: 13)),
    const SizedBox(height: 18),
    const NoticeCard(message: 'Firebase Authentication is not configured. Add the public Firebase app values to apps/mobile/.env to enable sign-in and registration.'),
    const SizedBox(height: 12),
    const _AccountAction(icon: Icons.business_outlined, title: 'Business profile', detail: 'Available after account setup'),
    const _AccountAction(icon: Icons.location_on_outlined, title: 'Project locations', detail: 'Available after account setup'),
  ]);

  Widget _buildSignIn() => ListView(padding: const EdgeInsets.fromLTRB(20, 22, 20, 28), children: [
    const Text('Account', style: TextStyle(color: AppColors.ink, fontSize: 24, fontWeight: FontWeight.w800)),
    const SizedBox(height: 5),
    const Text('Manage your profile and preferences.', style: TextStyle(color: AppColors.muted, fontSize: 13)),
    const SizedBox(height: 18),
    Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Text(_createAccount ? 'Create your EnerTech account' : 'Sign in to EnerTech', style: const TextStyle(color: AppColors.ink, fontSize: 16, fontWeight: FontWeight.w700)),
      const SizedBox(height: 12),
      TextField(controller: _email, keyboardType: TextInputType.emailAddress, autofillHints: const [AutofillHints.email], decoration: const InputDecoration(labelText: 'Email address', prefixIcon: Icon(Icons.mail_outline_rounded))),
      const SizedBox(height: 10),
      TextField(controller: _password, obscureText: true, autofillHints: [_createAccount ? AutofillHints.newPassword : AutofillHints.password], decoration: const InputDecoration(labelText: 'Password', prefixIcon: Icon(Icons.lock_outline_rounded))),
      if (_error != null) Padding(padding: const EdgeInsets.only(top: 10), child: Text(_error!, style: const TextStyle(color: Color(0xFF9A3029), fontSize: 12))),
      if (_message != null) Padding(padding: const EdgeInsets.only(top: 10), child: Text(_message!, style: const TextStyle(color: Color(0xFF21613A), fontSize: 12))),
      const SizedBox(height: 14),
      FilledButton(onPressed: _working ? null : _submit, child: _working ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white)) : Text(_createAccount ? 'Create account' : 'Sign in')),
      TextButton(onPressed: () => setState(() { _createAccount = !_createAccount; _error = null; _message = null; }), child: Text(_createAccount ? 'Already have an account? Sign in' : 'New to EnerTech? Create an account')),
      if (!_createAccount) TextButton(onPressed: _resetPassword, child: const Text('Forgot password?')),
    ]))),
    const SizedBox(height: 10),
    const NoticeCard(message: 'Your sign-in is handled securely by Firebase.'),
  ]);

  Widget _buildAccount(User user) => FutureBuilder<CustomerProfile?>(
    future: _profiles.loadMine(userUid: user.uid),
    builder: (context, snapshot) {
      final profile = snapshot.data;
      final roleText = profile?.roleDisplayName ?? 'Customer';
      final isBiz = profile?.isBusiness ?? false;

      return ListView(
        padding: const EdgeInsets.fromLTRB(20, 22, 20, 28),
        children: [
          const Text('Account', style: TextStyle(color: AppColors.ink, fontSize: 24, fontWeight: FontWeight.w800)),
          const SizedBox(height: 5),
          const Text('Manage your profile and business details.', style: TextStyle(color: AppColors.muted, fontSize: 13)),
          const SizedBox(height: 18),

          // User Card
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: [
                  Container(
                    width: 52,
                    height: 52,
                    decoration: BoxDecoration(
                      color: const Color(0xFFEAF3FA),
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: const Icon(Icons.person_outline_rounded, color: AppColors.blue, size: 28),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          profile?.name.isNotEmpty == true ? profile!.name : (user.displayName ?? 'EnerTech Customer'),
                          style: const TextStyle(color: AppColors.ink, fontWeight: FontWeight.w700, fontSize: 16),
                        ),
                        const SizedBox(height: 3),
                        Text(user.email ?? '', style: const TextStyle(color: AppColors.muted, fontSize: 12)),
                        const SizedBox(height: 5),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(
                            color: AppColors.blue.withValues(alpha: 0.1),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Text(
                            roleText,
                            style: const TextStyle(
                              color: AppColors.blue,
                              fontWeight: FontWeight.w700,
                              fontSize: 11,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),

          const SizedBox(height: 14),

          // Role & Business details
          if (profile != null) ...[
            _AccountAction(
              icon: Icons.badge_outlined,
              title: 'Account Role',
              detail: roleText,
              onTap: () => _editProfile(context, profile, user),
            ),
            if (isBiz && profile.companyName != null && profile.companyName!.isNotEmpty)
              _AccountAction(
                icon: Icons.business_outlined,
                title: 'Company Name',
                detail: profile.companyName!,
                onTap: () => _editProfile(context, profile, user),
              ),
            if (isBiz && profile.gstNumber != null && profile.gstNumber!.isNotEmpty)
              _AccountAction(
                icon: Icons.receipt_long_outlined,
                title: 'GST Number',
                detail: profile.gstNumber!,
                onTap: () => _editProfile(context, profile, user),
              ),
            if (profile.mobileNumber.isNotEmpty)
              _AccountAction(
                icon: Icons.phone_outlined,
                title: 'Mobile Number',
                detail: profile.mobileNumber,
                onTap: () => _editProfile(context, profile, user),
              ),
            if (profile.location.isNotEmpty)
              _AccountAction(
                icon: Icons.location_on_outlined,
                title: 'Location',
                detail: profile.location,
                onTap: () => _editProfile(context, profile, user),
              ),
            const SizedBox(height: 5),
          ],

          _AccountAction(
            icon: Icons.dns_outlined,
            title: 'Server Connection',
            detail: CustomerProfileRepository.effectiveBaseUrl,
            onTap: () => _changeServerUrl(context),
          ),

          const SizedBox(height: 18),
          OutlinedButton.icon(
            onPressed: () {
              CustomerProfileRepository.clearCache();
              FirebaseAuth.instance.signOut();
            },
            icon: const Icon(Icons.logout_rounded),
            label: const Text('Sign out'),
          ),
        ],
      );
    },
  );
}

class _RoleChip extends StatelessWidget {
  const _RoleChip({required this.label, required this.selected, required this.onTap});
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => ChoiceChip(
    label: Text(label),
    selected: selected,
    onSelected: (_) => onTap(),
    selectedColor: const Color(0xFFEAF3FA),
    side: BorderSide(color: selected ? AppColors.blue : AppColors.border),
    labelStyle: TextStyle(
      color: selected ? AppColors.blue : AppColors.ink,
      fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
    ),
  );
}

class _AccountAction extends StatelessWidget {
  const _AccountAction({
    required this.icon,
    required this.title,
    required this.detail,
    this.onTap,
  });

  final IconData icon;
  final String title;
  final String detail;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 9),
    child: Card(
      child: ListTile(
        leading: Icon(icon, color: AppColors.blue),
        title: Text(title, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
        subtitle: Text(detail, style: const TextStyle(fontSize: 11, color: AppColors.muted)),
        trailing: Icon(onTap != null ? Icons.edit_outlined : Icons.chevron_right_rounded, color: AppColors.muted, size: 20),
        onTap: onTap,
      ),
    ),
  );
}
