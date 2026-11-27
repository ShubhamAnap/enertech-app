import 'package:enertech_customer/data/legal_repository.dart';
import 'package:enertech_customer/screens/customer_entry_gate.dart';
import 'package:enertech_customer/theme/app_theme.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

void main() {
  testWidgets(
    'LegalConsentRow renders small checkbox with inline Privacy Policy and Terms links',
    (tester) async {
      var accepted = false;
      var openedPrivacy = 0;
      var openedTerms = 0;

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light,
          home: Scaffold(
            body: StatefulBuilder(
              builder: (context, setState) => LegalConsentRow(
                accepted: accepted,
                enabled: true,
                onChanged: (value) => setState(() => accepted = value),
                onOpenPrivacy: () => openedPrivacy++,
                onOpenTerms: () => openedTerms++,
              ),
            ),
          ),
        ),
      );

      final checkbox = tester.widget<Checkbox>(find.byType(Checkbox));
      expect(checkbox.value, isFalse);
      expect(find.textContaining('Privacy Policy'), findsOneWidget);
      expect(find.textContaining('Terms of Use'), findsOneWidget);

      await tester.tap(find.byType(Checkbox));
      await tester.pump();
      expect(accepted, isTrue);
      expect(openedPrivacy, 0);
      expect(openedTerms, 0);
    },
  );

  test('LegalRepository builds public CMS legal page URLs cleanly', () {
    expect(
      LegalRepository.pageUrl('privacy-policy').toString(),
      'https://cms.enertechups.cloud/privacy-policy',
    );
    expect(
      LegalRepository.pageUrl('terms').toString(),
      'https://cms.enertechups.cloud/terms',
    );
  });
}
