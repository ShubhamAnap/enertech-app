import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';

import '../theme/app_theme.dart';
import '../widgets/app_components.dart';
import 'chat_support_screen.dart';
import 'contact_inquiry_screen.dart';
import 'information_library_screen.dart';
import 'service_request_screen.dart';

class SupportScreen extends StatelessWidget {
  const SupportScreen({
    super.key,
    required this.appContent,
    required this.knowledge,
    required this.onNavigate,
  });
  final Future<Map<String, dynamic>> appContent;
  final Future<List<Map<String, dynamic>>> knowledge;
  final ValueChanged<int> onNavigate;

  void _unavailable(
    BuildContext context,
    String channel, {
    required String detail,
  }) {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('$channel unavailable'),
        content: Text(detail),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  Future<void> _openContact(
    BuildContext context,
    String value,
    String type,
  ) async {
    final contact = value.trim();
    if (contact.isEmpty) {
      _unavailable(
        context,
        type,
        detail:
            'An official $type channel has not been published in the app settings.',
      );
      return;
    }
    final uri = switch (type) {
      'WhatsApp' => Uri.parse(
        'https://wa.me/${contact.replaceAll(RegExp(r'[^0-9]'), '')}',
      ),
      'Email support' => Uri(scheme: 'mailto', path: contact),
      _ => Uri(scheme: 'tel', path: contact),
    };
    if (!await launchUrl(uri, mode: LaunchMode.externalApplication) &&
        context.mounted)
      _unavailable(
        context,
        type,
        detail:
            'This device could not open $type. Try another published support channel.',
      );
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<Map<String, dynamic>>(
    future: appContent,
    builder: (context, snapshot) {
      final contacts = snapshot.data?['contacts'] is Map
          ? snapshot.data!['contacts'] as Map
          : const <String, dynamic>{};
      final chat = snapshot.data?['chat'] is Map
          ? snapshot.data!['chat'] as Map
          : const <String, dynamic>{};
      final supportPhone = contacts['support_phone'] as String? ?? '';
      final salesPhone = contacts['sales_phone'] as String? ?? '';
      final whatsapp = contacts['whatsapp_number'] as String? ?? '';
      final supportEmail = contacts['support_email'] as String? ?? '';
      final salesEmail = contacts['sales_email'] as String? ?? '';
      final officeAddress = contacts['office_address'] as String? ?? '';
      final hours = contacts['support_hours'] as String? ?? '';
      final availability = contacts['availability_message'] as String? ?? '';
      final chatAvailable =
          chat['enabled'] == true &&
          (chat['embed_url'] as String? ?? '').isNotEmpty;
      return ListView(
        padding: const EdgeInsets.fromLTRB(20, 22, 20, 28),
        children: [
          const Text(
            'Support Centre',
            style: TextStyle(
              color: AppColors.ink,
              fontSize: 24,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 5),
          const Text(
            'How can we help you today?',
            style: TextStyle(color: AppColors.muted, fontSize: 13),
          ),
          const SizedBox(height: 17),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [AppColors.navy, Color(0xFF102C4D)],
              ),
              borderRadius: BorderRadius.circular(18),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Row(
                  children: [
                    Icon(
                      Icons.support_agent_rounded,
                      color: Color(0xFF9FE3F5),
                      size: 20,
                    ),
                    SizedBox(width: 8),
                    Text(
                      'Need technical assistance?',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 7),
                Text(
                  chatAvailable
                      ? 'Chat with EnerTech support or connect with our technical team.'
                      : availability.isNotEmpty
                      ? availability
                      : 'AI guidance and direct support will be available when verified knowledge and official channels are connected.',
                  style: const TextStyle(
                    color: Color(0xFFD3E0EC),
                    fontSize: 12,
                    height: 1.45,
                  ),
                ),
                const SizedBox(height: 13),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.tonalIcon(
                    style: FilledButton.styleFrom(
                      backgroundColor: Colors.white,
                      foregroundColor: AppColors.navy,
                    ),
                    onPressed: () => Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) =>
                            ChatSupportScreen(appContent: appContent),
                      ),
                    ),
                    icon: const Icon(Icons.chat_bubble_outline_rounded),
                    label: Text(
                      chatAvailable
                          ? 'Start support chat'
                          : 'Open EnerBot support',
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 19),
          const SectionTitle(title: 'Contact us'),
          const SizedBox(height: 8),
          GridView.count(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            crossAxisCount: 2,
            crossAxisSpacing: 9,
            mainAxisSpacing: 9,
            childAspectRatio: 1.7,
            children: [
              _ContactCard(
                icon: Icons.call_outlined,
                title: 'Call support',
                detail: supportPhone.isEmpty
                    ? 'Number not configured'
                    : supportPhone,
                onTap: () => _openContact(
                  context,
                  supportPhone.isEmpty ? salesPhone : supportPhone,
                  'Call support',
                ),
              ),
              _ContactCard(
                icon: Icons.chat_outlined,
                title: 'WhatsApp',
                detail: whatsapp.isEmpty
                    ? 'Official account not set'
                    : whatsapp,
                onTap: () => _openContact(context, whatsapp, 'WhatsApp'),
              ),
              _ContactCard(
                icon: Icons.mail_outline_rounded,
                title: 'Email support',
                detail: supportEmail.isEmpty
                    ? 'Address not configured'
                    : supportEmail,
                onTap: () =>
                    _openContact(context, supportEmail, 'Email support'),
              ),
              _ContactCard(
                icon: Icons.build_outlined,
                title: 'Service request',
                detail: 'Report a problem',
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => const ServiceRequestScreen(),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          OutlinedButton.icon(
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => const ContactInquiryScreen(),
              ),
            ),
            icon: const Icon(Icons.send_outlined),
            label: const Text('Send a message to EnerTech'),
          ),
          if (salesEmail.isNotEmpty) ...[
            const SizedBox(height: 10),
            Card(
              child: ListTile(
                leading: const Icon(
                  Icons.business_outlined,
                  color: AppColors.blue,
                ),
                title: const Text(
                  'Sales enquiries',
                  style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
                ),
                subtitle: Text(
                  salesEmail,
                  style: const TextStyle(fontSize: 11),
                ),
                onTap: () => _openContact(context, salesEmail, 'Email support'),
              ),
            ),
          ],
          if (officeAddress.isNotEmpty) ...[
            const SizedBox(height: 8),
            Card(
              child: ListTile(
                leading: const Icon(
                  Icons.location_on_outlined,
                  color: AppColors.blue,
                ),
                title: const Text(
                  'EnerTech office',
                  style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
                ),
                subtitle: Text(
                  officeAddress,
                  style: const TextStyle(fontSize: 11),
                ),
              ),
            ),
          ],
          const SizedBox(height: 19),
          const SectionTitle(title: 'Service resources'),
          const SizedBox(height: 8),
          Card(
            child: Column(
              children: [
                _SupportRow(
                  icon: Icons.track_changes_outlined,
                  title: 'Track service requests',
                  detail: 'View complaint status',
                  onTap: () => onNavigate(2),
                ),
                const Divider(height: 1, indent: 56),
                _SupportRow(
                  icon: Icons.menu_book_outlined,
                  title: 'Manuals & documents',
                  detail: 'Approved product documentation',
                  onTap: () => Navigator.of(context).push(
                    MaterialPageRoute<void>(
                      builder: (_) => const InformationLibraryScreen(
                        title: 'Manuals & documents',
                        icon: Icons.menu_book_outlined,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 19),
          if (hours.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Text(
                'Support hours: $hours',
                style: const TextStyle(color: AppColors.muted, fontSize: 11),
              ),
            ),
          FutureBuilder<List<Map<String, dynamic>>>(
            future: knowledge,
            builder: (context, faqSnapshot) {
              final articles =
                  faqSnapshot.data ?? const <Map<String, dynamic>>[];
              if (articles.isEmpty)
                return const NoticeCard(
                  message: 'Approved support answers will appear here when they are added and published in the CMS.',
                );
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const SectionTitle(title: 'Common questions'),
                  const SizedBox(height: 8),
                  ...articles.map(
                    (article) => Padding(
                      padding: const EdgeInsets.only(bottom: 7),
                      child: Card(
                        child: ListTile(
                          dense: true,
                          title: Text(
                            article['title'] as String? ?? 'Support answer',
                            style: const TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          subtitle: Text(
                            article['category'] as String? ?? '',
                            style: const TextStyle(fontSize: 10),
                          ),
                          trailing: const Icon(
                            Icons.chevron_right_rounded,
                            size: 18,
                            color: AppColors.muted,
                          ),
                          onTap: () => showDialog<void>(
                            context: context,
                            builder: (dialogContext) => AlertDialog(
                              title: Text(
                                article['title'] as String? ?? 'Support answer',
                              ),
                              content: SingleChildScrollView(
                                child: Text(article['answer'] as String? ?? ''),
                              ),
                              actions: [
                                TextButton(
                                  onPressed: () => Navigator.pop(dialogContext),
                                  child: const Text('Close'),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              );
            },
          ),
        ],
      );
    },
  );
}

class _ContactCard extends StatelessWidget {
  const _ContactCard({
    required this.icon,
    required this.title,
    required this.detail,
    required this.onTap,
  });
  final IconData icon;
  final String title;
  final String detail;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) => Card(
    child: InkWell(
      borderRadius: BorderRadius.circular(16),
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 19, color: AppColors.blue),
            const SizedBox(height: 7),
            Text(
              title,
              style: const TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w700,
                color: AppColors.ink,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              detail,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 10, color: AppColors.muted),
            ),
          ],
        ),
      ),
    ),
  );
}

class _SupportRow extends StatelessWidget {
  const _SupportRow({
    required this.icon,
    required this.title,
    required this.detail,
    required this.onTap,
  });
  final IconData icon;
  final String title;
  final String detail;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) => ListTile(
    onTap: onTap,
    leading: Container(
      width: 34,
      height: 34,
      decoration: BoxDecoration(
        color: const Color(0xFFF1F6FA),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Icon(icon, color: AppColors.blue, size: 17),
    ),
    title: Text(
      title,
      style: const TextStyle(
        fontSize: 12,
        color: AppColors.ink,
        fontWeight: FontWeight.w700,
      ),
    ),
    subtitle: Text(
      detail,
      style: const TextStyle(fontSize: 10, color: AppColors.muted),
    ),
    trailing: const Icon(
      Icons.chevron_right_rounded,
      color: AppColors.muted,
      size: 18,
    ),
  );
}

