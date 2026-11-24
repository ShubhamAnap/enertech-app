import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:material_ui/material_ui.dart';

import '../data/customer_profile_repository.dart';
import '../theme/app_theme.dart';

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
    String? _error;

  bool get _configured => Firebase.apps.isNotEmpty;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  void _editProfile(BuildContext context, CustomerProfile profile, User user) {
    final nameCtrl = TextEditingController(text: profile.name);
    final mobileCtrl = TextEditingController(text: profile.mobileNumber);
    final locationCtrl = TextEditingController(text: profile.location);
    final companyCtrl = TextEditingController(text: profile.companyName ?? '');
    final gstCtrl = TextEditingController(text: profile.gstNumber ?? '');
    String selectedRole = profile.customerType;
    String? sheetError;

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
                    'Edit Profile & Business Details',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: AppColors.ink),
                  ),
                  const SizedBox(height: 14),
                  const Text('Account Role', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: AppColors.muted)),
                  const SizedBox(height: 6),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      _RoleChip(
                        label: 'End User / Consumer',
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
                  const SizedBox(height: 14),
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
                    decoration: const InputDecoration(labelText: 'City / Location *', prefixIcon: Icon(Icons.location_on_outlined)),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: companyCtrl,
                    decoration: InputDecoration(
                      labelText: isBusiness ? 'Company Name *' : 'Company Name (Optional)',
                      prefixIcon: const Icon(Icons.business_outlined),
                    ),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: gstCtrl,
                    textCapitalization: TextCapitalization.characters,
                    maxLength: 15,
                    decoration: InputDecoration(
                      labelText: isBusiness ? 'GST Number (15 chars) *' : 'GST Number (Optional)',
                      prefixIcon: const Icon(Icons.receipt_long_outlined),
                      counterText: '',
                    ),
                  ),
                  if (sheetError != null) ...[
                    const SizedBox(height: 8),
                    Text(sheetError!, style: const TextStyle(color: Colors.red, fontSize: 12)),
                  ],
                  const SizedBox(height: 16),
                  FilledButton(
                    onPressed: () async {
                      final name = nameCtrl.text.trim();
                      final mobile = mobileCtrl.text.trim();
                      final loc = locationCtrl.text.trim();
                      final comp = companyCtrl.text.trim();
                      final gst = gstCtrl.text.trim().toUpperCase();

                      if (name.isEmpty || mobile.isEmpty || loc.isEmpty) {
                        setSheetState(() => sheetError = 'Name, mobile, and location are required.');
                        return;
                      }
                      if (isBusiness) {
                        if (comp.isEmpty) {
                          setSheetState(() => sheetError = 'Company name is required for business accounts.');
                          return;
                        }
                        if (gst.length != 15) {
                          setSheetState(() => sheetError = 'Enter a valid 15-character GST Number.');
                          return;
                        }
                      }

                      await _profiles.save({
                        'customer_type': selectedRole,
                        'name': name,
                        'mobile_number': mobile,
                        'email': user.email ?? profile.email,
                        'location': loc,
                        'company_name': comp.isNotEmpty ? comp : null,
                        'gst_number': gst.isNotEmpty ? gst : null,
                      }, userUid: user.uid);

                      if (ctx.mounted) Navigator.of(ctx).pop();
                      if (mounted) setState(() {});
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

  Future<void> _submitAuth() async {
    FocusScope.of(context).unfocus();
    final email = _email.text.trim();
    final password = _password.text;
    if (email.isEmpty || !email.contains('@')) {
      setState(() => _error = 'Enter a valid email address.');
      return;
    }
    if (password.length < 6) {
      setState(() => _error = 'Password must be at least 6 characters.');
      return;
    }
    setState(() {
      _working = true;
      _error = null;
    });
    try {
      final auth = FirebaseAuth.instance;
      if (_createAccount) {
        await auth.createUserWithEmailAndPassword(email: email, password: password);
      } else {
        await auth.signInWithEmailAndPassword(email: email, password: password);
      }
    } on FirebaseAuthException catch (e) {
      setState(() => _error = e.message ?? 'Authentication failed.');
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!_configured) {
      return const Center(child: Text('Firebase not configured.'));
    }

    return StreamBuilder<User?>(
      stream: FirebaseAuth.instance.userChanges(),
      builder: (context, snapshot) {
        final user = snapshot.data;
        if (user == null) {
          return _buildSignedOutView();
        }
        return _buildSignedInView(user);
      },
    );
  }

  Widget _buildSignedOutView() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(22),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text('Account', style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800, color: AppColors.ink)),
          const SizedBox(height: 6),
          const Text('Sign in to manage your profile and view requests.', style: TextStyle(color: AppColors.muted, fontSize: 13)),
          const SizedBox(height: 20),
          TextField(
            controller: _email,
            keyboardType: TextInputType.emailAddress,
            decoration: const InputDecoration(labelText: 'Email address', prefixIcon: Icon(Icons.mail_outline_rounded)),
          ),
          const SizedBox(height: 10),
          TextField(
            controller: _password,
            obscureText: true,
            decoration: const InputDecoration(labelText: 'Password', prefixIcon: Icon(Icons.lock_outline_rounded)),
          ),
          if (_error != null) ...[
            const SizedBox(height: 10),
            Text(_error!, style: const TextStyle(color: Colors.red, fontSize: 12)),
          ],
          const SizedBox(height: 16),
          FilledButton(
            onPressed: _working ? null : _submitAuth,
            child: _working ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white)) : Text(_createAccount ? 'Create Account' : 'Sign In'),
          ),
          TextButton(
            onPressed: () => setState(() => _createAccount = !_createAccount),
            child: Text(_createAccount ? 'Already have an account? Sign in' : 'New to EnerTech? Create an account'),
          ),
        ],
      ),
    );
  }

  Widget _buildSignedInView(User user) {
    return FutureBuilder<CustomerProfile?>(
      future: _profiles.loadMine(userUid: user.uid),
      builder: (context, profileSnapshot) {
        final profile = profileSnapshot.data;
        final role = profile?.customerType ?? 'end_user';
        final roleText = switch (role) {
          'reseller' => 'Reseller Partner',
          'epc' => 'EPC Contractor',
          'distributor' => 'Authorized Distributor',
          _ => 'End User / Consumer',
        };

        final initial = (profile?.name.isNotEmpty == true ? profile!.name : (user.displayName ?? user.email ?? 'E')).substring(0, 1).toUpperCase();

        return ListView(
          padding: const EdgeInsets.fromLTRB(20, 20, 20, 32),
          children: [
            const Text('Account', style: TextStyle(color: AppColors.ink, fontSize: 24, fontWeight: FontWeight.w800)),
            const SizedBox(height: 5),
            const Text('Manage your profile and business details.', style: TextStyle(color: AppColors.muted, fontSize: 13)),
            const SizedBox(height: 16),

            // User Identity Card
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Row(
                  children: [
                    Container(
                      width: 54,
                      height: 54,
                      decoration: BoxDecoration(
                        color: const Color(0xFFEAF3FA),
                        borderRadius: BorderRadius.circular(16),
                      ),
                      child: Center(
                        child: Text(
                          initial,
                          style: const TextStyle(color: AppColors.blue, fontWeight: FontWeight.w800, fontSize: 22),
                        ),
                      ),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            profile?.name.isNotEmpty == true ? profile!.name : (user.displayName ?? 'EnerTech Customer'),
                            style: const TextStyle(color: AppColors.ink, fontWeight: FontWeight.w800, fontSize: 17),
                          ),
                          const SizedBox(height: 2),
                          Text(user.email ?? profile?.email ?? '', style: const TextStyle(color: AppColors.muted, fontSize: 13)),
                          const SizedBox(height: 6),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                            decoration: BoxDecoration(
                              color: AppColors.blue.withValues(alpha: 0.1),
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: Text(
                              roleText,
                              style: const TextStyle(color: AppColors.blue, fontWeight: FontWeight.w700, fontSize: 11),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 16),
            const Text('PROFILE DETAILS', style: TextStyle(color: AppColors.muted, fontSize: 11, fontWeight: FontWeight.w700, letterSpacing: 0.5)),
            const SizedBox(height: 8),

            // Profile Fields
            _AccountAction(
              icon: Icons.badge_outlined,
              title: 'Account Role',
              detail: roleText,
              onTap: profile != null ? () => _editProfile(context, profile, user) : null,
            ),
            _AccountAction(
              icon: Icons.mail_outline_rounded,
              title: 'Email Address',
              detail: user.email ?? profile?.email ?? 'Not provided',
              onTap: null, // Email managed via auth
            ),
            _AccountAction(
              icon: Icons.phone_outlined,
              title: 'Mobile Number',
              detail: profile?.mobileNumber.isNotEmpty == true ? profile!.mobileNumber : 'Add mobile number',
              onTap: profile != null ? () => _editProfile(context, profile, user) : null,
            ),
            _AccountAction(
              icon: Icons.business_outlined,
              title: 'Company Name',
              detail: profile?.companyName?.isNotEmpty == true ? profile!.companyName! : 'Add company name',
              onTap: profile != null ? () => _editProfile(context, profile, user) : null,
            ),
            _AccountAction(
              icon: Icons.receipt_long_outlined,
              title: 'GST Number (GSTIN)',
              detail: profile?.gstNumber?.isNotEmpty == true ? profile!.gstNumber! : 'Add GSTIN',
              onTap: profile != null ? () => _editProfile(context, profile, user) : null,
            ),
            _AccountAction(
              icon: Icons.location_on_outlined,
              title: 'Location / City',
              detail: profile?.location.isNotEmpty == true ? profile!.location : 'Add location',
              onTap: profile != null ? () => _editProfile(context, profile, user) : null,
            ),

            const SizedBox(height: 20),

            // Edit Profile Button
            if (profile != null)
              FilledButton.icon(
                onPressed: () => _editProfile(context, profile, user),
                icon: const Icon(Icons.edit_note_rounded, size: 20),
                label: const Text('Edit Profile & Business Details'),
              ),

            const SizedBox(height: 12),

            // Sign Out
            OutlinedButton.icon(
              onPressed: () {
                CustomerProfileRepository.clearCache();
                FirebaseAuth.instance.signOut();
              },
              icon: const Icon(Icons.logout_rounded, size: 18),
              label: const Text('Sign out'),
            ),
          ],
        );
      },
    );
  }
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
    padding: const EdgeInsets.only(bottom: 8),
    child: Card(
      child: ListTile(
        leading: Container(
          width: 38,
          height: 38,
          decoration: BoxDecoration(
            color: const Color(0xFFF4F8FB),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Icon(icon, color: AppColors.blue, size: 20),
        ),
        title: Text(title, style: const TextStyle(color: AppColors.muted, fontSize: 11, fontWeight: FontWeight.w600)),
        subtitle: Text(detail, style: const TextStyle(color: AppColors.ink, fontSize: 14, fontWeight: FontWeight.w700)),
        trailing: onTap != null ? const Icon(Icons.edit_outlined, size: 18, color: AppColors.muted) : null,
        onTap: onTap,
      ),
    ),
  );
}
