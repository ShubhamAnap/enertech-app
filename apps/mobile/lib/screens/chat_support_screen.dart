import 'dart:convert';

import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:webview_flutter/webview_flutter.dart';

import '../theme/app_theme.dart';
import '../widgets/app_components.dart';

class ChatSupportScreen extends StatelessWidget {
  const ChatSupportScreen({super.key, required this.appContent});
  final Future<Map<String, dynamic>> appContent;

  @override
  Widget build(BuildContext context) => FutureBuilder<Map<String, dynamic>>(future: appContent, builder: (context, snapshot) {
    final config = snapshot.data?['chat'] is Map ? snapshot.data!['chat'] as Map : const <String, dynamic>{};
    final enabled = config['enabled'] == true;
    final embedUrl = Uri.tryParse(config['embed_url'] as String? ?? '');
    final scriptUrl = Uri.tryParse(config['widget_script_url'] as String? ?? '');
    final widgetKey = config['provider_key'] as String? ?? '';
    final integration = config['integration'] as String? ?? 'iframe';
    final allowedHosts = (config['allowed_hosts'] as List<dynamic>? ?? const []).whereType<String>().map((host) => host.toLowerCase()).toSet();
    final welcome = config['welcome_message'] as String? ?? '';
    final fallback = config['fallback_message'] as String? ?? '';
    final handoff = Uri.tryParse(config['human_handoff_url'] as String? ?? '');
    bool allowed(Uri? uri) => uri != null && uri.scheme == 'https' && allowedHosts.contains(uri.host.toLowerCase());
    final hostedWidget = integration == 'hosted_widget';
    final trustedEmbed = enabled && allowed(embedUrl) && (!hostedWidget || (allowed(scriptUrl) && widgetKey.isNotEmpty));
    WebViewController? controller;
    if (trustedEmbed) {
      controller = WebViewController()
        ..setJavaScriptMode(JavaScriptMode.unrestricted)
        ..setNavigationDelegate(NavigationDelegate(onNavigationRequest: (request) {
          final target = Uri.tryParse(request.url);
          return allowed(target) ? NavigationDecision.navigate : NavigationDecision.prevent;
        }));
      if (hostedWidget) {
        controller.loadHtmlString(_widgetDocument(scriptUrl!, embedUrl!, widgetKey), baseUrl: embedUrl.toString());
      } else {
        controller.loadRequest(embedUrl!);
      }
    }
    return Scaffold(
    appBar: AppBar(title: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(enabled ? 'EnerBot Support' : 'Support assistant', style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)), Text(trustedEmbed ? 'Connected support' : 'Not connected', style: const TextStyle(fontSize: 10, color: AppColors.muted, fontWeight: FontWeight.w400))]), actions: [if (config['human_handoff_enabled'] == true && handoff != null && handoff.scheme == 'https') IconButton(tooltip: 'Human support', onPressed: () => launchUrl(handoff, mode: LaunchMode.externalApplication), icon: const Icon(Icons.headset_mic_outlined))]),
    body: trustedEmbed && controller != null ? Column(children: [
      if (welcome.isNotEmpty) Padding(padding: const EdgeInsets.fromLTRB(16, 10, 16, 0), child: Align(alignment: Alignment.centerLeft, child: Text(welcome, style: const TextStyle(color: AppColors.muted, fontSize: 12)))),
      Expanded(child: WebViewWidget(controller: controller)),
    ]) : Column(children: [
      Expanded(child: ListView(padding: const EdgeInsets.all(18), children: [
        NoticeCard(message: fallback.isNotEmpty ? fallback : 'EnerBot is not connected to an approved knowledge source in this build. No troubleshooting answers are generated.'),
        const SizedBox(height: 16),
        const _ChatNotice(),
        const SizedBox(height: 14),
        const NoticeCard(icon: Icons.warning_amber_rounded, message: 'If there is smoke, burning smell, unusual heat, exposed wiring, or electrical danger: move away, do not touch the equipment, and contact qualified service personnel.'),
      ])),
      const Divider(height: 1),
      SafeArea(top: false, child: Padding(padding: const EdgeInsets.fromLTRB(16, 11, 16, 12), child: Column(children: [
        Row(children: [
          Expanded(child: OutlinedButton.icon(onPressed: null, icon: const Icon(Icons.add_photo_alternate_outlined), label: const Text('Upload photo'))),
          const SizedBox(width: 8),
          const IconButton(onPressed: null, tooltip: 'Send message', icon: Icon(Icons.send_rounded)),
        ]),
        const SizedBox(height: 7),
        const TextField(enabled: false, decoration: InputDecoration(hintText: 'Chat will be available when support is connected', isDense: true)),
      ]))),
    ]),
  );
  });
}

String _widgetDocument(Uri scriptUrl, Uri appUrl, String publicKey) {
  final escape = const HtmlEscape(HtmlEscapeMode.attribute).convert;
  return '<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta name="color-scheme" content="light"><style>html,body{width:100%;height:100%;margin:0;background:#f5f7fa;overflow:hidden}</style></head><body><script src="${escape(scriptUrl.toString())}" data-app-url="${escape(appUrl.toString())}" data-key="${escape(publicKey)}" async></script></body></html>';
}

class _ChatNotice extends StatelessWidget {
  const _ChatNotice();
  @override
  Widget build(BuildContext context) => Card(child: Padding(padding: const EdgeInsets.all(15), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    const Text('What support will ask for', style: TextStyle(color: AppColors.ink, fontSize: 14, fontWeight: FontWeight.w700)),
    const SizedBox(height: 10),
    for (final item in const ['Product model', 'Alarm or error code', 'What changed and when', 'Photo of the display or nameplate'])
      Padding(padding: const EdgeInsets.only(bottom: 7), child: Row(children: [const Icon(Icons.check_circle_outline_rounded, color: AppColors.blue, size: 17), const SizedBox(width: 8), Expanded(child: Text(item, style: const TextStyle(color: AppColors.muted, fontSize: 12)))])),
  ])));
}
