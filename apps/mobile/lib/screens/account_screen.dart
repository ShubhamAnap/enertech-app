import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:material_ui/material_ui.dart';

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

  Future<void> _submit() async {
    setState(() { _working = true; _error = null; _message = null; });
    try {
      final auth = FirebaseAuth.instance;
      if (_createAccount) {
        final credential = await auth.createUserWithEmailAndPassword(email: _email.text.trim(), password: _password.text);
        await credential.user?.sendEmailVerification();
        setState(() => _message = 'Account created. Check your inbox to verify your email.');
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
      setState(() { _error = null; _message = 'Password reset instructions have been sent.'; });
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
      FilledButton(onPressed: _working ? null : _submit, child: _working ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2)) : Text(_createAccount ? 'Create account' : 'Sign in')),
      TextButton(onPressed: () => setState(() { _createAccount = !_createAccount; _error = null; _message = null; }), child: Text(_createAccount ? 'Already have an account? Sign in' : 'New to EnerTech? Create an account')),
      if (!_createAccount) TextButton(onPressed: _resetPassword, child: const Text('Forgot password?')),
    ]))),
    const SizedBox(height: 10),
    const NoticeCard(message: 'Your sign-in is handled by Firebase. The app never stores passwords or database keys.'),
  ]);

  Widget _buildAccount(User user) => ListView(padding: const EdgeInsets.fromLTRB(20, 22, 20, 28), children: [
    const Text('Account', style: TextStyle(color: AppColors.ink, fontSize: 24, fontWeight: FontWeight.w800)),
    const SizedBox(height: 5),
    const Text('Manage your profile and preferences.', style: TextStyle(color: AppColors.muted, fontSize: 13)),
    const SizedBox(height: 18),
    Card(child: Padding(padding: const EdgeInsets.all(16), child: Row(children: [
      Container(width: 48, height: 48, decoration: BoxDecoration(color: const Color(0xFFEAF3FA), borderRadius: BorderRadius.circular(16)), child: const Icon(Icons.person_outline_rounded, color: AppColors.blue)),
      const SizedBox(width: 12),
      Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(user.displayName ?? 'EnerTech customer', style: const TextStyle(color: AppColors.ink, fontWeight: FontWeight.w700)), const SizedBox(height: 3), Text(user.email ?? '', style: const TextStyle(color: AppColors.muted, fontSize: 12)), Text(user.emailVerified ? 'Email verified' : 'Email verification pending', style: const TextStyle(color: AppColors.muted, fontSize: 11))])),
    ]))),
    const SizedBox(height: 14),
    const NoticeCard(message: 'Your requests and service history will appear here as those workflows are connected.'),
    const SizedBox(height: 15),
    const _AccountAction(icon: Icons.business_outlined, title: 'Business profile', detail: 'Profile storage is not configured yet'),
    const _AccountAction(icon: Icons.location_on_outlined, title: 'Project locations', detail: 'Address storage is not configured yet'),
    const _AccountAction(icon: Icons.notifications_outlined, title: 'Notifications', detail: 'Preferences are not connected'),
    const _AccountAction(icon: Icons.privacy_tip_outlined, title: 'Privacy & settings', detail: 'Policy content has not been supplied'),
    const SizedBox(height: 8),
    OutlinedButton.icon(onPressed: () => FirebaseAuth.instance.signOut(), icon: const Icon(Icons.logout_rounded), label: const Text('Sign out')),
  ]);
}

class _AccountAction extends StatelessWidget {
  const _AccountAction({required this.icon, required this.title, required this.detail});
  final IconData icon;
  final String title;
  final String detail;
  @override
  Widget build(BuildContext context) => Padding(padding: const EdgeInsets.only(bottom: 9), child: Card(child: ListTile(leading: Icon(icon, color: AppColors.blue), title: Text(title, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)), subtitle: Text(detail, style: const TextStyle(fontSize: 11)), trailing: const Icon(Icons.chevron_right_rounded, color: AppColors.muted), onTap: null)));
}
