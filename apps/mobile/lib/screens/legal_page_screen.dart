import 'package:material_ui/material_ui.dart';
import 'package:webview_flutter/webview_flutter.dart';

import '../data/legal_repository.dart';

class LegalPageScreen extends StatefulWidget {
  const LegalPageScreen({super.key, required this.title, required this.page});
  final String title;
  final String page;

  @override
  State<LegalPageScreen> createState() => _LegalPageScreenState();
}

class _LegalPageScreenState extends State<LegalPageScreen> {
  late final WebViewController _controller;
  bool _loading = true;
  bool _failed = false;

  @override
  void initState() {
    super.initState();
    _controller = WebViewController()
      ..setNavigationDelegate(NavigationDelegate(
        onPageFinished: (_) { if (mounted) setState(() => _loading = false); },
        onWebResourceError: (error) { if (error.isForMainFrame == true && mounted) setState(() { _loading = false; _failed = true; }); },
        onNavigationRequest: (request) {
          final target = Uri.tryParse(request.url);
          return target?.scheme == 'https' && target?.host == LegalRepository.pageUrl(widget.page).host
              ? NavigationDecision.navigate : NavigationDecision.prevent;
        },
      ))
      ..loadRequest(LegalRepository.pageUrl(widget.page));
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text(widget.title)),
    body: Stack(children: [
      if (!_failed) WebViewWidget(controller: _controller),
      if (_loading) const Center(child: CircularProgressIndicator()),
      if (_failed) Center(child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          const Text('This page could not be loaded. Check your connection and try again.'),
          TextButton(onPressed: () { setState(() { _loading = true; _failed = false; }); _controller.loadRequest(LegalRepository.pageUrl(widget.page)); }, child: const Text('Retry')),
        ]),
      )),
    ]),
  );
}

void openLegalPage(BuildContext context, String page) {
  Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => LegalPageScreen(
    title: page == 'privacy-policy' ? 'Privacy Policy' : 'Terms of Use', page: page,
  )));
}
