import 'package:enertech_customer/screens/faq_article_screen.dart';
import 'package:enertech_customer/screens/support_screen.dart';
import 'package:enertech_customer/screens/warranty_amc_screen.dart';
import 'package:enertech_customer/theme/app_theme.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

void main() {
  testWidgets(
    'SupportScreen renders Warranty & AMC card and FAQs below Service resources',
    (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light,
          home: Scaffold(
            body: SupportScreen(
              appContent: Future.value({
                'contacts': {
                  'support_phone': '+91 90000 00000',
                  'support_email': 'support@enertechups.test',
                },
              }),
              knowledge: Future.value([
                {
                  'id': 'faq-1',
                  'slug': 'ups-battery-care',
                  'title': 'How to maintain UPS batteries?',
                  'category': 'Maintenance',
                  'answer': '# Battery care\n- Keep terminals clean and **dry**.\nMore info: https://enertechups.com/support-guide',
                  'image_urls': <String>[],
                  'video_urls': ['https://youtu.be/example123'],
                },
              ]),
              onNavigate: (_) {},
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      final listScroll = find.byType(Scrollable).first;
      await tester.scrollUntilVisible(find.text('Warranty & AMC'), 200, scrollable: listScroll);
      expect(find.text('Warranty & AMC'), findsOneWidget);

      await tester.scrollUntilVisible(find.text('Service resources'), 200, scrollable: listScroll);
      await tester.scrollUntilVisible(find.text('How to maintain UPS batteries?'), 200, scrollable: listScroll);
      final serviceResourcesPos = tester.getTopLeft(find.text('Service resources'));
      final faqsPos = tester.getTopLeft(find.text('FAQs'));
      expect(faqsPos.dy, greaterThan(serviceResourcesPos.dy));

      await tester.tap(find.text('How to maintain UPS batteries?'));
      await tester.pumpAndSettle();
      expect(find.byType(FaqArticleScreen), findsOneWidget);
      expect(find.text('Open video'), findsOneWidget);
      expect(find.text('youtu.be'), findsOneWidget);
    },
  );

  testWidgets('FaqArticleScreen hides blank answer box for media-only FAQ', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.light,
        home: const FaqArticleScreen(
          article: {
            'title': 'Back Panel Sticker',
            'category': 'General',
            'answer': '',
            'image_urls': <String>[],
            'video_urls': ['https://youtu.be/demo'],
          },
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Back Panel Sticker'), findsOneWidget);
    expect(find.text('Open video'), findsOneWidget);
    expect(find.byType(Card), findsOneWidget);
  });

  testWidgets('WarrantyAmcScreen opens Register warranty and AMC forms', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(theme: AppTheme.light, home: const WarrantyAmcScreen()),
    );

    expect(find.text('Register warranty'), findsOneWidget);
    expect(find.text('AMC'), findsOneWidget);

    await tester.tap(find.text('Register warranty'));
    await tester.pumpAndSettle();
    expect(find.text('Customer name *'), findsOneWidget);
    expect(find.text('Email *'), findsOneWidget);
    expect(find.text('Mobile number *'), findsOneWidget);
    expect(find.text('Product serial number *'), findsOneWidget);
    expect(find.text('Date of purchase *'), findsOneWidget);

    await tester.pageBack();
    await tester.pumpAndSettle();

    await tester.tap(find.text('AMC'));
    await tester.pumpAndSettle();
    expect(find.text('Product serial number *'), findsOneWidget);
    expect(find.text('Location *'), findsOneWidget);
    expect(find.text('Date of purchase *'), findsOneWidget);
    expect(find.text('Customer name *'), findsNothing);
  });
}
