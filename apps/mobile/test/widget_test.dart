import 'package:enertech_customer/app.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

void main() {
  testWidgets('Home provides the primary customer journeys', (tester) async {
    await tester.pumpWidget(const EnerTechApp());
    expect(find.text('Reliable power.\nUninterrupted operations.'), findsOneWidget);
    expect(find.text('Explore products'), findsOneWidget);
    expect(find.text('Find a solution'), findsOneWidget);
    expect(find.text('Service & support'), findsOneWidget);
    expect(find.byType(NavigationBar), findsOneWidget);
  });

  testWidgets('Bottom navigation switches to the empty requests state', (tester) async {
    await tester.pumpWidget(const EnerTechApp());
    await tester.tap(find.text('Requests'));
    await tester.pumpAndSettle();
    expect(find.text('My requests'), findsOneWidget);
    expect(find.text('There are no account requests to show. Start with a guided enquiry when the submission workflow is available.'), findsOneWidget);
  });
}
