import 'package:material_ui/material_ui.dart';

import 'screens/customer_entry_gate.dart';
import 'theme/app_theme.dart';

class EnerTechApp extends StatelessWidget {
  const EnerTechApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: BrandIdentity.companyName,
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      home: const CustomerEntryGate(),
    );
  }
}
