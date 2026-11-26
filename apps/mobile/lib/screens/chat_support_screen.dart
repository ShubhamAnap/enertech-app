import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:webview_flutter/webview_flutter.dart';

import '../theme/app_theme.dart';
import '../widgets/app_components.dart';
import 'service_request_screen.dart';
import 'solution_finder_screen.dart';

class ChatSupportScreen extends StatelessWidget {
  const ChatSupportScreen({super.key, required this.appContent});
  final Future<Map<String, dynamic>> appContent;

  Future<void> _launch(String url) async {
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Support Desk'),
      leading: const BackButton(),
    ),
    body: FutureBuilder<Map<String, dynamic>>(
      future: appContent,
      builder: (context, snapshot) {
        final contacts = snapshot.data?['contacts'] is Map
            ? snapshot.data!['contacts'] as Map
            : const <String, dynamic>{};
        final phone = (contacts['support_phone'] as String? ?? '').replaceAll(
          RegExp(r'[^0-9+]'),
          '',
        );
        final whatsapp = (contacts['whatsapp_number'] as String? ?? '')
            .replaceAll(RegExp(r'[^0-9]'), '');
        final email = (contacts['support_email'] as String? ?? '').trim();
        final hours = contacts['support_hours'] as String? ?? '';
        final chat = snapshot.data?['chat'] is Map
            ? snapshot.data!['chat'] as Map
            : const <String, dynamic>{};
        final chatUrl = Uri.tryParse(chat['embed_url'] as String? ?? '');
        final allowedHosts = chat['allowed_hosts'] is List
            ? (chat['allowed_hosts'] as List)
                  .whereType<String>()
                  .map((host) => host.toLowerCase())
                  .toSet()
            : <String>{};
        final chatEnabled =
            chat['enabled'] == true &&
            chatUrl != null &&
            chatUrl.scheme == 'https' &&
            allowedHosts.contains(chatUrl.host.toLowerCase());
        final handoffUrl = Uri.tryParse(
          chat['human_handoff_url'] as String? ?? '',
        );
        final handoffEnabled =
            chat['human_handoff_enabled'] == true &&
            handoffUrl != null &&
            handoffUrl.scheme == 'https' &&
            allowedHosts.contains(handoffUrl.host.toLowerCase());
        final welcomeMessage = (chat['welcome_message'] as String? ?? '')
            .trim();
        final fallbackMessage = (chat['fallback_message'] as String? ?? '')
            .trim();
        final brand = snapshot.data?['brand'] is Map
            ? snapshot.data!['brand'] as Map
            : const <String, dynamic>{};
        final supportIconUrl = Uri.tryParse(
          brand['support_icon_url'] as String? ?? '',
        );
        WebViewController? chatController;
        if (chatEnabled) {
          chatController = WebViewController()
            ..setJavaScriptMode(JavaScriptMode.unrestricted)
            ..setNavigationDelegate(
              NavigationDelegate(
                onNavigationRequest: (request) {
                  final requested = Uri.tryParse(request.url);
                  if (requested?.scheme == 'https' &&
                      allowedHosts.contains(requested!.host.toLowerCase())) {
                    return NavigationDecision.navigate;
                  }
                  return NavigationDecision.prevent;
                },
              ),
            )
            ..loadRequest(chatUrl);
        }

        return ListView(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
          children: [
            // Header Card
            Container(
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                color: const Color(0xFFF0F6FB),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: const Color(0xFFD6E4F0)),
              ),
              child: Row(
                children: [
                  Container(
                    width: 48,
                    height: 48,
                    decoration: BoxDecoration(
                      color: AppColors.blue,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child:
                        supportIconUrl != null &&
                            supportIconUrl.scheme == 'https'
                        ? Image.network(
                            supportIconUrl.toString(),
                            fit: BoxFit.cover,
                            errorBuilder: (_, _, _) => const Icon(
                              Icons.support_agent_rounded,
                              color: Colors.white,
                              size: 28,
                            ),
                          )
                        : const Icon(
                            Icons.support_agent_rounded,
                            color: Colors.white,
                            size: 28,
                          ),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'EnerTech Support Desk',
                          style: TextStyle(
                            fontWeight: FontWeight.w800,
                            fontSize: 16,
                            color: AppColors.ink,
                          ),
                        ),
                        const SizedBox(height: 3),
                        Text(
                          hours.isEmpty
                              ? 'Use one of the verified contact channels below.'
                              : hours,
                          style: const TextStyle(
                            fontSize: 12,
                            color: AppColors.muted,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),

            if (welcomeMessage.isNotEmpty) ...[
              const SizedBox(height: 12),
              NoticeCard(message: welcomeMessage),
            ],

            if (chatEnabled) ...[
              const SizedBox(height: 18),
              const Text(
                'LIVE CHAT',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  color: AppColors.muted,
                  letterSpacing: 0.5,
                ),
              ),
              const SizedBox(height: 10),
              SizedBox(
                height: 420,
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(14),
                  child: WebViewWidget(controller: chatController!),
                ),
              ),
              if (fallbackMessage.isNotEmpty) ...[
                const SizedBox(height: 10),
                Text(
                  fallbackMessage,
                  style: const TextStyle(fontSize: 12, color: AppColors.muted),
                ),
              ],
              if (handoffEnabled) ...[
                const SizedBox(height: 10),
                OutlinedButton.icon(
                  onPressed: () => _launch(handoffUrl.toString()),
                  icon: const Icon(Icons.support_agent_rounded),
                  label: const Text('Talk to a person'),
                ),
              ],
            ] else if (fallbackMessage.isNotEmpty) ...[
              const SizedBox(height: 12),
              NoticeCard(message: fallbackMessage),
            ],

            const SizedBox(height: 20),
            const Text(
              'DIRECT CONTACT CHANNELS',
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w700,
                color: AppColors.muted,
                letterSpacing: 0.5,
              ),
            ),
            const SizedBox(height: 10),

            // Call Helpline
            if (phone.isNotEmpty)
              _SupportChannelCard(
                icon: Icons.phone_in_talk_rounded,
                color: const Color(0xFF2563EB),
                title: 'Customer Helpline',
                subtitle: 'Speak with technical support engineer',
                actionLabel: 'Call Now',
                onTap: () => _launch('tel:$phone'),
              ),

            // WhatsApp Chat
            if (whatsapp.isNotEmpty)
              _SupportChannelCard(
                icon: Icons.chat_rounded,
                color: const Color(0xFF16A34A),
                title: 'WhatsApp Support',
                subtitle: 'Quick chat, share photos or alarm codes',
                actionLabel: 'Chat on WhatsApp',
                onTap: () => _launch(
                  'https://wa.me/$whatsapp?text=Hello%20EnerTech%20Support,%20I%20need%20assistance.',
                ),
              ),

            // Email Support
            if (email.isNotEmpty)
              _SupportChannelCard(
                icon: Icons.mail_outline_rounded,
                color: const Color(0xFF9333EA),
                title: 'Email Support',
                subtitle: email,
                actionLabel: 'Send Email',
                onTap: () => _launch(
                  'mailto:$email?subject=EnerTech%20Customer%20Support',
                ),
              ),

            const SizedBox(height: 20),
            const Text(
              'SELF-SERVICE REQUESTS',
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w700,
                color: AppColors.muted,
                letterSpacing: 0.5,
              ),
            ),
            const SizedBox(height: 10),

            // Raise Service Ticket
            Card(
              child: ListTile(
                leading: Container(
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(
                    color: const Color(0xFFFFF7ED),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(
                    Icons.handyman_outlined,
                    color: Color(0xFFEA580C),
                    size: 22,
                  ),
                ),
                title: const Text(
                  'Log Service / Repair Ticket',
                  style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14),
                ),
                subtitle: const Text(
                  'Submit model, serial number, and issue details',
                  style: TextStyle(fontSize: 12, color: AppColors.muted),
                ),
                trailing: const Icon(Icons.chevron_right_rounded),
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => const ServiceRequestScreen(),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 8),

            // Request Quote
            Card(
              child: ListTile(
                leading: Container(
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(
                    color: const Color(0xFFEFF6FF),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(
                    Icons.request_quote_outlined,
                    color: Color(0xFF2563EB),
                    size: 22,
                  ),
                ),
                title: const Text(
                  'Request Quotation / Solution',
                  style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14),
                ),
                subtitle: const Text(
                  'Get customized commercial pricing from EnerTech sales',
                  style: TextStyle(fontSize: 12, color: AppColors.muted),
                ),
                trailing: const Icon(Icons.chevron_right_rounded),
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => const SolutionFinderScreen(),
                  ),
                ),
              ),
            ),

            const SizedBox(height: 22),

            // Emergency Safety Protocol
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: const Color(0xFFFEF2F2),
                border: Border.all(color: const Color(0xFFFECACA)),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(
                    Icons.warning_amber_rounded,
                    color: Color(0xFFDC2626),
                    size: 22,
                  ),
                  SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Electrical Safety Precaution',
                          style: TextStyle(
                            fontWeight: FontWeight.w700,
                            color: Color(0xFF991B1B),
                            fontSize: 13,
                          ),
                        ),
                        SizedBox(height: 4),
                        Text(
                          'If there is smoke, burning smell, unusual heat, or exposed wiring: immediately switch off input mains, evacuate the area, and contact qualified EnerTech personnel.',
                          style: TextStyle(
                            fontSize: 12,
                            color: Color(0xFF7F1D1D),
                            height: 1.4,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],
        );
      },
    ),
  );
}

class _SupportChannelCard extends StatelessWidget {
  const _SupportChannelCard({
    required this.icon,
    required this.color,
    required this.title,
    required this.subtitle,
    required this.actionLabel,
    required this.onTap,
  });

  final IconData icon;
  final Color color;
  final String title;
  final String subtitle;
  final String actionLabel;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 10),
    child: Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          children: [
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(icon, color: color, size: 24),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      fontWeight: FontWeight.w700,
                      fontSize: 14,
                      color: AppColors.ink,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    subtitle,
                    style: const TextStyle(
                      fontSize: 12,
                      color: AppColors.muted,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            FilledButton.tonal(
              onPressed: onTap,
              style: FilledButton.styleFrom(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 8,
                ),
                minimumSize: const Size(0, 36),
              ),
              child: Text(
                actionLabel,
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ],
        ),
      ),
    ),
  );
}
