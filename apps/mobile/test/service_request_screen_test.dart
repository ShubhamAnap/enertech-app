import 'package:enertech_customer/data/catalogue_models.dart';
import 'package:enertech_customer/data/customer_requests_repository.dart';
import 'package:enertech_customer/screens/service_request_screen.dart';
import 'package:enertech_customer/theme/app_theme.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

void main() {
  testWidgets('ServiceRequestScreen exposes enabled gallery and camera photo upload controls', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.light,
        home: const ServiceRequestScreen(),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Photo uploads not available'), findsNothing);
    await tester.scrollUntilVisible(
      find.text('Choose photos'),
      300,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();

    expect(find.text('Choose photos'), findsOneWidget);
    expect(find.text('Take photo'), findsOneWidget);

    final chooseButton = tester.widget<OutlinedButton>(
      find.widgetWithText(OutlinedButton, 'Choose photos'),
    );
    final cameraButton = tester.widget<OutlinedButton>(
      find.widgetWithText(OutlinedButton, 'Take photo'),
    );
    expect(chooseButton.onPressed, isNotNull);
    expect(cameraButton.onPressed, isNotNull);
  });

  test('ProductCategory parses optional product_count and CustomerRequestRecord preserves attachments', () {
    final category = ProductCategory.fromJson({
      'id': 'c1',
      'slug': 'online-ups',
      'name': 'Online UPS',
      'product_count': 15,
    });
    expect(category.productCount, 15);

    final record = CustomerRequestRecord.fromJson({
      'id': 'req-1',
      'kind': 'service',
      'status': 'submitted',
      'created_at': '2026-11-26T10:00:00Z',
      'payload': {
        'product_model': 'HTXi-100',
        'problem_category': 'alarm',
        'attachments': ['https://cdn.example.test/enertech-public/service-requests/u1/fault.jpg'],
      },
    });
    expect(record.payload['attachments'], hasLength(1));
  });
}
