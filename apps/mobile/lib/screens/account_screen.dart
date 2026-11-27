import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

import '../data/customer_profile_repository.dart';
import '../theme/app_theme.dart';
import 'legal_page_screen.dart';

class AccountScreen extends StatefulWidget {
  const AccountScreen({super.key});

  @override
  State<AccountScreen> createState() => _AccountScreenState();
}

class _AccountScreenState extends State<AccountScreen> {
  final _profiles = CustomerProfileRepository();

  bool get _configured => Firebase.apps.isNotEmpty;

  void _editProfile(BuildContext context, CustomerProfile profile, User user) {
    final nameCtrl = TextEditingController(text: profile.name);
    final mobileCtrl = TextEditingController(text: profile.mobileNumber);
    final locationCtrl = TextEditingController(text: profile.location);
    final companyCtrl = TextEditingController(text: profile.companyName ?? '');
    final gstCtrl = TextEditingController(text: profile.gstNumber ?? '');
    final editFormKey = GlobalKey<FormState>();
    String selectedRole = profile.customerType;
    bool saving = false;
    String? editError;

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
              child: Form(
                key: editFormKey,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Text(
                      'Edit Profile & Business Details',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w800,
                        color: AppColors.ink,
                      ),
                    ),
                    const SizedBox(height: 14),
                    const Text(
                      'Account Role',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                        color: AppColors.muted,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        _RoleChip(
                          label: 'End User / Consumer',
                          selected: selectedRole == 'end_user',
                          onTap: () => setSheetState(() {
                            selectedRole = 'end_user';
                            editError = null;
                          }),
                        ),
                        _RoleChip(
                          label: 'Reseller',
                          selected: selectedRole == 'reseller',
                          onTap: () => setSheetState(() {
                            selectedRole = 'reseller';
                            editError = null;
                          }),
                        ),
                        _RoleChip(
                          label: 'EPC Contractor',
                          selected: selectedRole == 'epc',
                          onTap: () => setSheetState(() {
                            selectedRole = 'epc';
                            editError = null;
                          }),
                        ),
                        _RoleChip(
                          label: 'Distributor',
                          selected: selectedRole == 'distributor',
                          onTap: () => setSheetState(() {
                            selectedRole = 'distributor';
                            editError = null;
                          }),
                        ),
                      ],
                    ),
                    const SizedBox(height: 14),
                    TextFormField(
                      controller: nameCtrl,
                      textCapitalization: TextCapitalization.words,
                      validator: (value) => (value?.trim().length ?? 0) >= 2
                          ? null
                          : 'Enter your full name.',
                      decoration: const InputDecoration(
                        labelText: 'Full Name *',
                        prefixIcon: Icon(Icons.person_outline_rounded),
                      ),
                    ),
                    const SizedBox(height: 10),
                    TextFormField(
                      controller: mobileCtrl,
                      keyboardType: TextInputType.phone,
                      validator: (value) {
                        final clean = value?.trim() ?? '';
                        final digits = clean.replaceAll(RegExp(r'[^0-9]'), '');
                        if (!RegExp(r'^\+?[0-9()\-\s]+$').hasMatch(clean) ||
                            digits.length < 10 ||
                            digits.length > 15)
                          return 'Enter 10–15 digits with an optional country code.';
                        return null;
                      },
                      decoration: const InputDecoration(
                        labelText: 'Mobile Number *',
                        prefixIcon: Icon(Icons.phone_outlined),
                      ),
                    ),
                    const SizedBox(height: 10),
                    TextFormField(
                      controller: locationCtrl,
                      textCapitalization: TextCapitalization.words,
                      validator: (value) => (value?.trim().length ?? 0) >= 2
                          ? null
                          : 'Enter your city or location.',
                      decoration: const InputDecoration(
                        labelText: 'City / Location *',
                        prefixIcon: Icon(Icons.location_on_outlined),
                      ),
                    ),
                    if (isBusiness) ...[
                      const SizedBox(height: 10),
                      TextFormField(
                        controller: companyCtrl,
                        textCapitalization: TextCapitalization.words,
                        validator: (value) => (value?.trim().length ?? 0) >= 2
                            ? null
                            : 'Enter your company or business name.',
                        decoration: const InputDecoration(
                          labelText: 'Company / Business Name *',
                          prefixIcon: Icon(Icons.business_outlined),
                        ),
                      ),
                      const SizedBox(height: 10),
                      TextFormField(
                        controller: gstCtrl,
                        textCapitalization: TextCapitalization.characters,
                        inputFormatters: [
                          FilteringTextInputFormatter.allow(
                            RegExp(r'[0-9A-Za-z]'),
                          ),
                          LengthLimitingTextInputFormatter(15),
                        ],
                        maxLength: 15,
                        validator: (value) {
                          final gst = value?.trim().toUpperCase() ?? '';
                          return RegExp(
                                r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$',
                              ).hasMatch(gst)
                              ? null
                              : 'Enter a valid 15-character GSTIN.';
                        },
                        decoration: const InputDecoration(
                          labelText: 'GSTIN *',
                          prefixIcon: Icon(Icons.receipt_long_outlined),
                          counterText: '',
                        ),
                      ),
                    ],
                    if (editError != null) ...[
                      const SizedBox(height: 10),
                      Text(
                        editError!,
                        style: const TextStyle(color: Colors.red, fontSize: 12),
                      ),
                    ],
                    const SizedBox(height: 16),
                    FilledButton(
                      onPressed: saving
                          ? null
                          : () async {
                              if (!editFormKey.currentState!.validate()) return;
                              setSheetState(() {
                                saving = true;
                                editError = null;
                              });
                              try {
                                await _profiles.save({
                                  'customer_type': selectedRole,
                                  'name': nameCtrl.text.trim(),
                                  'mobile_number': mobileCtrl.text.trim(),
                                  'email': user.email ?? profile.email,
                                  'location': locationCtrl.text.trim(),
                                  'company_name': isBusiness
                                      ? companyCtrl.text.trim()
                                      : null,
                                  'gst_number': isBusiness
                                      ? gstCtrl.text.trim().toUpperCase()
                                      : null,
                                }, userUid: user.uid);
                                if (ctx.mounted) Navigator.of(ctx).pop();
                                if (mounted) setState(() {});
                              } catch (_) {
                                if (ctx.mounted) {
                                  setSheetState(() {
                                    saving = false;
                                    editError = 'Your profile could not be saved. Check your connection and try again.';
                                  });
                                }
                              }
                            },
                      child: saving
                          ? const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.white,
                              ),
                            )
                          : const Text('Save Changes'),
                    ),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
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
    return const Center(
      child: Padding(
        padding: EdgeInsets.all(24),
        child: Text(
          'Your session has ended. Use the app sign-in screen to access your account.',
          textAlign: TextAlign.center,
          style: TextStyle(color: AppColors.muted, fontSize: 14),
        ),
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

        final initial =
            (profile?.name.isNotEmpty == true
                    ? profile!.name
                    : (user.displayName ?? user.email ?? 'E'))
                .substring(0, 1)
                .toUpperCase();

        return ListView(
          padding: const EdgeInsets.fromLTRB(20, 20, 20, 32),
          children: [
            const Text(
              'Account',
              style: TextStyle(
                color: AppColors.ink,
                fontSize: 24,
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 5),
            const Text(
              'Manage your profile and business details.',
              style: TextStyle(color: AppColors.muted, fontSize: 13),
            ),
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
                          style: const TextStyle(
                            color: AppColors.blue,
                            fontWeight: FontWeight.w800,
                            fontSize: 22,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            profile?.name.isNotEmpty == true
                                ? profile!.name
                                : (user.displayName ?? 'EnerTech Customer'),
                            style: const TextStyle(
                              color: AppColors.ink,
                              fontWeight: FontWeight.w800,
                              fontSize: 17,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            user.email ?? profile?.email ?? '',
                            style: const TextStyle(
                              color: AppColors.muted,
                              fontSize: 13,
                            ),
                          ),
                          const SizedBox(height: 6),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 10,
                              vertical: 3,
                            ),
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

            const SizedBox(height: 16),
            const Text(
              'PROFILE DETAILS',
              style: TextStyle(
                color: AppColors.muted,
                fontSize: 11,
                fontWeight: FontWeight.w700,
                letterSpacing: 0.5,
              ),
            ),
            const SizedBox(height: 8),

            // Profile Fields
            _AccountAction(
              icon: Icons.badge_outlined,
              title: 'Account Role',
              detail: roleText,
              onTap: profile != null
                  ? () => _editProfile(context, profile, user)
                  : null,
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
              detail: profile?.mobileNumber.isNotEmpty == true
                  ? profile!.mobileNumber
                  : 'Add mobile number',
              onTap: profile != null
                  ? () => _editProfile(context, profile, user)
                  : null,
            ),
            if (profile?.isBusiness == true) ...[
              _AccountAction(
                icon: Icons.business_outlined,
                title: 'Company Name',
                detail: profile?.companyName?.isNotEmpty == true
                    ? profile!.companyName!
                    : 'Add company name',
                onTap: profile != null
                    ? () => _editProfile(context, profile, user)
                    : null,
              ),
              _AccountAction(
                icon: Icons.receipt_long_outlined,
                title: 'GST Number (GSTIN)',
                detail: profile?.gstNumber?.isNotEmpty == true
                    ? profile!.gstNumber!
                    : 'Add GSTIN',
                onTap: profile != null
                    ? () => _editProfile(context, profile, user)
                    : null,
              ),
            ],
            _AccountAction(
              icon: Icons.location_on_outlined,
              title: 'Location / City',
              detail: profile?.location.isNotEmpty == true
                  ? profile!.location
                  : 'Add location',
              onTap: profile != null
                  ? () => _editProfile(context, profile, user)
                  : null,
            ),

            const SizedBox(height: 20),

            const Text('LEGAL', style: TextStyle(color: AppColors.muted, fontSize: 11, fontWeight: FontWeight.w700, letterSpacing: 0.5)),
            const SizedBox(height: 8),
            _AccountAction(icon: Icons.privacy_tip_outlined, title: 'Privacy Policy', detail: 'View the current policy', onTap: () => openLegalPage(context, 'privacy-policy')),
            _AccountAction(icon: Icons.description_outlined, title: 'Terms of Use', detail: 'View the current terms', onTap: () => openLegalPage(context, 'terms')),
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
  const _RoleChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });
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
        title: Text(
          title,
          style: const TextStyle(
            color: AppColors.muted,
            fontSize: 11,
            fontWeight: FontWeight.w600,
          ),
        ),
        subtitle: Text(
          detail,
          style: const TextStyle(
            color: AppColors.ink,
            fontSize: 14,
            fontWeight: FontWeight.w700,
          ),
        ),
        trailing: onTap != null
            ? const Icon(Icons.edit_outlined, size: 18, color: AppColors.muted)
            : null,
        onTap: onTap,
      ),
    ),
  );
}
