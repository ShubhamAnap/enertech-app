import 'dart:convert';

import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:webview_flutter/webview_flutter.dart';

import '../theme/app_theme.dart';

class FaqArticleScreen extends StatefulWidget {
  const FaqArticleScreen({super.key, required this.article});
  final Map<String, dynamic> article;

  @override
  State<FaqArticleScreen> createState() => _FaqArticleScreenState();
}

class _FaqArticleScreenState extends State<FaqArticleScreen> {
  final Map<String, WebViewController> _videoControllers = {};

  List<String> _urls(String key) =>
      (widget.article[key] as List<dynamic>? ?? const [])
          .whereType<String>()
          .where((value) => Uri.tryParse(value)?.scheme == 'https')
          .toList(growable: false);

  bool _directVideo(String url) {
    final path = Uri.tryParse(url)?.path.toLowerCase() ?? '';
    return path.endsWith('.mp4') || path.endsWith('.webm');
  }

  WebViewController _controller(
    String url,
  ) => _videoControllers.putIfAbsent(url, () {
    final safeUrl = const HtmlEscape(HtmlEscapeMode.attribute).convert(url);
    return WebViewController()
      ..setJavaScriptMode(JavaScriptMode.disabled)
      ..loadHtmlString(
        '''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body style="margin:0;background:#081d34"><video controls playsinline preload="metadata" style="width:100%;height:100%;object-fit:contain"><source src="$safeUrl"></video></body></html>''',
      );
  });

  List<InlineSpan> _boldSpans(String value, TextStyle style) {
    final spans = <InlineSpan>[];
    final pattern = RegExp(r'\*\*(.+?)\*\*');
    var start = 0;
    for (final match in pattern.allMatches(value)) {
      if (match.start > start)
        spans.add(TextSpan(text: value.substring(start, match.start)));
      spans.add(
        TextSpan(
          text: match.group(1),
          style: style.copyWith(fontWeight: FontWeight.w700),
        ),
      );
      start = match.end;
    }
    if (start < value.length) spans.add(TextSpan(text: value.substring(start)));
    return spans;
  }

  Widget _answerLine(String line) {
    final trimmed = line.trim();
    if (trimmed.isEmpty) return const SizedBox(height: 7);
    final heading = trimmed.startsWith('# ');
    final bullet = trimmed.startsWith('- ') || trimmed.startsWith('* ');
    final text = heading
        ? trimmed.substring(2)
        : bullet
        ? '• ${trimmed.substring(2)}'
        : trimmed;
    final style = TextStyle(
      color: AppColors.ink,
      fontSize: heading ? 16 : 13,
      fontWeight: heading ? FontWeight.w700 : FontWeight.w400,
      height: 1.5,
    );
    return Padding(
      padding: const EdgeInsets.only(bottom: 5),
      child: Text.rich(
        TextSpan(style: style, children: _boldSpans(text, style)),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final images = _urls('image_urls');
    final videos = _urls('video_urls');
    return Scaffold(
      appBar: AppBar(title: const Text('FAQ')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 28),
        children: [
          Text(
            widget.article['title'] as String? ?? 'Support answer',
            style: const TextStyle(
              color: AppColors.ink,
              fontSize: 22,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            widget.article['category'] as String? ?? 'General',
            style: const TextStyle(color: AppColors.muted, fontSize: 12),
          ),
          const SizedBox(height: 16),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: (widget.article['answer'] as String? ?? '')
                    .split('\n')
                    .map(_answerLine)
                    .toList(),
              ),
            ),
          ),
          for (final url in images) ...[
            const SizedBox(height: 12),
            ClipRRect(
              borderRadius: BorderRadius.circular(14),
              child: Image.network(
                url,
                fit: BoxFit.contain,
                errorBuilder: (_, _, _) => const Card(
                  child: Padding(
                    padding: EdgeInsets.all(16),
                    child: Text('Image unavailable'),
                  ),
                ),
              ),
            ),
          ],
          if (videos.isNotEmpty) ...[
            const SizedBox(height: 20),
            const Text(
              'Videos',
              style: TextStyle(
                color: AppColors.ink,
                fontWeight: FontWeight.w700,
                fontSize: 15,
              ),
            ),
          ],
          for (final url in videos) ...[
            const SizedBox(height: 10),
            if (_directVideo(url))
              ClipRRect(
                borderRadius: BorderRadius.circular(14),
                child: AspectRatio(
                  aspectRatio: 16 / 9,
                  child: WebViewWidget(controller: _controller(url)),
                ),
              )
            else
              Card(
                child: ListTile(
                  leading: const Icon(
                    Icons.play_circle_outline,
                    color: AppColors.blue,
                  ),
                  title: const Text('Open video'),
                  subtitle: Text(
                    Uri.parse(url).host,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  trailing: const Icon(Icons.open_in_new_rounded),
                  onTap: () => launchUrl(
                    Uri.parse(url),
                    mode: LaunchMode.externalApplication,
                  ),
                ),
              ),
          ],
        ],
      ),
    );
  }
}
